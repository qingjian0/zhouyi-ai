"""Matched sample-efficiency curves for symbolic and trainable relation discovery.

For each teacher family, both methods receive the same deterministic subset of
training states at each support size. Development and locked states remain fixed.
This measures within-family sample efficiency, not cross-family zero-shot transfer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, evaluate,
)
from prototype.cpg_ei_mixed_operator_discovery import run_discovery_benchmark


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _summarize_trainable(rows: list[dict]) -> dict[str, float]:
    if not rows:
        return {"families": 0}
    return {
        "families": len(rows),
        "mean_training_bit_accuracy": _mean([
            row["training"]["bit_accuracy"] for row in rows
        ]),
        "mean_development_bit_accuracy": _mean([
            row["development"]["bit_accuracy"] for row in rows
        ]),
        "mean_locked_bit_accuracy": _mean([
            row["locked"]["bit_accuracy"] for row in rows
        ]),
        "mean_locked_exact_state_accuracy": _mean([
            row["locked"]["exact_state_accuracy"] for row in rows
        ]),
        "families_with_decreased_loss": sum(row["loss_decreased"] for row in rows),
    }


def run_sample_efficiency_comparison(
    corpus: dict, *, support_sizes: Sequence[int] = (16, 32, 64, 128),
    epochs: int = 120, learning_rate: float = 0.1, l2: float = 1e-4,
) -> dict[str, Any]:
    sizes = tuple(support_sizes)
    if (not sizes or any(isinstance(k, bool) or not isinstance(k, int) or k < 1
                         for k in sizes)
            or tuple(sorted(set(sizes))) != sizes):
        raise ValueError("support_sizes must be unique, strictly increasing positive integers")

    manifest = corpus["manifest"]
    input_dim, output_dim = manifest["input_dim"], manifest["output_dim"]
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)
    min_train_count = min(
        sum(row["state_split"] == "train" for row in rows)
        for rows in rows_by_family.values()
    )
    if sizes[-1] > min_train_count:
        raise ValueError("largest support size exceeds available train states per family")

    per_size: dict[str, Any] = {}
    for support_size in sizes:
        trainable_family_results = []
        selected_states: dict[str, set[tuple[int, ...]]] = {}
        for family_id in sorted(rows_by_family):
            family_rows = rows_by_family[family_id]
            train_rows = [
                row for row in family_rows if row["state_split"] == "train"
            ]
            digest_seed = int.from_bytes(
                hashlib.sha256(family_id.encode("utf-8")).digest()[:8], "big"
            )
            rng = random.Random(manifest["seed"] + digest_seed)
            selected_rows = rng.sample(train_rows, support_size)
            selected_states[family_id] = {
                tuple(row["state"]) for row in selected_rows
            }
            examples = {
                split: [
                    TransitionExample(tuple(row["state"]), tuple(row["target"]))
                    for row in family_rows
                    if row["state_split"] == split
                    and (split != "train" or tuple(row["state"]) in selected_states[family_id])
                ]
                for split in ("train", "development", "locked")
            }
            model = RelationalTransitionModel.create(
                input_dim=input_dim, output_dim=output_dim,
                min_arity=1, max_arity=input_dim,
            )
            losses = model.train(
                examples["train"], epochs=epochs,
                learning_rate=learning_rate, l2=l2,
            )
            trainable_family_results.append({
                "family_id": family_id,
                "family_split": family_rows[0]["family_split"],
                "training": evaluate(model, examples["train"]),
                "development": evaluate(model, examples["development"]),
                "locked": evaluate(model, examples["locked"]),
                "initial_train_loss": losses[0],
                "final_train_loss": losses[-1],
                "loss_decreased": losses[-1] < losses[0],
            })

        sampled_corpus = {
            **corpus,
            "rows": [
                {
                    **row,
                    "state_split": (
                        "unused"
                        if row["state_split"] == "train"
                        and tuple(row["state"]) not in selected_states[row["family_id"]]
                        else row["state_split"]
                    ),
                }
                for row in corpus["rows"]
            ],
        }
        symbolic = run_discovery_benchmark(sampled_corpus)
        trainable_by_family_split = {
            split: _summarize_trainable([
                row for row in trainable_family_results
                if row["family_split"] == split
            ])
            for split in ("train", "development", "locked")
        }
        per_size[str(support_size)] = {
            "support_states_per_family": support_size,
            "trainable": {
                "overall": _summarize_trainable(trainable_family_results),
                "family_split_results": trainable_by_family_split,
            },
            "symbolic": {
                "family_split_results": symbolic["family_split_results"],
                "candidate_hypothesis_count": symbolic["candidate_hypothesis_count"],
                "candidate_truth_function_count": symbolic["candidate_truth_function_count"],
                "candidate_structural_alias_count": symbolic["candidate_structural_alias_count"],
            },
        }

    return {
        "benchmark_id": "zhouyi-cpg-ei-sample-efficiency-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "corpus": {
            "families": manifest["family_count"],
            "rows": manifest["row_count"],
            "input_dim": input_dim,
            "output_dim": output_dim,
            "state_split_per_family": manifest["state_split_per_family"],
            "family_split_counts": manifest["family_split_counts"],
        },
        "support_sizes": list(sizes),
        "training": {
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
            "model": "multi-output logistic regression over complete Boolean monomial basis",
            "sampling": "deterministic uniform sample without replacement within each family's train partition",
        },
        "evaluation_protocol": (
            "At each support size, both baselines use the same per-family training "
            "states. Development and locked partitions are unchanged. Family split "
            "labels are reporting strata only; this is within-family adaptation, "
            "not cross-family zero-shot transfer."
        ),
        "results_by_support_size": per_size,
        "claim_boundary": (
            "Synthetic Boolean sample-efficiency benchmark. It does not establish "
            "natural-language reasoning, open-world relation induction, or "
            "Transformer superiority."
        ),
    }


def write_json_report(report: dict[str, Any], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--support-sizes", type=int, nargs="+", default=[16, 32, 64, 128])
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    report = run_sample_efficiency_comparison(
        corpus, support_sizes=args.support_sizes, epochs=args.epochs,
        learning_rate=args.learning_rate, l2=args.l2,
    )
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
