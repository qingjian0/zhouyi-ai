"""Whole-document Hugging Face tokenizer oracle benchmark for large corpora.

This intentionally buffers the full document. It provides a canonical exact
count and resource baseline, not a bounded-memory streaming implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from prototype.memory_budget import MemoryMeasurementUnavailable, ProcessMemoryMeasurement


class TokenizerBenchmarkError(RuntimeError):
    """Raised when a source or tokenizer cannot be benchmarked safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def benchmark_whole_document(
    source_path: str | Path,
    tokenizer_json: str | Path,
    *,
    tokenizer_id: str,
    expected_tokens: int | None = 1_000_000,
) -> dict:
    source = Path(source_path)
    asset = Path(tokenizer_json)
    if not source.is_file():
        raise TokenizerBenchmarkError(f"source file does not exist: {source}")
    if not asset.is_file():
        raise TokenizerBenchmarkError(f"tokenizer JSON does not exist: {asset}")
    if not isinstance(tokenizer_id, str) or not tokenizer_id.strip():
        raise TokenizerBenchmarkError("tokenizer_id must be a stable non-empty identity")
    if expected_tokens is not None and (
        isinstance(expected_tokens, bool) or not isinstance(expected_tokens, int)
        or expected_tokens < 0
    ):
        raise TokenizerBenchmarkError("expected_tokens must be a non-negative integer or None")

    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise TokenizerBenchmarkError(
            "Install the optional dependency: pip install 'zhouyi-ai-cpg-ei[tokenizers]'"
        ) from exc

    source_stat_before = source.stat()
    asset_stat_before = asset.stat()
    started = time.perf_counter()
    rss_report = None
    try:
        with ProcessMemoryMeasurement() as measurement:
            raw = source.read_bytes()
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise TokenizerBenchmarkError("source must be valid UTF-8") from exc
            tokenizer = Tokenizer.from_file(str(asset))
            token_ids = tokenizer.encode(text).ids
        rss_report = measurement.report
    except MemoryMeasurementUnavailable:
        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise TokenizerBenchmarkError("source must be valid UTF-8") from exc
        tokenizer = Tokenizer.from_file(str(asset))
        token_ids = tokenizer.encode(text).ids

    elapsed = max(time.perf_counter() - started, 1e-12)
    source_stat_after = source.stat()
    asset_stat_after = asset.stat()
    if (source_stat_before.st_size, source_stat_before.st_mtime_ns) != (
        source_stat_after.st_size, source_stat_after.st_mtime_ns
    ):
        raise TokenizerBenchmarkError("source changed during benchmark")
    if (asset_stat_before.st_size, asset_stat_before.st_mtime_ns) != (
        asset_stat_after.st_size, asset_stat_after.st_mtime_ns
    ):
        raise TokenizerBenchmarkError("tokenizer asset changed during benchmark")

    count = len(token_ids)
    report = {
        "schema_version": 1,
        "benchmark": "huggingface_whole_document_tokenizer_oracle",
        "claim_boundary": (
            "Canonical whole-document tokenizer count only; full input and token IDs "
            "are buffered; not bounded-memory streaming, not a phone result unless "
            "run on the target phone, and not a production tokenizer certification."
        ),
        "tokenizer_id": tokenizer_id,
        "tokenizer_asset_sha256": _sha256(asset),
        "tokenizer_asset_bytes": asset_stat_after.st_size,
        "source_sha256": _sha256(source),
        "source_bytes": source_stat_after.st_size,
        "source_characters": len(text),
        "token_count": count,
        "expected_token_count": expected_tokens,
        "expected_token_count_match": (
            None if expected_tokens is None else count == expected_tokens
        ),
        "elapsed_seconds": elapsed,
        "tokens_per_second": count / elapsed,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "process_rss_measurement": (
            {
                "source": "sampled_process_rss",
                "baseline_rss_bytes": rss_report.baseline_rss_bytes,
                "sampled_peak_rss_bytes": rss_report.sampled_peak_rss_bytes,
                "peak_increment_bytes": rss_report.peak_increment_bytes,
                "final_increment_bytes": rss_report.final_increment_bytes,
                "sample_count": rss_report.sample_count,
                "interval_seconds": rss_report.interval_seconds,
            }
            if rss_report is not None else {"source": "unavailable"}
        ),
        "buffered_full_text_bytes": len(raw),
        "buffered_token_id_count": count,
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("tokenizer_json", type=Path)
    parser.add_argument("--tokenizer-id", required=True)
    parser.add_argument("--expected-tokens", type=int, default=1_000_000)
    parser.add_argument("--allow-any-count", action="store_true")
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    report = benchmark_whole_document(
        args.source, args.tokenizer_json,
        tokenizer_id=args.tokenizer_id,
        expected_tokens=None if args.allow_any_count else args.expected_tokens,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output == "-":
        print(rendered)
    else:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["expected_token_count_match"] is not False else 3


if __name__ == "__main__":
    raise SystemExit(main())
