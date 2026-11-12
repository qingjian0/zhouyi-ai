"""Measure process RSS while restoring E12-A6 lifecycle histories.

The benchmark separates ZPCM startup from E12-A6 replay and runs each restore
in a fresh subprocess so ru_maxrss is not contaminated by fixture creation.
It intentionally measures the current implementation; it does not assert a
memory target or replace an OS-level/cgroup benchmark.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import tempfile
import time
from typing import Iterable

from prototype.e12a6_lifecycle_contract import Candidate
from prototype.e12a6_zpcm_persistence import (
    EVENT_SCHEMA,
    PersistentLifecycleLedger,
    _candidate_to_dict,
)
from prototype.zpcm_memory import ZPCMMemory


def _current_rss_bytes() -> int | None:
    """Return current resident set size from procfs where available."""
    try:
        with open("/proc/self/status", encoding="ascii") as stream:
            for line in stream:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _cgroup_memory_bytes(filename: str) -> int | None:
    """Read a cgroup v2 memory counter when the process is containerized."""
    try:
        raw = Path("/sys/fs/cgroup", filename).read_text(encoding="ascii").strip()
        if raw == "max":
            return None
        value = int(raw)
        return value if value >= 0 else None
    except (OSError, ValueError):
        return None


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux/BSD report KiB; macOS reports bytes.
    return value if sys.platform == "darwin" else value * 1024


def _candidate(index: int) -> Candidate:
    return Candidate(
        candidate_id=f"benchmark:rule:{index}",
        version=1,
        canonical_expression=f"input_0 > threshold_{index}",
        proposer_family="rss-benchmark",
        supporting_families=("rss-benchmark",),
        input_types=("number",),
        operator="THRESHOLD_GT",
        complexity=1,
    )


def _write_fixture(path: Path, count: int, scope: str, batch_size: int) -> int:
    memory = ZPCMMemory(path)
    sequence = 0
    try:
        for start in range(0, count, batch_size):
            events = []
            for index in range(start, min(start + batch_size, count)):
                candidate = _candidate(index)
                events.append({
                    "event_id": f"e12a6:candidate:{candidate.candidate_id}@1",
                    "payload": {
                        "schema_version": EVENT_SCHEMA,
                        "kind": "candidate_registered",
                        "body": {"candidate": _candidate_to_dict(candidate)},
                    },
                })
            receipts = memory.append_lifecycle_events(
                events=events,
                scope=scope,
                expected_sequence=sequence,
            )
            sequence = receipts[-1]["sequence"]
    finally:
        memory.close()
    return sequence


def _restore_report(path: Path, scope: str) -> dict[str, int | None]:
    before = _current_rss_bytes()
    memory = ZPCMMemory(path)
    after_zpcm = _current_rss_bytes()
    store = None
    try:
        restore_started = time.perf_counter()
        store = PersistentLifecycleLedger(memory, scope=scope)
        restore_duration = time.perf_counter() - restore_started
        after_restore = _current_rss_bytes()
        return {
            "restore_duration_seconds": round(restore_duration, 6),
            "restore_events_per_second": (
                round(store._last_sequence / restore_duration, 2)
                if restore_duration > 0 else None
            ),
            "rss_before_zpcm_bytes": before,
            "rss_after_zpcm_bytes": after_zpcm,
            "rss_after_e12a6_restore_bytes": after_restore,
            "zpcm_init_seconds": zpcm_init_seconds,
            "e12a6_restore_seconds": restore_seconds,
            "peak_rss_bytes": _peak_rss_bytes(),
            "cgroup_memory_current_bytes": _cgroup_memory_bytes("memory.current"),
            "cgroup_memory_peak_bytes": _cgroup_memory_bytes("memory.peak"),
            "last_sequence": store._last_sequence,
            "restored_candidate_count": len(store._ledger.candidates),
            "indexed_lifecycle_projection_count": int(memory.db.execute(
                "SELECT COUNT(*) FROM e12a6_lifecycle_event_projection WHERE scope=?",
                (scope,),
            ).fetchone()[0]),
        }
    finally:
        if store is not None:
            store.close()
        memory.close()


def _run_child(path: Path, scope: str) -> dict[str, int | None]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "prototype.e12a6_rss_benchmark",
            "--restore",
            str(path),
            "--scope",
            scope,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _parse_sizes(value: str) -> list[int]:
    sizes = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not sizes or any(size < 1 for size in sizes):
        raise argparse.ArgumentTypeError("sizes must be positive comma-separated integers")
    return sorted(set(sizes))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=_parse_sizes, default=_parse_sizes("1000,10000,50000"))
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--scope", default="e12a6-rss-benchmark")
    parser.add_argument("--restore", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.restore is not None:
        print(json.dumps(_restore_report(args.restore, args.scope), sort_keys=True))
        return 0
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    results = []
    with tempfile.TemporaryDirectory(prefix="e12a6-rss-") as temporary:
        root = Path(temporary)
        for count in args.sizes:
            path = root / f"lifecycle-{count}.sqlite"
            event_count = _write_fixture(path, count, args.scope, args.batch_size)
            report = _run_child(path, args.scope)
            results.append({
                "history_events": event_count,
                "fixture_bytes": path.stat().st_size,
                **report,
            })
    print(json.dumps({
        "benchmark": "e12a6-restore-rss-v1",
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "results": results,
        "interpretation": (
            "Compare E12-A6 restore RSS and elapsed replay time across history sizes. "
            "Restore duration excludes fixture generation and ZPCM initialization. "
            "These are observational measurements, not pass/fail performance guarantees."
        ),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
