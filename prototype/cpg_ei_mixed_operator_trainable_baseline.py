"""Trainable polynomial-feature baseline for mixed Boolean relations.

This baseline fits one multi-output logistic model per teacher family using
Boolean monomial features. It is trainable, but it is not a deep neural model,
an explicit operator classifier, or a zero-shot family-transfer experiment.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, evaluate,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def run_trainable_baseline(
    corpus: dict, *, epochs: int = 120, learning_rate: float = 0.1,
    l2: float = 1e-4,
) -> dict[str, Any]:
    manifest = corpus["manifest"]
    input_dim = manifest["input_dim"]
    output_dim = manifest["output_dim"]
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)

    family_results = []
    for family_id in sorted(rows_by_family):
        rows = rows_by_family[family_id]
        split_rows = {
            split: [row for row in rows if row["state_split"] == split]
            for split in ("train", "development", "locked")
        }
        examples = {
            split: [
                TransitionExample(tuple(row["state"]), tuple(row["target"]))
                for row in selected
            ]
            for split, selected in split_rows.items()
        }
        model = RelationalTransitionModel.create(
            input_dim=input_dim, output_dim=output_dim,
            min_arity=1, max_arity=input_dim,
        )
        losses = model.train(
            examples["train"], epochs=epochs,
            learning_rate=learning_rate, l2=l2,
        )
        family_results.append({
            "family_id": family_id,
            "family_split": rows[0]["family_split"],
            "train_examples": len(examples["train"]),
            "development": evaluate(model, examples["development"]),
            "locked": evaluate(model, examples["locked"]),
            "initial_train_loss": losses[0],
            "final_train_loss": losses[-1],
            "loss_decreased": losses[-1] < losses[0],
        })

    def summarize(split: str) -> dict[str, float]:
        selected = [item[split] for item in family_results]
        if not selected:
            return {"families": 0}
        return {
            "families": len(selected),
            "mean_bit_accuracy": sum(x["bit_accuracy"] for x in selected) / len(selected),
            "mean_exact_state_accuracy": sum(
                x["exact_state_accuracy"] for x in selected
            ) / len(selected),
        }

    return {
        "benchmark_id": "zhouyi-cpg-ei-trainable-polynomial-baseline-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "model": {
            "type": "multi-output logistic regression over complete Boolean monomial basis",
            "input_dim": input_dim,
            "output_dim": output_dim,
            "min_arity": 1,
            "max_arity": input_dim,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "l2": l2,
            "initialization": "all-zero weights",
        },
        "evaluation_protocol": (
            "Independent per-family supervised fitting. Train states update model "
            "weights; development and locked states are evaluation-only. This is "
            "not cross-family meta-learning or zero-shot transfer."
        ),
        "development_summary": summarize("development"),
        "locked_summary": summarize("locked"),
        "all_families_loss_decreased": all(
            item["loss_decreased"] for item in family_results
        ),
        "family_results": family_results,
        "claim_boundary": (
            "A trainable linear classifier over a fixed exhaustive Boolean "
            "monomial basis. It does not learn the feature basis, explicitly "
            "classify operator semantics, establish open-world relation discovery, "
            "or demonstrate natural-language reasoning."
        ),
    }


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
    report = run_trainable_baseline(
        corpus, epochs=args.epochs,
        learning_rate=args.learning_rate, l2=args.l2,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({
        key: value for key, value in report.items()
        if key != "family_results"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
