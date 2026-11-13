"""Benchmark the NumPy vectorized early-stopping optimizer against its scalar reference."""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path
from typing import Any

from prototype.cpg_ei_early_stopping import (
    fit_with_early_stopping_scalar,
    fit_with_early_stopping_vectorized,
    run_early_stopping_baseline,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def _run_backend(
    corpus: dict,
    fit_function,
    *,
    max_epochs: int,
    patience: int,
    min_delta: float,
    learning_rate: float,
    l2: float,
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    report = run_early_stopping_baseline(
        corpus,
        max_epochs=max_epochs,
        patience=patience,
        min_delta=min_delta,
        learning_rate=learning_rate,
        l2=l2,
        fit_function=fit_function,
    )
    return report, time.perf_counter() - started


def run_optimizer_speed_comparison(
    *,
    family_count: int = 8,
    input_dim: int = 8,
    output_dim: int = 8,
    seed: int = 20261114,
    max_epochs: int = 600,
    patience: int = 30,
    min_delta: float = 1e-5,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
) -> dict[str, Any]:
    corpus = generate_mixed_corpus(
        family_count=family_count,
        input_dim=input_dim,
        output_dim=output_dim,
        seed=seed,
    )
    scalar, scalar_seconds = _run_backend(
        corpus,
        fit_with_early_stopping_scalar,
        max_epochs=max_epochs,
        patience=patience,
        min_delta=min_delta,
        learning_rate=learning_rate,
        l2=l2,
    )
    vectorized, vectorized_seconds = _run_backend(
        corpus,
        fit_with_early_stopping_vectorized,
        max_epochs=max_epochs,
        patience=patience,
        min_delta=min_delta,
        learning_rate=learning_rate,
        l2=l2,
    )

    metric_deltas = []
    best_epoch_matches = True
    dev_loss_deltas = []
    for left, right in zip(scalar["family_results"], vectorized["family_results"]):
        best_epoch_matches = best_epoch_matches and left["best_epoch"] == right["best_epoch"]
        dev_loss_deltas.append(abs(
            left["best_development_log_loss"] - right["best_development_log_loss"]
        ))
        for split in ("training", "development", "locked"):
            for metric in ("bit_accuracy", "exact_state_accuracy"):
                metric_deltas.append(abs(left[split][metric] - right[split][metric]))

    max_metric_delta = max(metric_deltas, default=0.0)
    max_dev_loss_delta = max(dev_loss_deltas, default=0.0)
    parity_passed = (
        best_epoch_matches
        and max_metric_delta == 0.0
        and max_dev_loss_delta <= 1e-8
    )
    speedup = scalar_seconds / vectorized_seconds if vectorized_seconds > 0 else None

    return {
        "benchmark_id": "zhouyi-cpg-ei-vectorized-optimizer-speed-v1",
        "dataset_id": corpus["manifest"]["dataset_id"],
        "corpus_sha256": corpus["manifest"]["corpus_sha256"],
        "dataset": {
            "seed": seed,
            "families": family_count,
            "rows": corpus["manifest"]["row_count"],
            "input_dim": input_dim,
            "output_dim": output_dim,
            "state_split_per_family": corpus["manifest"]["state_split_per_family"],
        },
        "optimizer_config": {
            "max_epochs": max_epochs,
            "patience": patience,
            "min_delta": min_delta,
            "learning_rate": learning_rate,
            "l2": l2,
            "initialization": "all-zero weights",
        },
        "scalar_reference": {
            "wall_seconds": scalar_seconds,
            "locked": scalar["locked_summary"],
            "mean_best_epoch": scalar["locked_summary"]["mean_best_epoch"],
            "mean_epochs_run": scalar["locked_summary"]["mean_epochs_run"],
            "early_stopped_families": scalar["locked_summary"]["early_stopped_families"],
        },
        "numpy_vectorized": {
            "wall_seconds": vectorized_seconds,
            "locked": vectorized["locked_summary"],
            "mean_best_epoch": vectorized["locked_summary"]["mean_best_epoch"],
            "mean_epochs_run": vectorized["locked_summary"]["mean_epochs_run"],
            "early_stopped_families": vectorized["locked_summary"]["early_stopped_families"],
        },
        "parity": {
            "passed": parity_passed,
            "best_epoch_matches_for_all_families": best_epoch_matches,
            "max_absolute_metric_delta": max_metric_delta,
            "max_absolute_best_development_loss_delta": max_dev_loss_delta,
            "metric_scope": "training/development/locked bit and exact-state accuracies",
            "locked_metrics_are_report_only": True,
        },
        "performance": {
            "speedup_scalar_over_vectorized": speedup,
            "wall_time_scope": "same corpus and optimizer settings; corpus generation excluded",
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "claim_boundary": (
            "This measures implementation speed and numerical agreement for the "
            "same per-family logistic learner on a finite synthetic Boolean corpus. "
            "It is not a model-quality or cross-family generalization claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--max-epochs", type=int, default=600)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run_optimizer_speed_comparison(
        family_count=args.families,
        input_dim=args.input_dim,
        output_dim=args.output_dim,
        seed=args.seed,
        max_epochs=args.max_epochs,
        patience=args.patience,
        min_delta=args.min_delta,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["parity"]["passed"]:
        raise SystemExit("vectorized optimizer did not meet numerical parity gates")


if __name__ == "__main__":
    main()
