"""Diagnose rejected CPG-EI proposal-split candidates under corrected gradients.

The benchmark records the best proposal BCE achieved by every candidate round,
including candidates rejected by the current acceptance rule. Candidate fitting
uses train states only; proposal states rank candidates; locked states are used
only for final reporting. Five seeds and three finite parity families are used.
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

DEFAULT_EPOCHS = (50, 100, 200)
DEFAULT_LEARNING_RATE = 4.2


def _support_metrics(active_edges, expected):
    discovered = set(active_edges)
    true_positive = len(discovered & expected)
    return {
        "support_precision": true_positive / len(discovered) if discovered else 0.0,
        "support_recall": true_positive / len(expected),
        "active_edge_count": len(discovered),
    }


def run_diagnostics(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    epochs_grid: Sequence[int] = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    min_proposal_improvement: float = 1e-5,
) -> dict:
    if not seeds or not epochs_grid:
        raise ValueError("seeds and epoch grid must be non-empty")
    if any(isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1
           for epoch in epochs_grid):
        raise ValueError("epoch values must be positive integers")
    if len(set(epochs_grid)) != len(epochs_grid):
        raise ValueError("epoch values must be unique")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning rate must be positive and finite")
    if not math.isfinite(min_proposal_improvement) or min_proposal_improvement < 0:
        raise ValueError("proposal improvement threshold must be finite and non-negative")

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
            for epochs in epochs_grid:
                model = CpgEiTransitionModel.create(active_relation_indices=set())
                result = grow_relation_graph_joint_motifs(
                    model,
                    train,
                    locked,
                    proposal_examples=proposal,
                    max_motifs=3,
                    epochs_per_candidate=epochs,
                    learning_rate=learning_rate,
                    gate_l1=0.001,
                    edge_group_l1=0.001,
                    min_training_improvement=min_proposal_improvement,
                )
                best_improvements = [
                    row["best_candidate_proposal_improvement"]
                    for row in result["trace"]
                ]
                best_candidate_bces = [
                    row["best_candidate_proposal_bce"]
                    for row in result["trace"]
                ]
                accepted_rounds = sum(
                    row["selected_motif"] is not None for row in result["trace"]
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
                    "learning_rate": learning_rate,
                    "min_proposal_improvement": min_proposal_improvement,
                    "selected_motif_count": len(result["selected_motifs"]),
                    "accepted_rounds": accepted_rounds,
                    "candidate_fits": result["candidate_fits_total"],
                    "training_passes": epochs * (1 + result["candidate_fits_total"]),
                    "best_candidate_proposal_improvements": best_improvements,
                    "best_candidate_proposal_bces": best_candidate_bces,
                    "mean_best_candidate_improvement": (
                        sum(best_improvements) / len(best_improvements)
                        if best_improvements else 0.0
                    ),
                    "max_best_candidate_improvement": (
                        max(best_improvements) if best_improvements else 0.0
                    ),
                    "mean_proposal_bce": result["proposal_selection_binary_cross_entropy"],
                    "locked_test_bce": result["validation_binary_cross_entropy"],
                    "locked_test_bit_accuracy": result["validation"]["bit_accuracy"],
                    "ood_bit_accuracy_by_family": ood,
                    **_support_metrics(result["active_edges"], expected),
                }
                numeric = [
                    row["mean_best_candidate_improvement"],
                    row["max_best_candidate_improvement"],
                    row["mean_proposal_bce"],
                    row["locked_test_bce"],
                    row["locked_test_bit_accuracy"],
                    row["support_precision"],
                    row["support_recall"],
                    *ood.values(),
                    *best_candidate_bces,
                ]
                if not all(math.isfinite(value) for value in numeric):
                    raise AssertionError("non-finite proposal-ranking diagnostic")
                records.append(row)

    grouped = defaultdict(list)
    for row in records:
        grouped[row["epochs_per_candidate"]].append(row)
    summary = []
    for epochs, rows in sorted(grouped.items()):
        improvements = [
            value for row in rows
            for value in row["best_candidate_proposal_improvements"]
        ]
        ood_values = [
            value for row in rows
            for value in row["ood_bit_accuracy_by_family"].values()
        ]
        summary.append({
            "epochs_per_candidate": epochs,
            "experiments": len(rows),
            "mean_selected_motifs": sum(r["selected_motif_count"] for r in rows) / len(rows),
            "exact_support_recovery_count": sum(
                r["support_precision"] == 1.0 and r["support_recall"] == 1.0
                for r in rows
            ),
            "mean_support_precision": sum(r["support_precision"] for r in rows) / len(rows),
            "mean_support_recall": sum(r["support_recall"] for r in rows) / len(rows),
            "mean_locked_test_bit_accuracy": sum(r["locked_test_bit_accuracy"] for r in rows) / len(rows),
            "mean_ood_bit_accuracy": sum(ood_values) / len(ood_values),
            "mean_best_candidate_proposal_improvement": sum(improvements) / len(improvements),
            "max_best_candidate_proposal_improvement": max(improvements),
            "mean_training_passes": sum(r["training_passes"] for r in rows) / len(rows),
        })

    return {
        "benchmark": "cpg-ei-proposal-ranking-diagnostics-v1",
        "seeds": list(seeds),
        "families": list(RULE_FAMILIES),
        "epochs_grid": list(epochs_grid),
        "learning_rate": learning_rate,
        "min_proposal_improvement": min_proposal_improvement,
        "split_sizes": {"train": 40, "proposal": 12, "locked_test": 12},
        "ranking_partition": "proposal",
        "candidate_fit_partition": "train",
        "locked_and_ood_metrics_used_for_selection": False,
        "summary": summary,
        "records": records,
        "claim_boundary": (
            "Finite synthetic six-bit parity diagnostic only. Oracle support is not "
            "provided to candidate selection. This does not establish open-world "
            "relation induction, natural-language reasoning, or production readiness."
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
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    args = parser.parse_args(argv)
    report = run_diagnostics(
        seeds=args.seeds,
        epochs_grid=args.epochs,
        learning_rate=args.learning_rate,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
