"""Independent-seed evaluation and controls for mixed-operator CPG-EI.

Each seed creates fresh teacher families and state partitions. Full polynomial,
unary-only, and train-derived majority baselines are evaluated side by side.
Locked partitions are report-only.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Sequence

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, evaluate,
)
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


def _examples(rows: list[dict], split: str) -> list[TransitionExample]:
    return [
        TransitionExample(tuple(row["state"]), tuple(row["target"]))
        for row in rows if row["state_split"] == split
    ]


def _family_average(metrics: list[dict]) -> dict[str, float]:
    if not metrics:
        raise ValueError("cannot summarize an empty family set")
    return {
        "families": len(metrics),
        "mean_bit_accuracy": statistics.mean(x["bit_accuracy"] for x in metrics),
        "mean_exact_state_accuracy": statistics.mean(
            x["exact_state_accuracy"] for x in metrics
        ),
    }


def _majority_family_metrics(rows: list[dict], output_dim: int) -> dict[str, dict]:
    train = _examples(rows, "train")
    if not train:
        raise ValueError("majority baseline requires training examples")
    predictions = []
    for output_index in range(output_dim):
        positive = sum(example.target[output_index] for example in train)
        predictions.append(int(positive * 2 > len(train)))
    result = {}
    for split in ("development", "locked"):
        held_out = _examples(rows, split)
        if not held_out:
            raise ValueError(f"{split} examples must not be empty")
        bit_correct = sum(
            int(predictions[i] == example.target[i])
            for example in held_out for i in range(output_dim)
        )
        exact_correct = sum(
            int(tuple(predictions) == example.target) for example in held_out
        )
        result[split] = {
            "examples": float(len(held_out)),
            "bit_accuracy": bit_correct / (len(held_out) * output_dim),
            "exact_state_accuracy": exact_correct / len(held_out),
        }
    return result


def _unary_family_metrics(
    rows: list[dict], *, input_dim: int, output_dim: int,
    epochs: int, learning_rate: float, l2: float,
) -> dict[str, dict]:
    train = _examples(rows, "train")
    model = RelationalTransitionModel.create(
        input_dim=input_dim, output_dim=output_dim,
        min_arity=1, max_arity=1,
    )
    losses = model.train(
        train, epochs=epochs, learning_rate=learning_rate, l2=l2,
    )
    return {
        "development": evaluate(model, _examples(rows, "development")),
        "locked": evaluate(model, _examples(rows, "locked")),
        "initial_train_loss": losses[0],
        "final_train_loss": losses[-1],
        "loss_decreased": losses[-1] < losses[0],
    }


def run_multiseed_benchmark(
    *, seeds: Sequence[int] = (20261114, 20261115, 20261116, 20261117, 20261118),
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
            family_count=family_count, input_dim=input_dim,
            output_dim=output_dim, seed=seed,
        )
        full = run_trainable_baseline(
            corpus, epochs=epochs, learning_rate=learning_rate, l2=l2,
        )
        rows_by_family: dict[str, list[dict]] = {}
        for row in corpus["rows"]:
            rows_by_family.setdefault(row["family_id"], []).append(row)

        unary_results = []
        majority_results = []
        for family_id in sorted(rows_by_family):
            rows = rows_by_family[family_id]
            unary_results.append(_unary_family_metrics(
                rows, input_dim=input_dim, output_dim=output_dim,
                epochs=epochs, learning_rate=learning_rate, l2=l2,
            ))
            majority_results.append(_majority_family_metrics(rows, output_dim))

        seed_results.append({
            "seed": seed,
            "dataset_id": full["dataset_id"],
            "corpus_sha256": full["corpus_sha256"],
            "families": corpus["manifest"]["family_count"],
            "rows": corpus["manifest"]["row_count"],
            "full_polynomial": {
                "development": full["development_summary"],
                "locked": full["locked_summary"],
                "all_families_loss_decreased": full["all_families_loss_decreased"],
            },
            "unary_only": {
                "development": _family_average([x["development"] for x in unary_results]),
                "locked": _family_average([x["locked"] for x in unary_results]),
                "all_families_loss_decreased": all(x["loss_decreased"] for x in unary_results),
            },
            "train_majority": {
                "development": _family_average([x["development"] for x in majority_results]),
                "locked": _family_average([x["locked"] for x in majority_results]),
            },
        })

    variants = ("full_polynomial", "unary_only", "train_majority")

    def aggregate(variant: str, split: str, metric: str) -> dict[str, float]:
        values = [float(item[variant][split][metric]) for item in seed_results]
        return {
            "mean_across_seeds": statistics.mean(values),
            "sample_std_across_seeds": statistics.stdev(values),
            "min_across_seeds": min(values),
            "max_across_seeds": max(values),
        }

    model_results = {}
    for variant in variants:
        model_results[variant] = {
            "development": {
                "bit_accuracy": aggregate(variant, "development", "mean_bit_accuracy"),
                "exact_state_accuracy": aggregate(
                    variant, "development", "mean_exact_state_accuracy"
                ),
            },
            "locked_report_only": {
                "bit_accuracy": aggregate(variant, "locked", "mean_bit_accuracy"),
                "exact_state_accuracy": aggregate(
                    variant, "locked", "mean_exact_state_accuracy"
                ),
            },
        }

    full_locked = model_results["full_polynomial"]["locked_report_only"]
    comparisons = {}
    for baseline in ("unary_only", "train_majority"):
        base_locked = model_results[baseline]["locked_report_only"]
        comparisons[f"full_minus_{baseline}_locked_report_only"] = {
            metric: (
                full_locked[metric]["mean_across_seeds"]
                - base_locked[metric]["mean_across_seeds"]
            )
            for metric in ("bit_accuracy", "exact_state_accuracy")
        }

    return {
        "benchmark_id": "zhouyi-cpg-ei-mixed-operator-multiseed-v2",
        "protocol": (
            "Fresh deterministic teacher families and state partitions per seed. "
            "Full polynomial and unary-only models are fitted independently per "
            "family with the same optimizer settings. Majority predictions are "
            "estimated from each family's training partition only. Development "
            "and locked partitions are evaluation-only; locked metrics never "
            "select hyperparameters."
        ),
        "model_config": {
            "input_dim": input_dim,
            "output_dim": output_dim,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
            "full_basis": "complete Boolean monomials, arity 1 through input_dim",
            "unary_control": "Boolean monomials with arity exactly 1",
            "majority_control": "per-output training-set majority; ties predict 0",
        },
        "dataset_summary": {
            "independent_seeds": len(selected_seeds),
            "families_per_seed": family_count,
            "total_independent_teacher_families": sum(x["families"] for x in seed_results),
            "rows_per_seed": family_count * (2 ** input_dim),
            "total_rows_across_seeds": sum(x["rows"] for x in seed_results),
            "corpus_sha256_by_seed": {
                str(item["seed"]): item["corpus_sha256"] for item in seed_results
            },
        },
        "model_results": model_results,
        "locked_comparisons_report_only": comparisons,
        "all_full_polynomial_families_loss_decreased": all(
            item["full_polynomial"]["all_families_loss_decreased"] for item in seed_results
        ),
        "all_unary_only_families_loss_decreased": all(
            item["unary_only"]["all_families_loss_decreased"] for item in seed_results
        ),
        "seed_results": seed_results,
        "claim_boundary": (
            "A small independent-seed comparison of per-family supervised fitting "
            "on synthetic mixed Boolean operators. It compares a fixed exhaustive "
            "monomial basis against unary-only and training-majority controls. It "
            "is not cross-family transfer, zero-shot learning, open-world relation "
            "discovery, natural-language reasoning, or evidence of superiority "
            "to Transformer models."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="20261114,20261115,20261116,20261117,20261118")
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
