"""Fair serial/parallel execution comparison for deterministic experiment handlers."""
from __future__ import annotations

import copy
import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from .scheduler import Handler, Scheduler, TaskGraph, TaskSpec


def _canonical(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("benchmark outputs must be finite JSON values") from exc


def _result_projection(state: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Exclude timing/attempt metadata; compare semantic task outcomes only."""
    return {
        task_id: {
            "status": item["status"],
            "result": item.get("result"),
            "error": item.get("error"),
        }
        for task_id, item in sorted(state.items())
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


async def _execute_once(
    tasks: list[TaskSpec],
    handlers: Mapping[str, Handler],
    concurrency: int,
    checkpoint: Path,
) -> dict[str, Any]:
    isolated_tasks = [
        TaskSpec(
            task_id=task.task_id,
            handler=task.handler,
            depends_on=task.depends_on,
            payload=copy.deepcopy(task.payload),
            max_retries=task.max_retries,
        )
        for task in tasks
    ]
    scheduler = Scheduler(
        TaskGraph(isolated_tasks), handlers,
        checkpoint=checkpoint, concurrency=concurrency,
    )
    started = time.perf_counter()
    state = await scheduler.run()
    elapsed = time.perf_counter() - started
    projection = _result_projection(state)
    return {
        "wall_seconds": elapsed,
        "task_count": len(tasks),
        "succeeded": sum(x["status"] == "succeeded" for x in projection.values()),
        "failed": sum(x["status"] == "failed" for x in projection.values()),
        "blocked": sum(x["status"] == "blocked" for x in projection.values()),
        "output_digest": _digest(projection),
        "per_task_output_digests": {
            task_id: _digest(outcome) for task_id, outcome in projection.items()
        },
        "outputs": projection,
    }


async def run_serial_parallel_benchmark(
    tasks: list[TaskSpec],
    handlers: Mapping[str, Handler],
    parallelism: int = 4,
    repeats: int = 3,
) -> dict[str, Any]:
    """Run identical tasks serially and concurrently, then verify output equality.

    Handlers must be deterministic and side-effect-free, or explicitly
    idempotent. Each repetition gets fresh scheduler state and checkpoints.
    """
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a non-empty list")
    if isinstance(parallelism, bool) or not isinstance(parallelism, int) or parallelism < 2:
        raise ValueError("parallelism must be an integer >= 2")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError("repeats must be a positive integer")

    # Validate graph and handler coverage before starting the stopwatch.
    graph = TaskGraph(tasks)
    task_set_digest = _digest([
        {
            "task_id": task.task_id,
            "handler": task.handler,
            "depends_on": list(task.depends_on),
            "payload": task.payload,
            "max_retries": task.max_retries,
        }
        for task in tasks
    ])
    unknown = {task.handler for task in graph.tasks.values()} - handlers.keys()
    if unknown:
        raise ValueError(f"unregistered handlers: {sorted(unknown)}")

    serial_runs: list[dict[str, Any]] = []
    parallel_runs: list[dict[str, Any]] = []
    # A private temporary root prevents stale checkpoints from contaminating runs.
    with tempfile.TemporaryDirectory(prefix="zhouyi-benchmark-") as temp:
        root = Path(temp)
        for index in range(repeats):
            # Alternate order to reduce systematic warm-up/order bias.
            modes = (("serial", 1), ("parallel", parallelism))
            if index % 2:
                modes = tuple(reversed(modes))
            for mode, concurrency in modes:
                result = await _execute_once(
                    tasks, handlers, concurrency,
                    root / f"repeat-{index:03d}" / f"{mode}.checkpoint.json",
                )
                if mode == "serial":
                    serial_runs.append(result)
                else:
                    parallel_runs.append(result)

    paired_equal = [
        serial_runs[i]["output_digest"] == parallel_runs[i]["output_digest"]
        for i in range(repeats)
    ]
    serial_digests = {run["output_digest"] for run in serial_runs}
    parallel_digests = {run["output_digest"] for run in parallel_runs}
    serial_median = statistics.median(x["wall_seconds"] for x in serial_runs)
    parallel_median = statistics.median(x["wall_seconds"] for x in parallel_runs)
    all_succeeded = all(
        run["failed"] == 0 and run["blocked"] == 0
        and run["succeeded"] == run["task_count"]
        for run in serial_runs + parallel_runs
    )
    equivalent = (
        all(paired_equal) and len(serial_digests) == 1
        and len(parallel_digests) == 1
    )
    return {
        "schema_version": 1,
        "task_count": len(tasks),
        "task_set_digest": task_set_digest,
        "repeats": repeats,
        "parallelism": parallelism,
        "equivalent": equivalent,
        "all_succeeded": all_succeeded,
        "paired_equivalence": paired_equal,
        "serial": {
            "median_wall_seconds": serial_median,
            "runs": serial_runs,
        },
        "parallel": {
            "median_wall_seconds": parallel_median,
            "runs": parallel_runs,
        },
        "speedup": (serial_median / parallel_median) if parallel_median > 0 else None,
        "interpretation": (
            "valid_for_speed_comparison" if equivalent and all_succeeded
            else "task_failures_present" if equivalent
            else "outputs_not_equivalent_or_not_repeatable"
        ),
        "notes": [
            "Speedup is descriptive wall-clock throughput, not evidence of improved reasoning quality.",
            "Use deterministic, side-effect-free or idempotent handlers.",
            "Run on the same machine and report CPU, memory, Python version and system load separately.",
            "Checkpoint files are isolated per run and removed after the benchmark.",
        ],
    }
