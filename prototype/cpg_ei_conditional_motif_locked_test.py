"""Leakage-safe optimizer selection and state-disjoint locked-test evaluation."""
from __future__ import annotations

import itertools
import json
import math
import random

from prototype.cpg_ei_mvp import CpgEiTransitionModel, Example, FEATURE_NAMES, evaluate
from prototype.cpg_ei_conditional_motif_e2e import PARITY_TRIPLES, expected_support
from prototype.cpg_ei_conditional_motif_proposals import rank_conditional_motifs


def make_state_disjoint_splits(seed: int) -> tuple[list[Example], list[Example], list[Example]]:
    """Partition the complete 6-bit state space into disjoint 32/16/16 splits."""
    states = list(itertools.product((0, 1), repeat=6))
    random.Random(seed).shuffle(states)

    def label(state):
        return tuple(
            sum(state[index] for index in PARITY_TRIPLES[head // 2]) % 2
            for head in range(6)
        )

    rows = [Example(tuple(state), label(state)) for state in states]
    return rows[:32], rows[32:48], rows[48:]


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
) -> dict:
    if not seeds or not learning_rates or not epoch_counts:
        raise ValueError("seeds, learning rates, and epoch counts must be non-empty")
    if any(rate <= 0 or not math.isfinite(rate) for rate in learning_rates):
        raise ValueError("learning rates must be finite and positive")
    if any(epoch < 1 for epoch in epoch_counts):
        raise ValueError("epoch counts must be positive")

    support = expected_support()
    splits = {seed: make_state_disjoint_splits(seed) for seed in seeds}

    # Hyperparameters are selected only from development states.
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

    # Refit on train + dev. Locked states are only passed to evaluate().
    locked_rows = []
    split_audit = []
    for seed in seeds:
        train, dev, locked = splits[seed]
        train_states = {row.state for row in train}
        dev_states = {row.state for row in dev}
        locked_states = {row.state for row in locked}
        split_audit.append({
            "seed": seed,
            "train_unique_states": len(train_states),
            "development_unique_states": len(dev_states),
            "locked_unique_states": len(locked_states),
            "train_dev_overlap": len(train_states & dev_states),
            "train_locked_overlap": len(train_states & locked_states),
            "dev_locked_overlap": len(dev_states & locked_states),
            "union_states": len(train_states | dev_states | locked_states),
        })
        locked_rows.append(
            _fit(train + dev, locked, seed, chosen_rate, chosen_epochs, support)
        )

    if any(
        audit["train_dev_overlap"] or audit["train_locked_overlap"]
        or audit["dev_locked_overlap"] or audit["union_states"] != 64
        for audit in split_audit
    ):
        raise AssertionError("state-disjoint split invariant violated")

    return {
        "benchmark": "cpg-ei-conditional-motif-state-disjoint-locked-test-v2",
        "seeds": list(seeds),
        "sample_counts": {
            "train": 32,
            "development": 16,
            "locked_test": 16,
            "total_unique_states": 64,
        },
        "split_semantics": "complete six-bit input state space partitioned without overlap",
        "split_audit": split_audit,
        "selection_policy": {
            "hyperparameter_selection": "development states only",
            "locked_test_access": "final evaluation only",
            "final_fit_data": "train + development states",
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
            "Five-seed complete six-bit GF(2) state-space partition. Locked input "
            "states are disjoint from training and development states. This finite "
            "truth-table benchmark does not establish arbitrary-arity discovery, "
            "open-world induction, natural-language reasoning, or general superiority "
            "to Transformer models."
        ),
    }


def main() -> None:
    print(json.dumps(run_locked_test(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
