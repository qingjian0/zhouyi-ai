"""Subprocess-isolated RSS benchmark for the N0.10 out-of-core path.

Example:
  python benchmarks/benchmark_n010_ooc_rss.py --sizes 1000 10000 --epochs 1

The parent writes JSONL; each measurement runs in a fresh child process so
peak RSS is attributable to indexing, streaming training, and evaluation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ru_maxrss_kib(value: int | float, platform: str | None = None) -> int:
    """Normalize getrusage.ru_maxrss to KiB (bytes on macOS, KiB on Linux)."""
    current_platform = sys.platform if platform is None else platform
    if current_platform == "darwin":
        return int(math.ceil(value / 1024.0))
    return int(value)


def _throughput_rates(train_records: int, total_records: int, elapsed_seconds: float) -> dict[str, float]:
    """Report end-to-end rates; elapsed includes indexing, training, and dev traversal."""
    if elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive")
    return {
        "train_rows_per_second_end_to_end": round(train_records / elapsed_seconds, 3),
        "total_rows_per_second_end_to_end": round(total_records / elapsed_seconds, 3),
    }


def _rss_kib() -> int:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        # macOS and non-procfs platforms use getrusage below.
        pass
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return _ru_maxrss_kib(value)


def _write_dataset(path: Path, records_per_split: int) -> None:
    with path.open("w", encoding="utf-8") as sink:
        for split, prefix in (("train", "tr"), ("dev", "dv")):
            for index in range(records_per_split):
                nodes = []
                targets = []
                for role in ("r0", "r1"):
                    target = f"{prefix}-{index}-{role}-positive"
                    targets.append(target)
                    nodes.extend((
                        {"node_id": target, "node_type": role, "features": [1.0, 0.5],
                         "tags": ["eligible"], "evidence_ids": [f"ev-{target}"]},
                        {"node_id": f"{prefix}-{index}-{role}-negative",
                         "node_type": role, "features": [-1.0, -0.5],
                         "tags": ["eligible"], "evidence_ids": []},
                    ))
                row = {
                    "id": f"{prefix}-{index}", "split": split,
                    "rule_family": "train-family" if split == "train" else "dev-family",
                    "group_id": f"{prefix}-source-{index // 4}",
                    "source_group_id": f"{prefix}-document-{index // 4}",
                    "nodes": nodes, "target_ids": targets,
                }
                sink.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _worker(dataset: Path, records: int, epochs: int) -> dict:
    from prototype.n09_learnable_srok import LearnableSROK, RoleSpec
    from prototype.n010_ooc import N010StreamingDataset

    roles = tuple(
        RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
        for name in ("r0", "r1")
    )
    baseline = _rss_kib()
    started = time.perf_counter()
    with N010StreamingDataset(
        dataset, roles, 2, expected_splits=("train", "dev")
    ) as stream:
        model = LearnableSROK(roles, 2)
        losses = model.fit_reiterable(
            stream.iter_training_examples, epochs=epochs,
            max_assignments_per_example=4,
        )
        dev_count = sum(1 for _ in stream.iter_split_rows("dev"))
        manifest = stream.manifest
    elapsed = time.perf_counter() - started
    peak = _ru_maxrss_kib(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    rates = _throughput_rates(records, manifest["records"], elapsed)
    return {
        "records_per_split": records,
        "total_records": manifest["records"],
        "epochs": epochs,
        "baseline_rss_kib": baseline,
        "peak_rss_kib": peak,
        "observed_peak_minus_baseline_kib": max(0, peak - baseline),
        "dev_rows_streamed": dev_count,
        "final_loss": losses[-1],
        "elapsed_seconds": round(elapsed, 3),
        **rates,
        "index": manifest["index"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[1000, 10000])
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--dataset")
    parser.add_argument("--records", type=int, default=0)
    args = parser.parse_args()

    if args.worker:
        result = _worker(Path(args.dataset), args.records, args.epochs)
        print(json.dumps(result, sort_keys=True))
        return

    results = []
    with tempfile.TemporaryDirectory(prefix="zhouyi-n010-rss-") as temp:
        for size in args.sizes:
            if size < 1:
                parser.error("sizes must be positive")
            dataset = Path(temp) / f"dataset-{size}.jsonl"
            _write_dataset(dataset, size)
            command = [
                sys.executable, str(Path(__file__).resolve()), "--worker",
                "--dataset", str(dataset), "--records", str(size),
                "--epochs", str(args.epochs),
            ]
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True,
                cwd=str(ROOT),
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "RSS worker failed for "
                    f"{size} records per split (exit {completed.returncode}):\\n"
                    f"stdout:\\n{completed.stdout}\\nstderr:\\n{completed.stderr}"
                )
            try:
                results.append(json.loads(completed.stdout.strip().splitlines()[-1]))
            except (IndexError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"RSS worker emitted invalid JSON for {size} records per split: "
                    f"{completed.stdout!r}; stderr={completed.stderr!r}"
                ) from exc

    output = {
        "benchmark": "n010_ooc_subprocess_peak_rss",
        "platform": sys.platform,
        "measurements": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
