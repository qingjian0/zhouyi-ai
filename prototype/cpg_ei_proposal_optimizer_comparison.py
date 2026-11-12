"""Compare SGD and Adam for proposal-split joint motif discovery.

The true support is not supplied to candidate selection. Candidate models are
fit on train states, ranked only on proposal states, and evaluated on locked
and alternate-family states after selection. This isolates whether the Adam
optimization advantage transfers from oracle-known-support fitting to actual
bounded candidate discovery.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from typing import Sequence

from prototype.cpg_ei_mvp import CpgEiTransitionModel, evaluate
from prototype.cpg_ei_joint_proposals import grow_relation_graph_joint_motifs
from prototype.cpg_ei_selection_sweep import (
    DEFAULT_SEEDS,
    RULE_FAMILIES,
    exact_support,
    make_examples,
    partition_states,
)


OPTIMIZER_CONFIGS = (
    {"optimizer": "sgd", "learning_rate": 4.2},
    {"optimizer": "adam", "learning_rate": 0.1},
)
DEFAULT_EPOCHS = (50, 100, 200)


def _support_metrics(active_edges, expected):
    discovered = set(active_edges)
    expected_set = set(expected)
    true_positive = len(discovered & expected_set)
    return {
        "support_precision": true_positive / len(discovered) if discovered else 0.0,
        "support_recall": true_positive / len(expected_set),
        "active_edge_count": len(discovered),
        "exact_support": discovered == expected_set,
    }


def run_comparison(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    epochs_grid: Sequence[int] = DEFAULT_EPOCHS,
    optimizer_configs: Sequence[dict] = OPTIMIZER_CONFIGS,
) -> dict:
    if not seeds or not epochs_grid or not optimizer_configs:
        raise ValueError("seeds, epoch grid and optimizer configs must be non-empty")
    if any(isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1
           for epoch in epochs_grid):
        raise ValueError("epoch values must be positive integers")
    if len(set(epochs_grid)) != len(epochs_grid):
        raise ValueError("epoch values must be unique")
    configs = []
    for config in optimizer_configs:
        optimizer = config.get("optimizer")
        rate = config.get("learning_rate")
        if optimizer not in {"sgd", "adam"}:
            raise ValueError("optimizer must be sgd or adam")
        if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0:
            raise ValueError("optimizer learning rate must be positive and finite")
        configs.append({"optimizer": optimizer, "learning_rate": float(rate)})

    records = []
    for seed in seeds:
        train_states, proposal_states, locked_states = partition_states(seed)
        train_set, proposal_set, locked_set = map(
            set, (train_states, proposal_states, locked_states)
        )
        if (train_set & proposal_set) or (train_set & locked_set) or (proposal_set & locked_set):
            raise AssertionError("train/proposal/locked partitions overlap")
        for family, triples in RULE_FAMILIES.items():
            train = make_examples(train_states, triples)
            proposal = make_examples(proposal_states, triples)
            locked = make_examples(locked_states, triples)
            expected = exact_support(triples)
            for epochs, config in itertools.product(epochs_grid, configs):
                model = CpgEiTransitionModel.create(active_relation_indices=set())
                result = grow_relation_graph_joint_motifs(
                    model,
                    train,
                    locked,
                    proposal_examples=proposal,
                    max_motifs=3,
                    epochs_per_candidate=epochs,
                    learning_rate=config["learning_rate"],
                    optimizer=config["optimizer"],
                    gate_l1=0.001,
                    edge_group_l1=0.001,
                    min_training_improvement=1e-5,
                )
                improvements = [
                    item["best_candidate_proposal_improvement"]
                    for item in result["trace"]
                ]
                accepted_rounds = sum(
                    item["selected_motif"] is not None for item in result["trace"]
                )
                ood = {
                    other_family: evaluate(
                        model, make_examples(locked_states, other_triples)
                    )["bit_accuracy"]
                    for other_family, other_triples in RULE_FAMILIES.items()
                    if other_family != family
                }
                row = {
                    "seed": seed,
                    "family": family,
                    "epochs_per_candidate": epochs,
                    "optimizer": config["optimizer"],
                    "learning_rate": config["learning_rate"],
                    "selected_motif_count": len(result["selected_motifs"]),
                    "accepted_rounds": accepted_rounds,
                    "candidate_fits": result["candidate_fits_total"],
                    "training_passes": epochs * (1 + result["candidate_fits_total"]),
                    "best_candidate_proposal_improvements": improvements,
                    "mean_best_candidate_improvement": (
                        sum(improvements) / len(improvements) if improvements else 0.0
                    ),
                    "max_best_candidate_improvement": (
                        max(improvements) if improvements else 0.0
                    ),
                    "proposal_bce": result["proposal_selection_binary_cross_entropy"],
                    "locked_bce": result["validation_binary_cross_entropy"],
                    "locked_bit_accuracy": result["validation"]["bit_accuracy"],
                    "ood_bit_accuracy_by_family": ood,
                    **_support_metrics(result["active_edges"], expected),
                }
                numeric = [
                    row["mean_best_candidate_improvement"],
                    row["max_best_candidate_improvement"],
                    row["proposal_bce"],
                    row["locked_bce"],
                    row["locked_bit_accuracy"],
                    row["support_precision"],
                    row["support_recall"],
                    *ood.values(),
                ]
                if not all(math.isfinite(value) for value in numeric):
                    raise AssertionError("non-finite optimizer candidate-discovery metric")
                records.append(row)

    grouped = defaultdict(list)
    for row in records:
        grouped[(row["optimizer"], row["learning_rate"], row["epochs_per_candidate"])].append(row)
    summary = []
    for (optimizer, rate, epochs), rows in sorted(grouped.items()):
        improvements = [
            value for row in rows
            for value in row["best_candidate_proposal_improvements"]
        ]
        ood_values = [
            value for row in rows
            for value in row["ood_bit_accuracy_by_family"].values()
        ]
        summary.append({
            "optimizer": optimizer,
            "learning_rate": rate,
            "epochs_per_candidate": epochs,
            "experiments": len(rows),
            "exact_support_recovery_count": sum(row["exact_support"] for row in rows),
            "mean_selected_motifs": sum(row["selected_motif_count"] for row in rows) / len(rows),
            "mean_support_precision": sum(row["support_precision"] for row in rows) / len(rows),
            "mean_support_recall": sum(row["support_recall"] for row in rows) / len(rows),
            "mean_proposal_bce": sum(row["proposal_bce"] for row in rows) / len(rows),
            "mean_locked_bit_accuracy": sum(row["locked_bit_accuracy"] for row in rows) / len(rows),
            "mean_ood_bit_accuracy": sum(ood_values) / len(ood_values),
            "mean_best_candidate_improvement": sum(improvements) / len(improvements),
            "max_best_candidate_improvement": max(improvements),
            "mean_training_passes": sum(row["training_passes"] for row in rows) / len(rows),
        })

    return {
        "benchmark": "cpg-ei-proposal-split-sgd-vs-adam-v1",
        "seeds": list(seeds),
        "families": list(RULE_FAMILIES),
        "epochs_grid": list(epochs_grid),
        "optimizer_configs": configs,
        "split_sizes": {"train": 40, "proposal": 12, "locked_test": 12},
        "candidate_fit_partition": "train",
        "candidate_ranking_partition": "proposal",
        "locked_and_ood_metrics_used_for_selection": False,
        "summary": summary,
        "records": records,
        "claim_boundary": (
            "Finite synthetic six-bit parity candidate-discovery experiment. "
            "No oracle support is supplied to selection; no natural-language or "
            "open-world relation-induction claim is made."
        ),
    }


def _parse_ints(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_parse_ints, default=DEFAULT_SEEDS)
    parser.add_argument("--epochs", type=_parse_ints, default=DEFAULT_EPOCHS)
    args = parser.parse_args(argv)
    report = run_comparison(seeds=args.seeds, epochs_grid=args.epochs)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
