"""Per-family polynomial learner with development-loss early stopping.

The model is fitted independently per family. Development data selects the
checkpoint; locked states are report-only and never influence training or
checkpoint selection.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, evaluate,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def _binary_cross_entropy(
    model: RelationalTransitionModel,
    examples: list[TransitionExample],
) -> float:
    if not examples:
        raise ValueError("development examples must not be empty")
    total = 0.0
    for row in examples:
        probabilities = model.predict_proba(row.state)
        for probability, label in zip(probabilities, row.target):
            p = min(max(probability, 1e-12), 1.0 - 1e-12)
            total -= label * math.log(p) + (1 - label) * math.log1p(-p)
    return total / (len(examples) * model.output_dim)


def fit_with_early_stopping(
    model: RelationalTransitionModel,
    training: list[TransitionExample],
    development: list[TransitionExample],
    *,
    max_epochs: int = 120,
    patience: int = 12,
    min_delta: float = 1e-5,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
) -> dict[str, Any]:
    if not training or not development:
        raise ValueError("training and development examples must both be non-empty")
    numeric = (min_delta, learning_rate, l2)
    if (isinstance(max_epochs, bool) or not isinstance(max_epochs, int) or max_epochs < 1
            or isinstance(patience, bool) or not isinstance(patience, int) or patience < 1
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in numeric)
            or min_delta < 0 or learning_rate <= 0 or l2 < 0):
        raise ValueError("invalid early-stopping or optimizer configuration")

    best_loss = _binary_cross_entropy(model, development)
    best_epoch = 0
    best_weights = copy.deepcopy(model.weights)
    epochs_without_improvement = 0
    train_losses = []
    epochs_run = 0

    for epoch in range(1, max_epochs + 1):
        losses = model.train(
            training, epochs=1, learning_rate=learning_rate, l2=l2
        )
        train_losses.append(losses[-1])
        epochs_run = epoch
        development_loss = _binary_cross_entropy(model, development)
        if development_loss < best_loss - min_delta:
            best_loss = development_loss
            best_epoch = epoch
            best_weights = copy.deepcopy(model.weights)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    model.weights = best_weights
    weights_digest = hashlib.sha256(
        json.dumps(model.weights, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "epochs_run": epochs_run,
        "best_epoch": best_epoch,
        "best_development_log_loss": best_loss,
        "initial_train_loss": train_losses[0] if train_losses else None,
        "last_train_loss_before_restore": train_losses[-1] if train_losses else None,
        "stopped_early": epochs_run < max_epochs,
        "selected_weights_sha256": weights_digest,
    }


def run_early_stopping_baseline(
    corpus: dict, *, max_epochs: int = 120, patience: int = 12,
    min_delta: float = 1e-5, learning_rate: float = 0.1, l2: float = 1e-4,
) -> dict[str, Any]:
    manifest = corpus["manifest"]
    input_dim, output_dim = manifest["input_dim"], manifest["output_dim"]
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in corpus["rows"]:
        rows_by_family[row["family_id"]].append(row)

    family_results = []
    for family_id in sorted(rows_by_family):
        rows = rows_by_family[family_id]
        examples = {
            split: [
                TransitionExample(tuple(row["state"]), tuple(row["target"]))
                for row in rows if row["state_split"] == split
            ]
            for split in ("train", "development", "locked")
        }
        model = RelationalTransitionModel.create(
            input_dim=input_dim, output_dim=output_dim,
            min_arity=1, max_arity=input_dim,
        )
        fit = fit_with_early_stopping(
            model, examples["train"], examples["development"],
            max_epochs=max_epochs, patience=patience, min_delta=min_delta,
            learning_rate=learning_rate, l2=l2,
        )
        family_results.append({
            "family_id": family_id,
            "family_split": rows[0]["family_split"],
            "training": evaluate(model, examples["train"]),
            "development": evaluate(model, examples["development"]),
            "locked": evaluate(model, examples["locked"]),
            **fit,
        })

    def summarize(selected: list[dict], split: str) -> dict[str, float]:
        if not selected:
            return {"families": 0}
        return {
            "families": len(selected),
            "mean_bit_accuracy": sum(
                row[split]["bit_accuracy"] for row in selected
            ) / len(selected),
            "mean_exact_state_accuracy": sum(
                row[split]["exact_state_accuracy"] for row in selected
            ) / len(selected),
            "mean_best_epoch": sum(row["best_epoch"] for row in selected) / len(selected),
            "mean_epochs_run": sum(row["epochs_run"] for row in selected) / len(selected),
            "early_stopped_families": sum(row["stopped_early"] for row in selected),
        }

    return {
        "benchmark_id": "zhouyi-cpg-ei-early-stopping-baseline-v1",
        "dataset_id": manifest["dataset_id"],
        "corpus_sha256": manifest["corpus_sha256"],
        "model": {
            "type": "multi-output logistic regression over complete Boolean monomial basis",
            "input_dim": input_dim,
            "output_dim": output_dim,
            "max_epochs": max_epochs,
            "patience": patience,
            "min_delta": min_delta,
            "learning_rate": learning_rate,
            "l2": l2,
            "checkpoint_selection": "minimum development binary cross-entropy",
        },
        "evaluation_protocol": (
            "Independent per-family fitting. Training states update weights; "
            "development log loss selects and restores the checkpoint; locked "
            "states are report-only. Not cross-family meta-learning or zero-shot transfer."
        ),
        "training_summary": summarize(family_results, "training"),
        "development_summary": summarize(family_results, "development"),
        "locked_summary": summarize(family_results, "locked"),
        "family_split_results": {
            split: {
                metric: summarize([
                    row for row in family_results if row["family_split"] == split
                ], metric)
                for metric in ("training", "development", "locked")
            }
            for split in ("train", "development", "locked")
        },
        "family_results": family_results,
        "claim_boundary": (
            "Early-stopped trainable linear classifier over a fixed exhaustive "
            "Boolean monomial basis. Does not learn the feature basis or establish "
            "open-world relation induction or natural-language reasoning."
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
    parser.add_argument("--max-epochs", type=int, default=120)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    report = run_early_stopping_baseline(
        corpus, max_epochs=args.max_epochs, patience=args.patience,
        min_delta=args.min_delta, learning_rate=args.learning_rate, l2=args.l2,
    )
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
