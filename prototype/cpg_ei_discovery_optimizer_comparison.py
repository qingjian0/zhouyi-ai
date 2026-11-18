"""Compare SGD and Adam in CPG-EI's actual bounded motif-selection loop.

The true support is never supplied. Candidate fitting uses train states;
proposal_split ranks on a disjoint proposal partition; locked and alternate
family metrics are reporting-only. Finite synthetic six-bit diagnostic only.
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

DEFAULT_CONFIGS = (
    ("sgd", 1.0),
    ("sgd", 2.0),
    ("adam", 0.03),
    ("adam", 0.1),
)


def run_selection_optimizer_comparison(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    optimizer_configs: Sequence[tuple[str, float]] = DEFAULT_CONFIGS,
    epochs_per_candidate: int = 50,
    max_motifs: int = 3,
) -> dict:
    if not seeds or not optimizer_configs:
        raise ValueError("seeds and optimizer_configs must be non-empty")
    if epochs_per_candidate < 1 or not 1 <= max_motifs <= 20:
        raise ValueError("invalid candidate training schedule")
    configs = tuple((str(name), float(rate)) for name, rate in optimizer_configs)
    if any(name not in {"sgd", "adam"} for name, _ in configs):
        raise ValueError("optimizer must be 'sgd' or 'adam'")
    if any(not math.isfinite(rate) or rate <= 0.0 for _, rate in configs):
        raise ValueError("learning rates must be positive and finite")
    if len(set(configs)) != len(configs):
        raise ValueError("optimizer configurations must be unique")

    records = []
    for seed in seeds:
        train_states, proposal_states, locked_states = partition_states(seed)
        partitions = tuple(set(part) for part in (
            train_states, proposal_states, locked_states
        ))
        if any(
            partitions[i] & partitions[j]
            for i in range(3) for j in range(i + 1, 3)
        ):
            raise AssertionError("train/proposal/locked partitions overlap")

        for family, triples in RULE_FAMILIES.items():
            train = make_examples(train_states, triples)
            proposal = make_examples(proposal_states, triples)
            locked = make_examples(locked_states, triples)
            expected = exact_support(triples)

            for optimizer, learning_rate in configs:
                for protocol in ("proposal_split", "legacy_train_ranked"):
                    model = CpgEiTransitionModel.create(active_relation_indices=set())
                    kwargs = (
                        {"proposal_examples": proposal}
                        if protocol == "proposal_split" else {}
                    )
                    result = grow_relation_graph_joint_motifs(
                        model,
                        train,
                        locked,
                        **kwargs,
                        max_motifs=max_motifs,
                        epochs_per_candidate=epochs_per_candidate,
                        learning_rate=learning_rate,
                        gate_l1=0.001,
                        edge_group_l1=0.001,
                        optimizer=optimizer,
                    )
                    discovered = set(result["active_edges"])
                    true_positive = len(discovered & expected)
                    precision = (
                        true_positive / len(discovered) if discovered else 0.0
                    )
                    recall = true_positive / len(expected)
                    ood = {
                        other_family: evaluate(
                            model, make_examples(locked_states, other_triples)
                        )["bit_accuracy"]
                        for other_family, other_triples in RULE_FAMILIES.items()
                        if other_family != family
                    }
                    row = {
                        "seed": seed,
                        "train_family": family,
                        "optimizer": optimizer,
                        "learning_rate": learning_rate,
                        "selection_protocol": protocol,
                        "epochs_per_candidate": epochs_per_candidate,
                        "max_motifs": max_motifs,
                        "train_examples": len(train),
                        "proposal_examples": (
                            len(proposal) if protocol == "proposal_split" else 0
                        ),
                        "locked_test_examples": len(locked),
                        "selected_motif_count": len(result["selected_motifs"]),
                        "candidate_fits": result["candidate_fits_total"],
                        "training_passes": epochs_per_candidate * (
                            1 + result["candidate_fits_total"]
                        ),
                        "selection_bce": result[
                            "proposal_selection_binary_cross_entropy"
                        ],
                        "selection_metric_source": (
                            "proposal" if protocol == "proposal_split" else "train"
                        ),
                        "locked_test_bce": result["validation_binary_cross_entropy"],
                        "locked_test_bit_accuracy": result["validation"]["bit_accuracy"],
                        "support_precision": precision,
                        "support_recall": recall,
                        "active_edge_count": len(discovered),
                        "exact_support_recovery": (
                            precision == 1.0 and recall == 1.0
                        ),
                        "ood_bit_accuracy_by_family": ood,
                        "locked_and_ood_metrics_used_for_selection": False,
                    }
                    metrics = [
                        row["selection_bce"],
                        row["locked_test_bce"],
                        row["locked_test_bit_accuracy"],
                        row["support_precision"],
                        row["support_recall"],
                        *ood.values(),
                    ]
                    if not all(math.isfinite(value) for value in metrics):
                        raise AssertionError("non-finite optimizer selection metric")
                    records.append(row)

    grouped = defaultdict(list)
    for row in records:
        grouped[(
            row["optimizer"], row["learning_rate"], row["selection_protocol"]
        )].append(row)
    summary = []
    for (optimizer, rate, protocol), rows in sorted(grouped.items()):
        ood_values = [
            value for row in rows
            for value in row["ood_bit_accuracy_by_family"].values()
        ]
        summary.append({
            "optimizer": optimizer,
            "learning_rate": rate,
            "selection_protocol": protocol,
            "experiments": len(rows),
            "experiments_with_any_selected_motif": sum(
                row["selected_motif_count"] > 0 for row in rows
            ),
            "exact_support_recovery_count": sum(
                row["exact_support_recovery"] for row in rows
            ),
            "mean_selected_motifs": sum(
                row["selected_motif_count"] for row in rows
            ) / len(rows),
            "mean_support_precision": sum(
                row["support_precision"] for row in rows
            ) / len(rows),
            "mean_support_recall": sum(
                row["support_recall"] for row in rows
            ) / len(rows),
            "mean_locked_test_bit_accuracy": sum(
                row["locked_test_bit_accuracy"] for row in rows
            ) / len(rows),
            "mean_ood_bit_accuracy": sum(ood_values) / len(ood_values),
            "mean_training_passes": sum(
                row["training_passes"] for row in rows
            ) / len(rows),
        })

    return {
        "benchmark": "cpg-ei-discovery-sgd-vs-adam-v1",
        "seeds": list(seeds),
        "rule_families": list(RULE_FAMILIES),
        "optimizer_configs": [
            {"optimizer": name, "learning_rate": rate}
            for name, rate in configs
        ],
        "split_sizes": {
            "train": 40, "proposal_selection": 12, "locked_test": 12
        },
        "epochs_per_candidate": epochs_per_candidate,
        "max_motifs": max_motifs,
        "selection_metrics": {
            "proposal_split": "proposal_selection_bce",
            "legacy_train_ranked": "train_bce",
        },
        "locked_and_ood_metrics_used_for_selection": False,
        "summary": summary,
        "records": records,
        "claim_boundary": (
            "Finite synthetic six-bit parity families only; true support is "
            "not supplied. This does not establish open-ended relation "
            "induction, natural-language reasoning, or production readiness."
        ),
    }


def _parse_seeds(value: str) -> tuple[int, ...]:
    try:
        seeds = tuple(
            int(part.strip()) for part in value.split(",") if part.strip()
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "seeds must be comma-separated integers"
        ) from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_parse_seeds, default=DEFAULT_SEEDS)
    parser.add_argument("--epochs-per-candidate", type=int, default=50)
    parser.add_argument("--max-motifs", type=int, default=3)
    args = parser.parse_args(argv)
    report = run_selection_optimizer_comparison(
        seeds=args.seeds,
        epochs_per_candidate=args.epochs_per_candidate,
        max_motifs=args.max_motifs,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
