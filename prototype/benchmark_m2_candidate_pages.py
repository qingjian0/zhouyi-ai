"""Isolated-process RSS benchmark for the M2 bounded candidate-page reader.

Example:
  python -m prototype.benchmark_m2_candidate_pages --records 1000 --json

The parent builds a deterministic synthetic M1/M2 corpus. A fresh spawned
process then opens the stores and traverses every current-candidate page,
reporting sampled RSS and the OS high-water mark separately from serialized
page bytes. This is a benchmark, not a production memory guarantee.
"""
from __future__ import annotations

import argparse
import io
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
from typing import Any

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.memory_budget import ProcessMemoryMeasurement, sample_process_memory
from prototype.m2_semantic_unit_store import (
    MAX_EVENT_BYTES,
    MAX_REPLAY_PAGE_BYTES,
    PersistentM2SemanticUnitStore,
)
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope, RoleBinding,
    SemanticUnitCandidate, TruthStatus, TypedAttribute, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


SCOPE = "m2-page-benchmark"


def _candidate(index: int, reference) -> SemanticUnitCandidate:
    record_id = f"bench-{index:08d}"
    return SemanticUnitCandidate(
        envelope=RecordEnvelope(
            schema_version="m2-record-v1",
            record_id=record_id,
            record_kind="SemanticUnitCandidate",
            producer="m2-page-benchmark",
            producer_version="1",
            recorded_at="2026-11-12T00:00:00Z",
            scope=SCOPE,
            source_refs=(reference,),
            derivation_refs=(f"benchmark-observation-{index:08d}",),
        ),
        kind=UnitKind.EVENT,
        surface_forms=(f"synthetic relation event {index:08d}",),
        typed_attributes=(
            TypedAttribute(
                "agent", "entity_ref", "entity:benchmark",
                source_refs=(reference,),
            ),
        ),
        role_bindings=(
            RoleBinding("agent", "entity:benchmark"),
            RoleBinding("patient", f"entity:item-{index:08d}"),
        ),
        grounding_status=GroundingStatus.GROUNDED,
        epistemic_status=EpistemicStatus.ASSERTED,
        extractor_confidence=0.8,
        truth_status=TruthStatus.UNKNOWN,
    )


def _reader_worker(
    connection,
    evidence_db: str,
    memory_db: str,
    page_size: int,
    max_event_bytes: int,
    page_budget_bytes: int,
    sample_interval: float,
) -> None:
    memory = None
    try:
        resolver = SQLiteEvidenceRefResolver(evidence_db)
        with ProcessMemoryMeasurement(sample_interval) as measurement:
            memory = ZPCMMemory(memory_db)
            store = PersistentM2SemanticUnitStore(
                memory,
                resolver,
                scope=SCOPE,
                max_event_bytes=max_event_bytes,
                max_replay_page_bytes=page_budget_bytes,
            )
            cursor = None
            records_read = 0
            page_count = 0
            max_page_payload_bytes = 0
            while True:
                page = store.read_candidate_page(
                    after_root_id=cursor, page_size=page_size,
                )
                page_count += 1
                records_read += len(page.items)
                max_page_payload_bytes = max(
                    max_page_payload_bytes, page.payload_bytes,
                )
                cursor = page.next_cursor
                del page
                if cursor is None:
                    break
            if memory is not None:
                memory.close()
                memory = None
        report = measurement.report
        if report is None:
            raise RuntimeError("RSS measurement did not produce a report")
        sample = sample_process_memory()
        connection.send({
            "records_read": records_read,
            "page_count": page_count,
            "max_page_payload_bytes": max_page_payload_bytes,
            "sampled_memory": report.to_dict(),
            "os_peak_rss_bytes": sample.os_peak_rss_bytes,
            "rss_source": sample.source,
        })
    except BaseException as exc:
        try:
            connection.send({"error": f"{type(exc).__name__}: {exc}"})
        except (BrokenPipeError, OSError):
            pass
        raise
    finally:
        if memory is not None:
            memory.close()
        connection.close()


def run_benchmark(
    *, records: int = 1000, page_size: int = 64,
    page_budget_bytes: int = MAX_REPLAY_PAGE_BYTES,
    sample_interval: float = 0.005,
) -> dict[str, Any]:
    if isinstance(records, bool) or not isinstance(records, int) or records < 1:
        raise ValueError("records must be a positive integer")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 128:
        raise ValueError("page_size must be in [1, 128]")
    if (isinstance(page_budget_bytes, bool) or not isinstance(page_budget_bytes, int)
            or not 8192 <= page_budget_bytes <= MAX_REPLAY_PAGE_BYTES):
        raise ValueError("page_budget_bytes must be in [8192, 4194304]")
    max_event_bytes = min(MAX_EVENT_BYTES, page_budget_bytes)

    with tempfile.TemporaryDirectory(prefix="zhouyi-m2-page-bench-") as temporary:
        root = Path(temporary)
        evidence_db = root / "evidence.sqlite3"
        memory_db = root / "zpcm.sqlite3"

        ingestor = SQLiteEvidenceIngestor(evidence_db)
        source = ("Zhouyi-AI bounded candidate-page benchmark evidence.\n" * 4).encode("utf-8")
        ingest = ingestor.ingest(
            "benchmark-document", "synthetic://m2-page-benchmark",
            io.BytesIO(source), chunk_bytes=512,
        )
        if not ingest.complete:
            raise RuntimeError("synthetic M1 evidence ingestion did not complete")
        chunk = ingestor.get_chunks("benchmark-document")[0]
        resolver = SQLiteEvidenceRefResolver(evidence_db)
        reference = resolver.make_reference("benchmark-document", chunk.chunk_id)

        memory = ZPCMMemory(memory_db)
        try:
            store = PersistentM2SemanticUnitStore(
                memory,
                resolver,
                scope=SCOPE,
                max_event_bytes=max_event_bytes,
                max_replay_page_bytes=page_budget_bytes,
            )
            for index in range(records):
                store.record_candidate(_candidate(index, reference))
        finally:
            memory.close()

        parent = multiprocessing.get_context("spawn")
        receive, send = parent.Pipe(duplex=False)
        process = parent.Process(
            target=_reader_worker,
            args=(
                send, str(evidence_db), str(memory_db), page_size,
                max_event_bytes, page_budget_bytes, sample_interval,
            ),
        )
        process.start()
        send.close()
        try:
            if not receive.poll(300):
                process.kill()
                process.join(timeout=5)
                raise TimeoutError("isolated M2 page-reader benchmark exceeded 300 seconds")
            result = receive.recv()
        finally:
            receive.close()
        process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        if process.exitcode != 0:
            raise RuntimeError(result.get("error", f"reader worker exited {process.exitcode}"))
        if "error" in result:
            raise RuntimeError(result["error"])
        if result["records_read"] != records:
            raise RuntimeError(
                f"page reader returned {result['records_read']} of {records} candidates"
            )

        return {
            "records_requested": records,
            "records_read": result["records_read"],
            "page_size_limit": page_size,
            "page_budget_bytes": page_budget_bytes,
            "max_event_bytes": max_event_bytes,
            "page_count": result["page_count"],
            "max_page_payload_bytes": result["max_page_payload_bytes"],
            "evidence_database_bytes": evidence_db.stat().st_size,
            "memory_database_bytes": memory_db.stat().st_size,
            "isolated_reader": {
                "sampled_memory": result["sampled_memory"],
                "os_peak_rss_bytes": result["os_peak_rss_bytes"],
                "rss_source": result["rss_source"],
            },
            "measurement_warning": (
                "sampled RSS can miss short-lived peaks; OS high-water is reported "
                "separately. Serialized page bytes are not equivalent to Python heap "
                "or total process RSS. This synthetic benchmark is not a device SLA."
            ),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--page-size", type=int, default=64)
    parser.add_argument("--page-budget-bytes", type=int, default=MAX_REPLAY_PAGE_BYTES)
    parser.add_argument("--sample-interval", type=float, default=0.005)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_benchmark(
        records=args.records,
        page_size=args.page_size,
        page_budget_bytes=args.page_budget_bytes,
        sample_interval=args.sample_interval,
    )
    print(json.dumps(report, sort_keys=True) if args.json else json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
