"""Measure ZPCM keyset-reader memory without conflating bytes with RSS.

Run from the repository root:
    python benchmarks/benchmark_zpcm_keyset_memory.py --events 10000 --page-size 128

The report separates Python allocation peak (tracemalloc) from sampled process
RSS. RSS sampling uses /proc/self/statm on Linux; it reports null elsewhere
rather than silently substituting a different metric.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import tempfile
import time
import tracemalloc

from prototype.zpcm_memory import ZPCMMemory


def current_rss_bytes() -> int | None:
    statm = Path("/proc/self/statm")
    if not statm.exists():
        return None
    try:
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--page-size", type=int, default=128)
    parser.add_argument("--payload-bytes", type=int, default=256)
    args = parser.parse_args()
    if args.events < 1 or not 1 <= args.page_size <= 4096 or args.payload_bytes < 0:
        parser.error("events must be positive, page-size in [1,4096], payload-bytes non-negative")

    payload_text = "x" * args.payload_bytes
    with tempfile.TemporaryDirectory(prefix="zpcm-memory-bench-") as temp:
        memory = ZPCMMemory(Path(temp) / "bench.sqlite3")
        try:
            sequence = 0
            for index in range(args.events):
                receipt = memory.append_domain_event(
                    event_type="benchmark_semantic_unit",
                    event_id=f"bench:{index}",
                    scope="benchmark",
                    payload={"record_id": f"record:{index}", "payload": payload_text},
                    expected_sequence=sequence,
                )
                sequence = receipt["sequence"]

            gc.collect()
            rss_before = current_rss_bytes()
            tracemalloc.start()
            python_before, _ = tracemalloc.get_traced_memory()
            tracemalloc.reset_peak()
            rss_peak = rss_before
            count = 0
            started = time.perf_counter()
            for event in memory.iter_domain_events(
                event_type="benchmark_semantic_unit",
                scope="benchmark",
                page_size=args.page_size,
            ):
                # Touch decoded data so the benchmark includes JSON payloads.
                count += len(event["payload"]["payload"])
                rss_now = current_rss_bytes()
                if rss_now is not None:
                    rss_peak = rss_now if rss_peak is None else max(rss_peak, rss_now)
            elapsed = time.perf_counter() - started
            python_after, python_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            print(json.dumps({
                "events_requested": args.events,
                "events_read": args.events if count == args.events * args.payload_bytes else None,
                "page_size": args.page_size,
                "payload_bytes_per_event": args.payload_bytes,
                "elapsed_seconds": round(elapsed, 6),
                "python_tracemalloc_peak_delta_bytes": max(0, python_peak - python_before),
                "rss_before_iteration_bytes": rss_before,
                "rss_peak_during_iteration_bytes": rss_peak,
                "rss_peak_delta_bytes": (
                    max(0, rss_peak - rss_before)
                    if rss_peak is not None and rss_before is not None else None
                ),
                "rss_sampling": "/proc/self/statm sampled per event" if rss_before is not None else "unavailable",
                "interpretation": (
                    "Reader memory should scale primarily with page_size and payload size, "
                    "not total event count. This benchmark does not measure model KV cache."
                ),
            }, ensure_ascii=False, indent=2))
        finally:
            memory.close()


if __name__ == "__main__":
    main()
