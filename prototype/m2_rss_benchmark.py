"""Measure M2 candidate-store startup, point lookup, and streaming RSS in fresh processes.

Fixture construction is isolated in the parent process. Each measurement runs
in a child with a fresh SQLite connection so fixture-generation memory is not
counted as candidate-store startup or read memory.
"""
from __future__ import annotations

import argparse
import io
import json
import resource
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Iterable

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.m2_semantic_unit_store import PersistentSemanticUnitCandidateStore
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope, SemanticUnitCandidate,
    TruthStatus, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


def _rss_bytes() -> int | None:
    try:
        with open("/proc/self/status", encoding="ascii") as stream:
            for line in stream:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _write_fixture(memory_path: Path, evidence_path: Path, count: int, scope: str) -> None:
    ingestor = SQLiteEvidenceIngestor(evidence_path)
    source = ("M2 isolated RSS benchmark source evidence. " * 64).encode("utf-8")
    result = ingestor.ingest(
        "m2-rss-fixture", "m2-rss-fixture.txt", io.BytesIO(source), chunk_bytes=4096,
    )
    if not result.complete:
        raise RuntimeError("M2 benchmark evidence fixture did not complete")
    resolver = SQLiteEvidenceRefResolver(evidence_path)
    reference = resolver.make_reference("m2-rss-fixture", resolver_chunk_id(evidence_path))
    memory = ZPCMMemory(memory_path)
    store = PersistentSemanticUnitCandidateStore(memory, resolver, scope=scope)
    try:
        for index in range(count):
            candidate = SemanticUnitCandidate(
                envelope=RecordEnvelope(
                    schema_version="m2-record-v1",
                    record_id=f"m2-rss:{index:08d}",
                    record_kind="SemanticUnitCandidate",
                    producer="m2-rss-benchmark",
                    producer_version="1",
                    recorded_at="2026-11-22T00:00:00Z",
                    scope=scope,
                    source_refs=(reference,),
                ),
                kind=UnitKind.ENTITY,
                surface_forms=(f"candidate-{index:08d}",),
                grounding_status=GroundingStatus.GROUNDED,
                epistemic_status=EpistemicStatus.ASSERTED,
                truth_status=TruthStatus.UNKNOWN,
            )
            store.record_candidate(candidate)
    finally:
        memory.close()


def resolver_chunk_id(evidence_path: Path) -> str:
    # Resolve the fixture's sole chunk without depending on a generated ID.
    import sqlite3
    connection = sqlite3.connect(evidence_path)
    try:
        row = connection.execute(
            "SELECT chunk_id FROM evidence_chunks WHERE document_id=? ORDER BY ordinal LIMIT 1",
            ("m2-rss-fixture",),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("M2 benchmark evidence chunk is missing")
    return str(row[0])


def _probe(memory_path: Path, evidence_path: Path, scope: str, lookup_id: str, page_size: int) -> dict:
    rss_before = _rss_bytes()
    resolver = SQLiteEvidenceRefResolver(evidence_path)
    memory = ZPCMMemory(memory_path)
    started = time.perf_counter()
    store = PersistentSemanticUnitCandidateStore(memory, resolver, scope=scope)
    startup_seconds = time.perf_counter() - started
    rss_after_startup = _rss_bytes()

    started = time.perf_counter()
    candidate = store.get_candidate(lookup_id)
    lookup_seconds = time.perf_counter() - started
    if candidate is None or candidate.envelope.record_id != lookup_id:
        raise RuntimeError("M2 benchmark indexed point lookup failed")

    started = time.perf_counter()
    first_page = []
    for item in store.iter_candidates(page_size=page_size):
        first_page.append(item)
        if len(first_page) >= page_size:
            break
    first_page_seconds = time.perf_counter() - started

    started = time.perf_counter()
    streamed_count = sum(1 for _ in store.iter_candidates(page_size=page_size))
    stream_seconds = time.perf_counter() - started
    result = {
        "startup_seconds": round(startup_seconds, 6),
        "point_lookup_seconds": round(lookup_seconds, 6),
        "first_page_seconds": round(first_page_seconds, 6),
        "first_page_records": len(first_page),
        "stream_scan_seconds": round(stream_seconds, 6),
        "streamed_records": streamed_count,
        "rss_before_store_bytes": rss_before,
        "rss_after_store_init_bytes": rss_after_startup,
        "peak_rss_bytes": _peak_rss_bytes(),
        "high_water_sequence": store._last_sequence,
    }
    memory.close()
    return result


def _run_child(memory_path: Path, evidence_path: Path, scope: str, lookup_id: str, page_size: int) -> dict:
    completed = subprocess.run(
        [
            sys.executable, "-m", "prototype.m2_rss_benchmark",
            "--probe", "--memory", str(memory_path), "--evidence", str(evidence_path),
            "--scope", scope, "--lookup-id", lookup_id, "--page-size", str(page_size),
        ],
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
    parser.add_argument("--scope", default="m2-rss-benchmark")
    parser.add_argument("--page-size", type=int, default=64)
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--memory", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--evidence", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--lookup-id", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.page_size < 1:
        parser.error("--page-size must be positive")
    if args.probe:
        if args.memory is None or args.evidence is None or not args.lookup_id:
            parser.error("probe requires memory, evidence, and lookup-id")
        print(json.dumps(_probe(
            args.memory, args.evidence, args.scope, args.lookup_id, args.page_size,
        ), sort_keys=True))
        return 0

    results = []
    with tempfile.TemporaryDirectory(prefix="m2-rss-") as temporary:
        root = Path(temporary)
        for count in args.sizes:
            memory_path = root / f"m2-{count}.sqlite"
            evidence_path = root / f"evidence-{count}.sqlite"
            _write_fixture(memory_path, evidence_path, count, args.scope)
            lookup_id = f"m2-rss:{count // 2:08d}"
            report = _run_child(
                memory_path, evidence_path, args.scope, lookup_id, args.page_size,
            )
            results.append({
                "fixture_records": count,
                "memory_db_bytes": memory_path.stat().st_size,
                "evidence_db_bytes": evidence_path.stat().st_size,
                **report,
            })
    print(json.dumps({
        "benchmark": "m2-candidate-startup-lookup-stream-rss-v1",
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "results": results,
        "interpretation": (
            "Fresh-process measurements for M2 semantic candidate storage. "
            "Store initialization, indexed point lookup, first bounded page, and "
            "full keyset-stream scan are timed separately. Fixture construction "
            "occurs in the parent process and is excluded from child RSS. "
            "Streaming scan consumes one candidate at a time; no full result list "
            "is retained. RSS is observational and not a hardware-independent limit."
        ),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
