"""CPG-EI candidate-selection learning-rate sensitivity on finite parity families.

This sweep changes only the candidate-fit learning rate. Candidate parameters
are fitted on the train partition, proposal_split candidates are ranked on the
independent proposal partition, and locked states are reported only after
selection. It is a finite synthetic diagnostic, not an open-world claim.
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

DEFAULT_LEARNING_RATES = (0.15, 0.35, 0.7)


def _support_metrics(active_edges, expected):
    discovered = set(active_edges)
    true_positive = len(discovered & expected)
    return {
        "support_precision": true_positive / len(discovered) if discovered else 0.0,
        "support_recall": true_positive / len(expected),
        "active_edge_count": len(discovered),
    }


def run_selection_optimizer_sweep(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    learning_rates: Sequence[float] = DEFAULT_LEARNING_RATES,
    epochs: int = 50,
) -> dict:
    if not seeds or not learning_rates or epochs < 1:
        raise ValueError("seeds, learning_rates, and epochs must be non-empty/positive")
    if any(not math.isfinite(rate) or rate <= 0.0 for rate in learning_rates):
        raise ValueError("learning rates must be positive and finite")
    if len(set(learning_rates)) != len(learning_rates):
        raise ValueError("learning rates must be unique")

    records = []
    for seed in seeds:
        train_states, proposal_states, locked_states = partition_states(seed)
        parts = tuple(set(part) for part in (train_states, proposal_states, locked_states))
        if any(parts[i] & parts[j] for i in range(3) for j in range(i + 1, 3)):
            raise AssertionError("train/proposal/locked partitions overlap")
        for family, triples in RULE_FAMILIES.items():
            train = make_examples(train_states, triples)
            proposal = make_examples(proposal_states, triples)
            locked = make_examples(locked_states, triples)
            expected = exact_support(triples)
            for learning_rate in learning_rates:
                for protocol in ("proposal_split", "legacy_train_ranked"):
                    model = CpgEiTransitionModel.create(active_relation_indices=set())
                    ranking_partition = "proposal" if protocol == "proposal_split" else "train"
                    kwargs = {"proposal_examples": proposal} if protocol == "proposal_split" else {}
                    result = grow_relation_graph_joint_motifs(
                        model,
                        train,
                        locked,
                        **kwargs,
                        max_motifs=3,
                        epochs_per_candidate=epochs,
                        learning_rate=learning_rate,
                        gate_l1=0.001,
                        edge_group_l1=0.001,
                    )
                    ood = {
                        other_family: evaluate(
                            model, make_examples(locked_states, other_triples)
                        )["bit_accuracy"]
                        for other_family, other_triples in RULE_FAMILIES.items()
                        if other_family != family
                    }
                    record = {
                        "seed": seed,
                        "train_family": family,
                        "learning_rate": learning_rate,
                        "epochs_per_candidate": epochs,
                        "selection_protocol": protocol,
                        "train_examples": len(train),
                        "proposal_examples": len(proposal) if protocol == "proposal_split" else 0,
                        "locked_test_examples": len(locked),
                        "selected_motif_count": len(result["selected_motifs"]),
                        "candidate_fits": result["candidate_fits_total"],
                        "training_passes": epochs * (1 + result["candidate_fits_total"]),
                        # The legacy baseline deliberately ranks on train BCE;
                        # do not label that score as proposal-held-out evidence.
                        "candidate_ranking_partition": ranking_partition,
                        "candidate_ranking_bce": result["proposal_selection_binary_cross_entropy"],
                        "proposal_selection_bce": (
                            result["proposal_selection_binary_cross_entropy"]
                            if ranking_partition == "proposal" else None
                        ),
                        "locked_test_bce": result["validation_binary_cross_entropy"],
                        "locked_test_bit_accuracy": result["validation"]["bit_accuracy"],
                        "ood_bit_accuracy_by_family": ood,
                        **_support_metrics(result["active_edges"], expected),
                    }
                    metrics = [
                        record["candidate_ranking_bce"],
                        record["locked_test_bce"],
                        record["locked_test_bit_accuracy"],
                        record["support_precision"],
                        record["support_recall"],
                        *ood.values(),
                    ]
                    if not all(math.isfinite(value) for value in metrics):
                        raise AssertionError("non-finite selection optimizer metric")
                    records.append(record)

    grouped = defaultdict(list)
    for row in records:
        grouped[(row["learning_rate"], row["selection_protocol"])].append(row)

    summary = []
    for (learning_rate, protocol), rows in sorted(grouped.items()):
        ood_values = [
            value for row in rows
            for value in row["ood_bit_accuracy_by_family"].values()
        ]
        summary.append({
            "learning_rate": learning_rate,
            "selection_protocol": protocol,
            "experiments": len(rows),
            "exact_support_recovery_count": sum(
                row["support_precision"] == 1.0 and row["support_recall"] == 1.0
                for row in rows
            ),
            "mean_selected_motifs": sum(row["selected_motif_count"] for row in rows) / len(rows),
            "mean_support_precision": sum(row["support_precision"] for row in rows) / len(rows),
            "mean_support_recall": sum(row["support_recall"] for row in rows) / len(rows),
            "mean_locked_test_bit_accuracy": sum(row["locked_test_bit_accuracy"] for row in rows) / len(rows),
            "mean_ood_bit_accuracy": sum(ood_values) / len(ood_values),
            "mean_training_passes": sum(row["training_passes"] for row in rows) / len(rows),
        })

    return {
        "benchmark": "cpg-ei-selection-learning-rate-sensitivity-v1",
        "seeds": list(seeds),
        "rule_families": list(RULE_FAMILIES),
        "learning_rates": list(learning_rates),
        "epochs_per_candidate": epochs,
        "split_sizes": {"train": 40, "proposal_selection": 12, "locked_test": 12},
        "regularization": {"gate_l1": 0.001, "edge_group_l1": 0.001},
        "summary": summary,
        "records": records,
        "selection_metric": "candidate_ranking_bce_on_protocol_specific_partition",
        "ranking_partitions": {
            "proposal_split": "proposal",
            "legacy_train_ranked": "train",
        },
        "locked_and_ood_metrics_used_for_selection": False,
        "claim_boundary": (
            "Finite synthetic six-bit parity families only. This sweep tests "
            "candidate-fit optimizer sensitivity, not open-ended relation "
            "induction, natural-language reasoning, or production readiness."
        ),
    }


def _parse_seeds(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return result


def _parse_rates(value: str) -> tuple[float, ...]:
    try:
        result = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("learning rates must be comma-separated numbers") from exc
    if not result or any(not math.isfinite(rate) or rate <= 0.0 for rate in result):
        raise argparse.ArgumentTypeError("learning rates must be positive and finite")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_parse_seeds, default=DEFAULT_SEEDS)
    parser.add_argument("--learning-rates", type=_parse_rates, default=DEFAULT_LEARNING_RATES)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    report = run_selection_optimizer_sweep(
        seeds=args.seeds, learning_rates=args.learning_rates, epochs=args.epochs
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) if args.json else report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
