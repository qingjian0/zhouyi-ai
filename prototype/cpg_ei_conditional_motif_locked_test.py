"""Leakage-safe optimizer selection and locked-test evaluation for CPG-EI."""
from __future__ import annotations

import json
import math

from prototype.cpg_ei_mvp import CpgEiTransitionModel, FEATURE_NAMES, evaluate
from prototype.cpg_ei_conditional_motif_e2e import make_parity_dataset, expected_support
from prototype.cpg_ei_conditional_motif_proposals import rank_conditional_motifs


def _fit(train, evaluation_rows, seed, learning_rate, epochs, support):
    proposal = rank_conditional_motifs(train, max_motifs=3)
    motifs = [tuple(item["lines"]) for item in proposal["selected"]]
    selected = {
        name for item in proposal["selected"] for name in item["feature_names"]
    }
    model = CpgEiTransitionModel.create(
        active_relation_indices={FEATURE_NAMES.index(name) for name in selected}
    )
    losses = model.train(
        train, epochs=epochs, learning_rate=learning_rate,
        gate_l1=0.0, edge_group_l1=0.0,
    )
    metrics = evaluate(model, evaluation_rows)
    overlap = len(selected & support)
    return {
        "seed": seed,
        "learning_rate": learning_rate,
        "epochs": epochs,
        "selected_motifs": [list(lines) for lines in motifs],
        "selected_relation_count": len(selected),
        "support_precision": overlap / len(selected) if selected else 0.0,
        "support_recall": overlap / len(support),
        "exact_support_recovery": selected == support,
        "bit_accuracy": metrics["bit_accuracy"],
        "exact_state_accuracy": metrics["exact_state_accuracy"],
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "finite_loss": all(math.isfinite(value) for value in losses),
    }


def run_locked_test(
    *,
    seeds: tuple[int, ...] = (11, 23, 37, 53, 71),
    learning_rates: tuple[float, ...] = (0.35, 1.05, 2.1, 4.2),
    epoch_counts: tuple[int, ...] = (300, 600),
    train_samples: int = 512,
    dev_samples: int = 256,
    locked_samples: int = 256,
) -> dict:
    if not seeds or not learning_rates or not epoch_counts:
        raise ValueError("seeds, learning rates, and epoch counts must be non-empty")
    if any(rate <= 0 or not math.isfinite(rate) for rate in learning_rates):
        raise ValueError("learning rates must be finite and positive")
    if any(epoch < 1 for epoch in epoch_counts):
        raise ValueError("epoch counts must be positive")
    if min(train_samples, dev_samples, locked_samples) < 1:
        raise ValueError("sample counts must be positive")

    support = expected_support()
    splits = {
        seed: (
            make_parity_dataset(train_samples, seed),
            make_parity_dataset(dev_samples, seed + 1000),
            make_parity_dataset(locked_samples, seed + 10000),
        )
        for seed in seeds
    }

    # Hyperparameters are selected only from development metrics.
    dev_rows = []
    for rate in learning_rates:
        for epochs in epoch_counts:
            rows = [
                _fit(splits[seed][0], splits[seed][1], seed, rate, epochs, support)
                for seed in seeds
            ]
            dev_rows.append({
                "learning_rate": rate,
                "epochs": epochs,
                "mean_bit_accuracy": sum(row["bit_accuracy"] for row in rows) / len(rows),
                "mean_exact_state_accuracy": sum(
                    row["exact_state_accuracy"] for row in rows
                ) / len(rows),
                "exact_support_recovery_count": sum(
                    row["exact_support_recovery"] for row in rows
                ),
                "all_losses_finite": all(row["finite_loss"] for row in rows),
            })

    # Deterministic tie-break: dev bit accuracy, exact-state accuracy,
    # fewer epochs, then lower learning rate.
    chosen = max(
        dev_rows,
        key=lambda row: (
            row["mean_bit_accuracy"],
            row["mean_exact_state_accuracy"],
            -row["epochs"],
            -row["learning_rate"],
        ),
    )
    chosen_rate = chosen["learning_rate"]
    chosen_epochs = chosen["epochs"]

    # Refit using train + dev only. Locked examples are passed only to evaluate().
    locked_rows = []
    for seed in seeds:
        train, dev, locked = splits[seed]
        locked_rows.append(
            _fit(
                train + dev, locked, seed, chosen_rate, chosen_epochs, support
            )
        )

    return {
        "benchmark": "cpg-ei-conditional-motif-locked-test-v1",
        "seeds": list(seeds),
        "sample_counts": {
            "train": train_samples,
            "development": dev_samples,
            "locked_test": locked_samples,
        },
        "selection_policy": {
            "hyperparameter_selection": "development split only",
            "locked_test_access": "final evaluation only",
            "final_fit_data": "train + development",
            "tie_break": "dev bit accuracy, dev exact-state accuracy, fewer epochs, lower learning rate",
        },
        "selected_config": {
            "optimizer": "existing_full_batch_sgd",
            "learning_rate": chosen_rate,
            "epochs": chosen_epochs,
        },
        "development_sweep": dev_rows,
        "locked_test_summary": {
            "exact_support_recovery_count": sum(
                row["exact_support_recovery"] for row in locked_rows
            ),
            "mean_bit_accuracy": sum(row["bit_accuracy"] for row in locked_rows) / len(locked_rows),
            "min_bit_accuracy": min(row["bit_accuracy"] for row in locked_rows),
            "mean_exact_state_accuracy": sum(
                row["exact_state_accuracy"] for row in locked_rows
            ) / len(locked_rows),
            "all_losses_finite": all(row["finite_loss"] for row in locked_rows),
        },
        "locked_test_records": locked_rows,
        "claim_boundary": (
            "Five-seed finite six-line GF(2) parity benchmark. The locked test is "
            "excluded from hyperparameter selection and fitting. This does not "
            "establish arbitrary-arity discovery, open-world induction, natural-"
            "language reasoning, or general superiority to Transformer models."
        ),
    }


def main() -> None:
    print(json.dumps(run_locked_test(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
