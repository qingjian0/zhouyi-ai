"""Development-loss plateau scheduling for the per-family polynomial baseline.

The scheduler lowers the learning rate when development loss plateaus, restores
the best development checkpoint, and never reads locked labels for optimization.
This remains within-family supervised adaptation, not meta-learning.
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

from prototype.cpg_ei_early_stopping import _binary_cross_entropy
from prototype.cpg_ei_generic_learner import RelationalTransitionModel, TransitionExample, evaluate
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


def fit_with_plateau_schedule(model, training, development, *, max_epochs=600,
                              lr_patience=15, stop_patience=30, min_delta=1e-5,
                              learning_rate=0.1, lr_factor=0.5,
                              min_learning_rate=0.00625, l2=1e-4):
    if not training or not development:
        raise ValueError("training and development examples must both be non-empty")
    ints = (max_epochs, lr_patience, stop_patience)
    floats = (min_delta, learning_rate, lr_factor, min_learning_rate, l2)
    if (any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in ints)
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in floats)
            or min_delta < 0 or learning_rate <= 0 or not 0 < lr_factor < 1
            or min_learning_rate <= 0 or min_learning_rate > learning_rate or l2 < 0):
        raise ValueError("invalid scheduler or optimizer configuration")

    best_loss = _binary_cross_entropy(model, development)
    best_epoch, best_weights = 0, copy.deepcopy(model.weights)
    scheduler_best, plateau_epochs, epochs_at_min_lr = best_loss, 0, 0
    current_lr, reductions, epochs_run = learning_rate, 0, 0
    train_losses = []

    for epoch in range(1, max_epochs + 1):
        losses = model.train(training, epochs=1, learning_rate=current_lr, l2=l2)
        train_losses.append(losses[-1])
        epochs_run = epoch
        dev_loss = _binary_cross_entropy(model, development)
        if dev_loss < best_loss - min_delta:
            best_loss, best_epoch = dev_loss, epoch
            best_weights = copy.deepcopy(model.weights)
        if dev_loss < scheduler_best - min_delta:
            scheduler_best, plateau_epochs, epochs_at_min_lr = dev_loss, 0, 0
        else:
            plateau_epochs += 1
            if plateau_epochs >= lr_patience:
                next_lr = max(min_learning_rate, current_lr * lr_factor)
                if next_lr < current_lr:
                    current_lr, reductions = next_lr, reductions + 1
                plateau_epochs = 0
                if current_lr <= min_learning_rate:
                    epochs_at_min_lr += lr_patience
                else:
                    epochs_at_min_lr = 0
        if current_lr <= min_learning_rate and epochs_at_min_lr >= stop_patience:
            break

    model.weights = best_weights
    digest = hashlib.sha256(json.dumps(model.weights, separators=(",", ":")).encode()).hexdigest()
    return {"epochs_run": epochs_run, "best_epoch": best_epoch,
            "best_development_log_loss": best_loss,
            "initial_train_loss": train_losses[0], "last_train_loss_before_restore": train_losses[-1],
            "learning_rate_reductions": reductions, "final_learning_rate": current_lr,
            "stopped_early": epochs_run < max_epochs, "selected_weights_sha256": digest}


def run_adaptive_schedule(corpus, *, max_epochs=600, lr_patience=15, stop_patience=30,
                          min_delta=1e-5, learning_rate=0.1, lr_factor=0.5,
                          min_learning_rate=0.00625, l2=1e-4):
    manifest = corpus["manifest"]
    grouped = defaultdict(list)
    for row in corpus["rows"]:
        grouped[row["family_id"]].append(row)
    results = []
    for family_id in sorted(grouped):
        rows = grouped[family_id]
        examples = {split: [TransitionExample(tuple(r["state"]), tuple(r["target"]))
                            for r in rows if r["state_split"] == split]
                    for split in ("train", "development", "locked")}
        model = RelationalTransitionModel.create(manifest["input_dim"], manifest["output_dim"],
                                                 min_arity=1, max_arity=manifest["input_dim"])
        fit = fit_with_plateau_schedule(model, examples["train"], examples["development"],
            max_epochs=max_epochs, lr_patience=lr_patience, stop_patience=stop_patience,
            min_delta=min_delta, learning_rate=learning_rate, lr_factor=lr_factor,
            min_learning_rate=min_learning_rate, l2=l2)
        results.append({"family_id": family_id, "family_split": rows[0]["family_split"],
                        "training": evaluate(model, examples["train"]),
                        "development": evaluate(model, examples["development"]),
                        "locked": evaluate(model, examples["locked"]), **fit})

    def summarize(split, selected):
        if not selected:
            return {"families": 0}
        return {"families": len(selected),
            "mean_bit_accuracy": sum(r[split]["bit_accuracy"] for r in selected) / len(selected),
            "mean_exact_state_accuracy": sum(r[split]["exact_state_accuracy"] for r in selected) / len(selected),
            "mean_best_epoch": sum(r["best_epoch"] for r in selected) / len(selected),
            "mean_epochs_run": sum(r["epochs_run"] for r in selected) / len(selected),
            "mean_lr_reductions": sum(r["learning_rate_reductions"] for r in selected) / len(selected),
            "early_stopped_families": sum(r["stopped_early"] for r in selected)}
    return {"benchmark_id": "zhouyi-cpg-ei-adaptive-lr-schedule-v1",
        "dataset_id": manifest["dataset_id"], "corpus_sha256": manifest["corpus_sha256"],
        "model": {"type": "multi-output logistic regression over complete Boolean monomial basis",
            "max_epochs": max_epochs, "lr_patience": lr_patience, "stop_patience": stop_patience,
            "min_delta": min_delta, "initial_learning_rate": learning_rate,
            "lr_factor": lr_factor, "min_learning_rate": min_learning_rate, "l2": l2,
            "checkpoint_selection": "minimum development binary cross-entropy"},
        "evaluation_protocol": "Independent per-family fitting. Training updates weights; development loss drives scheduling and checkpoint selection; locked states are report-only. Not meta-learning or zero-shot transfer.",
        "training_summary": summarize("training", results),
        "development_summary": summarize("development", results),
        "locked_summary": summarize("locked", results), "family_results": results,
        "claim_boundary": "Synthetic Boolean benchmark of a plateau learning-rate scheduler; not open-world relation induction or natural-language reasoning."}


def write_json_report(report, path):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=8)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--max-epochs", type=int, default=600)
    parser.add_argument("--lr-patience", type=int, default=15)
    parser.add_argument("--stop-patience", type=int, default=30)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--lr-factor", type=float, default=0.5)
    parser.add_argument("--min-learning-rate", type=float, default=0.00625)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    corpus = generate_mixed_corpus(family_count=args.families, input_dim=args.input_dim,
                                   output_dim=args.output_dim, seed=args.seed)
    report = run_adaptive_schedule(corpus, max_epochs=args.max_epochs,
        lr_patience=args.lr_patience, stop_patience=args.stop_patience,
        min_delta=args.min_delta, learning_rate=args.learning_rate,
        lr_factor=args.lr_factor, min_learning_rate=args.min_learning_rate, l2=args.l2)
    if args.json:
        write_json_report(report, args.json)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
