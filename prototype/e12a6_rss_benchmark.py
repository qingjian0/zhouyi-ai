"""Measure isolated E12-A6 restore RSS and latency at increasing history sizes.

Fixture generation happens in the parent process. Each restore runs in a fresh
subprocess so process peak RSS is not contaminated by fixture construction.
The benchmark reports observations; it does not encode hardware-specific limits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
from typing import Iterable


from prototype.e12a6_lifecycle_contract import Action, ActionType, Candidate, CandidateState, Evidence, SplitRole
from prototype.e12a6_zpcm_persistence import (
    EVENT_SCHEMA, PersistentLifecycleLedger, _action_to_dict, _candidate_to_dict,
    _evidence_to_dict, _safe_evidence,
)
from prototype.zpcm_memory import ZPCMMemory


def _proc_status_memory_bytes(field: str) -> int | None:
    try:
        with open("/proc/self/status", encoding="ascii") as stream:
            for line in stream:
                if line.startswith(f"{field}:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _cgroup_memory_bytes(filename: str) -> int | None:
    try:
        raw = Path("/sys/fs/cgroup", filename).read_text(encoding="ascii").strip()
        if raw == "max":
            return None
        value = int(raw)
        return value if value >= 0 else None
    except (OSError, ValueError):
        return None


def _peak_rss_bytes() -> int:
    high_water = _proc_status_memory_bytes("VmHWM")
    if high_water is not None:
        return high_water
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _candidate(index: int, evidence_id: str | None = None) -> Candidate:
    return Candidate(
        candidate_id=f"benchmark:rule:{index}",
        version=1,
        canonical_expression=f"input_0 > threshold_{index}",
        proposer_family="rss-benchmark",
        supporting_families=("rss-benchmark",),
        input_types=("number",),
        operator="THRESHOLD_GT",
        complexity=1,
        evidence_ids=(evidence_id,) if evidence_id is not None else (),
    )


def _evidence(index: int) -> Evidence:
    return _safe_evidence(Evidence(
        evidence_id=f"benchmark:evidence:{index}",
        episode_id=f"benchmark:episode:{index}",
        world_family="rss-benchmark-world",
        split_role=SplitRole.TRAIN,
        observation_id=f"benchmark:observation:{index}",
        outcome=f"opaque-evidence-ref:{index}",
        model_version="rss-benchmark-model",
        prediction_commit_step=1,
        label_visibility_step=2,
    ))


def _action(index: int, candidate_id: str) -> Action:
    return Action(
        action_id=f"benchmark:propose:{index}",
        action_type=ActionType.PROPOSE,
        candidate_id=candidate_id,
        candidate_version=1,
        from_state=CandidateState.OBSERVED,
        to_state=CandidateState.PROPOSED,
    )


def _write_fixture(
    path: Path, count: int, scope: str, batch_size: int, *,
    checkpoint: bool = False, event_mix: str = "candidate-only",
) -> int:
    if event_mix not in {"candidate-only", "mixed"}:
        raise ValueError("event_mix must be candidate-only or mixed")
    memory = ZPCMMemory(path)
    sequence = 0
    try:
        pending = []
        for index in range(count):
            candidate = _candidate(index, f"benchmark:evidence:{index}" if event_mix == "mixed" else None)
            if event_mix == "mixed":
                evidence = _evidence(index)
                action = _action(index, candidate.candidate_id)
                pending.extend([
                    {
                        "event_id": f"e12a6:evidence:{evidence.evidence_id}",
                        "payload": {
                            "schema_version": EVENT_SCHEMA,
                            "kind": "evidence_registered",
                            "body": {"evidence": _evidence_to_dict(evidence)},
                        },
                    },
                    {
                        "event_id": f"e12a6:candidate:{candidate.candidate_id}@1",
                        "payload": {
                            "schema_version": EVENT_SCHEMA,
                            "kind": "candidate_registered",
                            "body": {"candidate": _candidate_to_dict(candidate)},
                        },
                    },
                    {
                        "event_id": f"e12a6:action:{action.action_id}",
                        "payload": {
                            "schema_version": EVENT_SCHEMA,
                            "kind": "action_applied",
                            "body": {"action": _action_to_dict(action)},
                        },
                    },
                ])
            else:
                pending.append({
                    "event_id": f"e12a6:candidate:{candidate.candidate_id}@1",
                    "payload": {
                        "schema_version": EVENT_SCHEMA,
                        "kind": "candidate_registered",
                        "body": {"candidate": _candidate_to_dict(candidate)},
                    },
                })
            while len(pending) >= batch_size:
                batch, pending = pending[:batch_size], pending[batch_size:]
                receipts = memory.append_lifecycle_events(
                    events=batch, scope=scope, expected_sequence=sequence,
                )
                sequence = receipts[-1]["sequence"]
        if pending:
            receipts = memory.append_lifecycle_events(
                events=pending, scope=scope, expected_sequence=sequence,
            )
            sequence = receipts[-1]["sequence"]
        if checkpoint:
            store = PersistentLifecycleLedger(memory, scope=scope)
            try:
                store.checkpoint()
            finally:
                store.close()
    finally:
        memory.close()
    return sequence


def _restore_report(path: Path, scope: str) -> dict[str, int | float | None]:
    before = _proc_status_memory_bytes("VmRSS")
    memory_started = time.perf_counter()
    memory = ZPCMMemory(path)
    zpcm_init_seconds = time.perf_counter() - memory_started
    after_zpcm = _proc_status_memory_bytes("VmRSS")
    checkpoint = memory.load_e12a6_lifecycle_checkpoint(scope=scope)
    store = None
    try:
        restore_started = time.perf_counter()
        store = PersistentLifecycleLedger(memory, scope=scope)
        restore_seconds = time.perf_counter() - restore_started
        counts = memory.lifecycle_state_projection_counts(scope=scope)
        after_restore = _proc_status_memory_bytes("VmRSS")
        return {
            "restore_duration_seconds": round(restore_seconds, 6),
            "restore_events_per_second": round(store._last_sequence / restore_seconds, 2) if restore_seconds > 0 else None,
            "rss_before_zpcm_bytes": before,
            "rss_after_zpcm_bytes": after_zpcm,
            "rss_after_restore_bytes": after_restore,
            "peak_rss_bytes": _peak_rss_bytes(),
            "zpcm_init_duration_seconds": round(zpcm_init_seconds, 6),
            "cgroup_memory_current_bytes": _cgroup_memory_bytes("memory.current"),
            "cgroup_memory_peak_bytes": _cgroup_memory_bytes("memory.peak"),
            "last_sequence": store._last_sequence,
            "checkpoint_sequence": checkpoint["checkpoint_sequence"] if checkpoint else None,
            "restored_candidate_count": len(store._ledger.candidates),
            "candidate_projection_count": counts["candidates"],
            "evidence_projection_count": counts["evidence"],
            "action_projection_count": counts["actions"],
        }
    finally:
        if store is not None:
            store.close()
        memory.close()


def _run_child(path: Path, scope: str) -> dict[str, int | float | None]:
    completed = subprocess.run(
        [sys.executable, "-m", "prototype.e12a6_rss_benchmark", "--restore", str(path), "--scope", scope],
        check=True, capture_output=True, text=True,
    )
    return json.loads(completed.stdout)


def _parse_sizes(value: str) -> list[int]:
    try:
        sizes = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be positive comma-separated integers") from exc
    if not sizes or any(size < 1 for size in sizes):
        raise argparse.ArgumentTypeError("sizes must be positive comma-separated integers")
    return sorted(set(sizes))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=_parse_sizes, default=_parse_sizes("1000,10000,50000"))
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--event-mix", choices=("candidate-only", "mixed"), default="candidate-only")
    parser.add_argument("--checkpoint", action="store_true",
                        help="publish a verified checkpoint before measuring restore")
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
            event_count = _write_fixture(
                path, count, args.scope, args.batch_size, checkpoint=args.checkpoint, event_mix=args.event_mix,
            )
            report = _run_child(path, args.scope)
            results.append({"fixture_records": count, "history_events": event_count, "event_mix": args.event_mix, "fixture_bytes": path.stat().st_size, **report})
    print(json.dumps({
        "benchmark": (
            "e12a6-checkpoint-restore-rss-v1" if args.checkpoint
            else "e12a6-restore-rss-v2"
        ),
        "event_mix": args.event_mix,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "results": results,
        "interpretation": (
            "Fresh-process RSS and restore latency for synthetic candidate-registration histories. "
            "Fixture generation and ZPCM initialization are excluded from restore duration. "
            + ("A verified checkpoint is loaded; its event prefix is still digest-checked, while semantic "
               "replay is limited to the suffix. This is not O(1) restore. " if args.checkpoint else "")
            + "This does not measure production event mixes or impose a hardware-independent memory guarantee."
        ),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
