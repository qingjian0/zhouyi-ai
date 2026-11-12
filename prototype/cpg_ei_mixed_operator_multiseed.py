"""Independent-seed evaluation for the mixed-operator trainable baseline.

Each seed creates a fresh set of teacher families and state partitions. Metrics
are aggregated across independent corpus seeds; locked partitions are report-only.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Sequence

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_trainable_baseline import run_trainable_baseline


def _validate_seeds(seeds: Sequence[int]) -> tuple[int, ...]:
    normalized = tuple(seeds)
    if len(normalized) < 2:
        raise ValueError("at least two independent seeds are required")
    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in normalized):
        raise ValueError("seeds must be integers")
    if len(set(normalized)) != len(normalized):
        raise ValueError("seeds must be unique")
    return normalized


def run_multiseed_benchmark(
    *, seeds: Sequence[int] = (20261114, 20261115),
    family_count: int = 8,
    input_dim: int = 8,
    output_dim: int = 8,
    epochs: int = 120,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
) -> dict[str, Any]:
    selected_seeds = _validate_seeds(seeds)
    seed_results = []
    for seed in selected_seeds:
        corpus = generate_mixed_corpus(
            family_count=family_count,
            input_dim=input_dim,
            output_dim=output_dim,
            seed=seed,
        )
        report = run_trainable_baseline(
            corpus, epochs=epochs, learning_rate=learning_rate, l2=l2,
        )
        seed_results.append({
            "seed": seed,
            "dataset_id": report["dataset_id"],
            "corpus_sha256": report["corpus_sha256"],
            "families": corpus["manifest"]["family_count"],
            "rows": corpus["manifest"]["row_count"],
            "development": report["development_summary"],
            "locked": report["locked_summary"],
            "all_families_loss_decreased": report["all_families_loss_decreased"],
        })

    def aggregate(split: str, metric: str) -> dict[str, float]:
        values = [float(item[split][metric]) for item in seed_results]
        return {
            "mean_across_seeds": statistics.mean(values),
            "sample_std_across_seeds": statistics.stdev(values),
            "min_across_seeds": min(values),
            "max_across_seeds": max(values),
        }

    total_families = sum(item["families"] for item in seed_results)
    total_rows = sum(item["rows"] for item in seed_results)
    return {
        "benchmark_id": "zhouyi-cpg-ei-mixed-operator-multiseed-v1",
        "protocol": (
            "Fresh deterministic teacher families and state partitions per seed. "
            "Each family is fitted independently. Development and locked partitions "
            "are evaluation-only; locked metrics never select hyperparameters."
        ),
        "model_config": {
            "input_dim": input_dim,
            "output_dim": output_dim,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
            "basis": "complete Boolean monomials, arity 1 through input_dim",
        },
        "dataset_summary": {
            "independent_seeds": len(selected_seeds),
            "families_per_seed": family_count,
            "total_independent_teacher_families": total_families,
            "rows_per_seed": family_count * (2 ** input_dim),
            "total_rows_across_seeds": total_rows,
            "corpus_sha256_by_seed": {
                str(item["seed"]): item["corpus_sha256"] for item in seed_results
            },
        },
        "development_aggregation": {
            "mean_bit_accuracy": aggregate("development", "mean_bit_accuracy"),
            "mean_exact_state_accuracy": aggregate("development", "mean_exact_state_accuracy"),
        },
        "locked_aggregation_report_only": {
            "mean_bit_accuracy": aggregate("locked", "mean_bit_accuracy"),
            "mean_exact_state_accuracy": aggregate("locked", "mean_exact_state_accuracy"),
        },
        "all_families_loss_decreased": all(
            item["all_families_loss_decreased"] for item in seed_results
        ),
        "seed_results": seed_results,
        "claim_boundary": (
            "A small independent-seed replication of per-family supervised fitting "
            "on synthetic mixed Boolean operators. It is not cross-family transfer, "
            "zero-shot learning, open-world relation discovery, natural-language "
            "reasoning, or evidence of superiority to Transformer models."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="20261114,20261115")
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    try:
        seeds = tuple(int(value.strip()) for value in args.seeds.split(",") if value.strip())
    except ValueError as exc:
        parser.error(f"invalid --seeds: {exc}")
    report = run_multiseed_benchmark(
        seeds=seeds, family_count=args.families,
        input_dim=args.input_dim, output_dim=args.output_dim,
        epochs=args.epochs, learning_rate=args.learning_rate, l2=args.l2,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({
        key: value for key, value in report.items() if key != "seed_results"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
