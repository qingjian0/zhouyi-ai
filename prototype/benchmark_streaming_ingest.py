"""Measure streaming evidence ingestion on a real input file.

Example:
  python -m prototype.benchmark_streaming_ingest input.txt evidence.sqlite3 \
      --document-id corpus-v1 --chunk-bytes 8192 --json
  python -m prototype.benchmark_streaming_ingest input.txt evidence.sqlite3 \
      --document-id corpus-v1 --tokenizer my_tokenizer:count_tokens --json

The database path must not already exist. Tokenizer plugins must expose a
callable accepting one text chunk and returning its exact token count.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import time

from prototype.memory_budget import ProcessMemoryMeasurement, sample_process_memory
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor


def _load_tokenizer(spec: str):
    if ":" not in spec:
        raise ValueError("tokenizer must use module:callable syntax")
    module_name, attribute = spec.split(":", 1)
    if not module_name or not attribute:
        raise ValueError("tokenizer must use module:callable syntax")
    module = importlib.import_module(module_name)
    tokenizer = getattr(module, attribute)
    if not callable(tokenizer):
        raise TypeError(f"tokenizer is not callable: {spec}")
    return tokenizer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--chunk-bytes", type=int, default=8192)
    parser.add_argument("--tokenizer", help="exact tokenizer as module:callable")
    parser.add_argument("--sample-interval", type=float, default=0.01)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    source_path = args.input.resolve()
    database_path = args.database.resolve()
    if not source_path.is_file():
        parser.error(f"input file does not exist: {source_path}")
    if database_path.exists():
        parser.error(f"database already exists; choose a fresh path: {database_path}")
    if args.chunk_bytes < 4:
        parser.error("--chunk-bytes must be >= 4")

    # SQLite can create the database file, but it cannot create missing parent
    # directories. Make the requested output location usable before opening it.
    database_path.parent.mkdir(parents=True, exist_ok=True)

    tokenizer = _load_tokenizer(args.tokenizer) if args.tokenizer else None
    before = source_path.stat()
    baseline = sample_process_memory()
    started = time.perf_counter()
    store = SQLiteEvidenceIngestor(database_path)
    with ProcessMemoryMeasurement(args.sample_interval) as measurement:
        with source_path.open("rb") as stream:
            result = store.ingest(
                args.document_id,
                str(source_path),
                stream,
                chunk_bytes=args.chunk_bytes,
                tokenizer=tokenizer,
            )
    elapsed = time.perf_counter() - started
    after = source_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("input file changed while it was being ingested")

    report = measurement.report
    assert report is not None
    db_bytes = database_path.stat().st_size
    wal_path = Path(str(database_path) + "-wal")
    shm_path = Path(str(database_path) + "-shm")
    payload = {
        "document_id": result.document_id,
        "complete": result.complete,
        "chunks_committed": result.chunks_committed,
        "source_bytes": result.next_byte_offset,
        "chunk_bytes": args.chunk_bytes,
        "tokenizer_configured": tokenizer is not None,
        "all_persisted_token_counts_known": result.token_count_known,
        "elapsed_seconds": elapsed,
        "throughput_mib_per_second": (
            result.next_byte_offset / (1024 * 1024) / elapsed if elapsed else None
        ),
        "database_bytes": db_bytes,
        "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        "shm_bytes": shm_path.stat().st_size if shm_path.exists() else 0,
        "baseline_rss_bytes": baseline.rss_bytes,
        "os_peak_rss_bytes_after_run": sample_process_memory().os_peak_rss_bytes,
        "sampled_memory": report.to_dict(),
        "measurement_warning": (
            "sampled peak can miss short-lived allocations; run in a fresh isolated "
            "process and retain OS high-water metrics for release decisions"
        ),
    }
    print(json.dumps(payload, sort_keys=True) if args.json else json.dumps(payload, indent=2))
    return 0 if result.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
