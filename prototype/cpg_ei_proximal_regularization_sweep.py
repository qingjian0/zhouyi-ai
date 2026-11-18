"""Calibrate proximal group-L1 after correcting CPG-EI mean-head gradients.

The six-output BCE gradient is normalized by six heads. This sweep holds the
corrected SGD learning rate at 2.1 and measures group-L1 values in both direct
sparse-teacher fitting and residual structure discovery. It does not choose a
configuration from validation metrics; all values are reported side-by-side.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from typing import Sequence

from prototype.cpg_ei_mvp import CpgEiTransitionModel, FEATURE_NAMES, evaluate, make_dataset
from prototype.cpg_ei_structure_discovery import grow_relation_graph

DEFAULT_SEEDS = (7, 17, 29, 41, 53)
DEFAULT_GROUP_L1 = (0.001, 0.0025, 0.005, 0.0075, 0.01, 0.015, 0.03)
TRUE_SUPPORT = {
    FEATURE_NAMES[7 + index] for index in (0, 4, 10)
} | {
    FEATURE_NAMES[22 + index] for index in (1, 7, 15)
}


def _support_metrics(discovered):
    found = set(discovered)
    true_positive = len(found & TRUE_SUPPORT)
    return {
        "active_group_count": len(found),
        "support_precision": true_positive / len(found) if found else 0.0,
        "support_recall": true_positive / len(TRUE_SUPPORT),
        "exact_support_recovery": found == TRUE_SUPPORT,
    }


def run_proximal_regularization_sweep(
    *,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    group_l1_values: Sequence[float] = DEFAULT_GROUP_L1,
    learning_rate: float = 2.1,
    direct_epochs: int = 120,
    discovery_rounds: int = 5,
    edges_per_round: int = 3,
    discovery_epochs_per_round: int = 100,
) -> dict:
    if not seeds or not group_l1_values:
        raise ValueError("seeds and group_l1_values must be non-empty")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if direct_epochs < 1 or discovery_rounds < 1 or discovery_epochs_per_round < 1:
        raise ValueError("epoch and round budgets must be positive")
    if not 1 <= edges_per_round <= 35:
        raise ValueError("edges_per_round must be in [1, 35]")
    values = tuple(float(value) for value in group_l1_values)
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("group_l1 values must be finite and non-negative")
    if len(set(values)) != len(values):
        raise ValueError("group_l1 values must be unique")

    records = []
    for seed in seeds:
        train = make_dataset(1024, seed=seed, sparse_teacher=True)
        validation = make_dataset(256, seed=seed + 1, sparse_teacher=True)
        for group_l1 in values:
            direct = CpgEiTransitionModel.create()
            direct_losses = direct.train(
                train,
                epochs=direct_epochs,
                learning_rate=learning_rate,
                gate_l1=0.01,
                edge_group_l1=group_l1,
            )
            direct_discovered = {
                FEATURE_NAMES[index]
                for index in direct.active_relation_indices
                if math.sqrt(sum(
                    direct.weights[head][index] ** 2 for head in range(6)
                )) > 1e-5
            }
            direct_metrics = evaluate(direct, validation)
            records.append({
                "seed": seed,
                "mode": "direct_sparse_fit",
                "learning_rate": learning_rate,
                "group_l1": group_l1,
                "epochs": direct_epochs,
                "training_loss": direct_losses[-1],
                "validation_bit_accuracy": direct_metrics["bit_accuracy"],
                **_support_metrics(direct_discovered),
            })

            discovered_model = CpgEiTransitionModel.create(
                active_relation_indices=set()
            )
            result = grow_relation_graph(
                discovered_model,
                train,
                validation,
                rounds=discovery_rounds,
                edges_per_round=edges_per_round,
                epochs_per_round=discovery_epochs_per_round,
                learning_rate=learning_rate,
                gate_l1=0.01,
                edge_group_l1=group_l1,
            )
            metrics = evaluate(discovered_model, validation)
            records.append({
                "seed": seed,
                "mode": "residual_structure_discovery",
                "learning_rate": learning_rate,
                "group_l1": group_l1,
                "epochs": discovery_rounds * (discovery_epochs_per_round + 1),
                "training_loss": None,
                "validation_bit_accuracy": metrics["bit_accuracy"],
                **_support_metrics(result["active_edges"]),
            })

    grouped = defaultdict(list)
    for row in records:
        grouped[(row["mode"], row["group_l1"])].append(row)
    summary = []
    for (mode, group_l1), rows in sorted(grouped.items()):
        summary.append({
            "mode": mode,
            "group_l1": group_l1,
            "experiments": len(rows),
            "mean_validation_bit_accuracy": sum(
                row["validation_bit_accuracy"] for row in rows
            ) / len(rows),
            "mean_active_group_count": sum(
                row["active_group_count"] for row in rows
            ) / len(rows),
            "mean_support_precision": sum(
                row["support_precision"] for row in rows
            ) / len(rows),
            "mean_support_recall": sum(
                row["support_recall"] for row in rows
            ) / len(rows),
            "exact_support_recovery_count": sum(
                row["exact_support_recovery"] for row in rows
            ),
        })

    return {
        "benchmark": "cpg-ei-proximal-group-l1-calibration-v1",
        "seeds": list(seeds),
        "learning_rate": learning_rate,
        "group_l1_values": list(values),
        "gate_l1": 0.01,
        "direct_epochs": direct_epochs,
        "discovery_rounds": discovery_rounds,
        "edges_per_round": edges_per_round,
        "discovery_epochs_per_round": discovery_epochs_per_round,
        "true_support": sorted(TRUE_SUPPORT),
        "summary": summary,
        "records": records,
        "selection_metric": "none; all configurations reported",
        "claim_boundary": (
            "Synthetic sparse six-bit teacher only. This calibrates proximal "
            "regularization after gradient normalization; it does not establish "
            "open-ended relation induction or natural-language reasoning."
        ),
    }


def _parse_numbers(value: str) -> tuple[float, ...]:
    try:
        result = tuple(float(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated numbers") from exc
    if not result:
        raise argparse.ArgumentTypeError("at least one value is required")
    return result


def _parse_seeds(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not result:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=_parse_seeds, default=DEFAULT_SEEDS)
    parser.add_argument("--group-l1-values", type=_parse_numbers, default=DEFAULT_GROUP_L1)
    parser.add_argument("--learning-rate", type=float, default=2.1)
    parser.add_argument("--direct-epochs", type=int, default=120)
    parser.add_argument("--discovery-rounds", type=int, default=5)
    parser.add_argument("--edges-per-round", type=int, default=3)
    parser.add_argument("--discovery-epochs-per-round", type=int, default=100)
    args = parser.parse_args(argv)
    report = run_proximal_regularization_sweep(
        seeds=args.seeds,
        group_l1_values=args.group_l1_values,
        learning_rate=args.learning_rate,
        direct_epochs=args.direct_epochs,
        discovery_rounds=args.discovery_rounds,
        edges_per_round=args.edges_per_round,
        discovery_epochs_per_round=args.discovery_epochs_per_round,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
