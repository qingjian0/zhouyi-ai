"""Matched comparison of symbolic discovery and trainable polynomial baselines.

Both methods receive the exact same generated families and per-family train,
development, and locked states. This is within-family adaptation, not zero-shot
cross-family transfer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_discovery import run_discovery_benchmark
from prototype.cpg_ei_mixed_operator_trainable_baseline import run_trainable_baseline


def _trainable_split_summary(rows: list[dict]) -> dict[str, float]:
    if not rows:
        return {"families": 0}
    return {
        "families": len(rows),
        "mean_locked_bit_accuracy": sum(
            row["locked"]["bit_accuracy"] for row in rows
        ) / len(rows),
        "mean_locked_exact_state_accuracy": sum(
            row["locked"]["exact_state_accuracy"] for row in rows
        ) / len(rows),
        "mean_development_bit_accuracy": sum(
            row["development"]["bit_accuracy"] for row in rows
        ) / len(rows),
        "mean_training_bit_accuracy": sum(
            row["training"]["bit_accuracy"] for row in rows
        ) / len(rows),
        "families_with_decreased_loss": sum(
            row["loss_decreased"] for row in rows
        ),
    }


def run_matched_comparison(
    corpus: dict, *, epochs: int = 120,
    learning_rate: float = 0.1, l2: float = 1e-4,
) -> dict[str, Any]:
    symbolic = run_discovery_benchmark(corpus)
    trainable = run_trainable_baseline(
        corpus, epochs=epochs, learning_rate=learning_rate, l2=l2,
    )
    if symbolic["corpus_sha256"] != trainable["corpus_sha256"]:
        raise AssertionError("baselines did not evaluate the same corpus")

    trainable_by_split = {}
    for split in ("train", "development", "locked"):
        trainable_by_split[split] = _trainable_split_summary([
            row for row in trainable["family_results"]
            if row["family_split"] == split
        ])

    return {
        "benchmark_id": "zhouyi-cpg-ei-matched-baseline-comparison-v1",
        "dataset_id": corpus["manifest"]["dataset_id"],
        "corpus_sha256": corpus["manifest"]["corpus_sha256"],
        "corpus": {
            "families": corpus["manifest"]["family_count"],
            "rows": corpus["manifest"]["row_count"],
            "input_dim": corpus["manifest"]["input_dim"],
            "output_dim": corpus["manifest"]["output_dim"],
            "state_split_per_family": corpus["manifest"]["state_split_per_family"],
            "family_split_counts": corpus["manifest"]["family_split_counts"],
        },
        "protocol": (
            "Matched per-family adaptation: both baselines receive identical "
            "train/development/locked states for each family. The family_split "
            "field is a reporting stratum only; it is not a zero-shot or "
            "cross-family transfer evaluation."
        ),
        "symbolic": {
            "candidate_hypothesis_count": symbolic["candidate_hypothesis_count"],
            "candidate_truth_function_count": symbolic["candidate_truth_function_count"],
            "candidate_structural_alias_count": symbolic["candidate_structural_alias_count"],
            "family_split_results": symbolic["family_split_results"],
        },
        "trainable": {
            "model": trainable["model"],
            "all_families_loss_decreased": trainable["all_families_loss_decreased"],
            "family_split_results": trainable_by_split,
        },
        "metric_interpretation": {
            "symbolic_locked_bit_accuracy": (
                "Bitwise prediction accuracy on locked states after finite-rule "
                "search; not an operator-identification metric."
            ),
            "symbolic_full_truth_table_exact_rate": (
                "Fraction of outputs whose selected rule matches the teacher "
                "function over every possible input state."
            ),
            "symbolic_operator_recovery_rate": (
                "Exact operator-label recovery; can be lower than function "
                "recovery when distinct operator descriptions are functionally aliased."
            ),
            "trainable_locked_bit_accuracy": (
                "Bitwise prediction accuracy of the fitted polynomial logistic model."
            ),
            "trainable_locked_exact_state_accuracy": (
                "Fraction of locked input states for which all output bits are correct."
            ),
        },
        "claim_boundary": (
            "Synthetic Boolean benchmark comparison only. Neither result "
            "establishes natural-language reasoning, open-world relation "
            "induction, or superiority to Transformer models."
        ),
    }


def write_json_report(report: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    report = run_matched_comparison(
        corpus, epochs=args.epochs,
        learning_rate=args.learning_rate, l2=args.l2,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
