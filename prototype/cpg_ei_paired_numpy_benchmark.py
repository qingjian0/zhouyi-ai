"""Paired same-run Python/NumPy benchmark for the symbolic-support hybrid."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import time
import tracemalloc
from pathlib import Path
from typing import Any

from prototype.cpg_ei_compute_accounted_hybrid import run_support_constrained_hybrid
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus

EXPECTED_CORPUS_SHA256 = "f56948816847a587c194931588027f97d99a4541644932b81f2df26e7b381c15"


def _measure_backend(corpus: dict, backend: str) -> tuple[dict[str, Any], float, int]:
    gc.collect()
    tracemalloc.start()
    baseline_current, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    started = time.perf_counter()
    report = run_support_constrained_hybrid(
        corpus,
        max_epochs=600,
        patience=30,
        min_delta=1e-5,
        learning_rate=0.1,
        l2=1e-4,
        optimizer_backend=backend,
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return report, elapsed, max(0, peak - baseline_current)


def _family_signature(report: dict) -> dict[str, dict]:
    return {
        family["family_id"]: {
            "prediction_sha256": family["prediction_sha256"],
            "feature_counts_by_output": family["feature_counts_by_output"],
            "best_epochs": [
                fit["best_epoch"] for fit in family["output_fits"]
            ],
            "weight_digests": [
                fit["selected_weights_sha256"] for fit in family["output_fits"]
            ],
        }
        for family in report["family_results"]
    }


def run_paired_benchmark() -> dict[str, Any]:
    corpus = generate_mixed_corpus(
        family_count=8, input_dim=8, output_dim=8, seed=20261114
    )
    digest = corpus["manifest"]["corpus_sha256"]
    if digest != EXPECTED_CORPUS_SHA256:
        raise AssertionError(f"fixed corpus digest changed: {digest}")

    # Same process, interpreter, runner, corpus object, and optimizer settings.
    # Python is run first, followed by NumPy. This is one paired measurement,
    # not a multi-run performance distribution.
    python_report, python_seconds, python_peak = _measure_backend(corpus, "python")
    python_signature = _family_signature(python_report)
    python_locked = python_report["locked_summary"]
    python_compute = python_report["compute_accounting"]
    python_features = python_report["feature_accounting"]
    del python_report
    gc.collect()

    numpy_report, numpy_seconds, numpy_peak = _measure_backend(corpus, "numpy")
    numpy_signature = _family_signature(numpy_report)
    numpy_locked = numpy_report["locked_summary"]
    numpy_compute = numpy_report["compute_accounting"]
    numpy_features = numpy_report["feature_accounting"]

    shared_families = sorted(set(python_signature) & set(numpy_signature))
    predictions_match = (
        len(shared_families) == len(python_signature) == len(numpy_signature)
        and all(
            python_signature[key]["prediction_sha256"]
            == numpy_signature[key]["prediction_sha256"]
            for key in shared_families
        )
    )
    features_match = all(
        python_signature[key]["feature_counts_by_output"]
        == numpy_signature[key]["feature_counts_by_output"]
        for key in shared_families
    )
    epoch_matches = sum(
        left == right
        for key in shared_families
        for left, right in zip(
            python_signature[key]["best_epochs"],
            numpy_signature[key]["best_epochs"],
        )
    )
    weight_digest_matches = sum(
        left == right
        for key in shared_families
        for left, right in zip(
            python_signature[key]["weight_digests"],
            numpy_signature[key]["weight_digests"],
        )
    )
    locked_metrics_match = python_locked == numpy_locked
    if not predictions_match or not features_match or not locked_metrics_match:
        raise AssertionError(
            "paired backend parity failed: predictions, features, or locked metrics differ"
        )

    try:
        import numpy as np
        numpy_version = np.__version__
    except ImportError as exc:  # pragma: no cover - benchmark requires NumPy
        raise RuntimeError("paired benchmark requires numpy>=1.26") from exc

    return {
        "benchmark_id": "zhouyi-cpg-ei-paired-numpy-hybrid-v1",
        "corpus_sha256": digest,
        "dataset": {
            "families": 8,
            "rows": len(corpus["rows"]),
            "input_dim": 8,
            "output_dim": 8,
            "seed": 20261114,
        },
        "optimizer": {
            "max_epochs": 600,
            "patience": 30,
            "min_delta": 1e-5,
            "learning_rate": 0.1,
            "l2": 1e-4,
            "initialization": "all-zero weights",
        },
        "measurement_protocol": {
            "runner": "same CI job and process",
            "corpus": "same in-memory corpus object and digest",
            "execution_order": ["python", "numpy"],
            "repetitions_per_backend": 1,
            "timing_scope": "run_support_constrained_hybrid only; corpus generation excluded",
            "memory_scope": "tracemalloc peak delta above each backend's pre-call Python heap",
            "interpretation": "paired single-run measurement; not a multi-run speedup distribution",
        },
        "methods": {
            "python": {
                "wall_seconds": python_seconds,
                "peak_traced_allocation_delta_bytes": python_peak,
                "locked_summary": python_locked,
                "feature_accounting": python_features,
                "compute_accounting": python_compute,
            },
            "numpy": {
                "wall_seconds": numpy_seconds,
                "peak_traced_allocation_delta_bytes": numpy_peak,
                "locked_summary": numpy_locked,
                "feature_accounting": numpy_features,
                "compute_accounting": numpy_compute,
            },
        },
        "parity": {
            "locked_metrics_identical": locked_metrics_match,
            "all_family_predictions_identical": predictions_match,
            "feature_bases_identical": features_match,
            "selected_epoch_matches": epoch_matches,
            "selected_epoch_comparisons": 64,
            "exact_weight_digest_matches": weight_digest_matches,
            "weight_digest_comparisons": 64,
        },
        "timing": {
            "python_over_numpy_speedup": (
                python_seconds / numpy_seconds if numpy_seconds else None
            ),
            "faster_backend": (
                "numpy" if numpy_seconds < python_seconds else "python"
            ),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": numpy_version,
        },
        "claim_boundary": (
            "Paired implementation-performance measurement on one fixed synthetic "
            "Boolean benchmark. It does not establish generalization, cross-family "
            "transfer, open-world relation induction, Yi-Xue understanding, causal "
            "discovery, natural-language reasoning, or Transformer superiority."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    report = run_paired_benchmark()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "corpus_sha256": report["corpus_sha256"],
        "methods": {
            key: {
                "wall_seconds": value["wall_seconds"],
                "locked_summary": value["locked_summary"],
            }
            for key, value in report["methods"].items()
        },
        "parity": report["parity"],
        "timing": report["timing"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
