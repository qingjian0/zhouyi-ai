"""Run the full fixed-seed symbolic-support hybrid with the optional NumPy backend."""
from __future__ import annotations

import json
import platform
import resource
import sys
import time
import tracemalloc
from pathlib import Path

from prototype.cpg_ei_compute_accounted_hybrid import run_support_constrained_hybrid
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


EXPECTED_CORPUS_SHA256 = "f56948816847a587c194931588027f97d99a4541644932b81f2df26e7b381c15"
PYTHON_REFERENCE = {
    "corpus_sha256": EXPECTED_CORPUS_SHA256,
    "wall_seconds": 711.2501230579999,
    "locked_bit_accuracy": 0.900390625,
    "locked_exact_state_accuracy": 0.412109375,
    "feature_count_mean": 27.375,
    "optimizer_epochs_total": 33266,
    "backend": "python-reference-from-parent-pr-422",
}


def run_benchmark() -> dict:
    corpus = generate_mixed_corpus(
        family_count=8, input_dim=8, output_dim=8, seed=20261114
    )
    digest = corpus["manifest"]["corpus_sha256"]
    if digest != EXPECTED_CORPUS_SHA256:
        raise AssertionError(f"fixed corpus digest changed: {digest}")
    tracemalloc.start()
    started = time.perf_counter()
    report = run_support_constrained_hybrid(
        corpus, max_epochs=600, patience=30, min_delta=1e-5,
        learning_rate=0.1, l2=1e-4, optimizer_backend="numpy",
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report["acceleration_benchmark"] = {
        "reference_python_hybrid": PYTHON_REFERENCE,
        "numpy_wall_seconds": elapsed,
        "numpy_peak_traced_bytes": peak,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": __import__("numpy").__version__,
        },
        "comparison_policy": (
            "Same corpus digest and model protocol as parent PR #422. The Python "
            "wall time is a historical CI measurement, not a paired same-process "
            "timing; treat timing ratio as indicative only. Accuracy and feature "
            "counts are directly comparable on the identical locked split."
        ),
    }
    return report


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "corpus_sha256": report["corpus_sha256"],
        "locked_summary": report["locked_summary"],
        "compute_accounting": report["compute_accounting"],
        "acceleration_benchmark": report["acceleration_benchmark"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
