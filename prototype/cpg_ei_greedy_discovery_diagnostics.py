"""Diagnose CPG-EI convergence and greedy structure-selection sensitivity.

All hyperparameters are fixed before evaluation. Synthetic teacher support is
used only for post-hoc metrics; validation examples are never used to rank edges.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict

from prototype.cpg_ei_mvp import (
    CpgEiTransitionModel, FEATURE_NAMES, evaluate, make_dataset,
)
from prototype.cpg_ei_structure_discovery import grow_relation_graph

TRUE_SUPPORT = {
    "hyperedge_2_0_1", "hyperedge_2_0_5", "hyperedge_2_2_4",
    "hyperedge_3_0_1_3", "hyperedge_3_0_3_4", "hyperedge_3_1_4_5",
}


def _metrics(discovered):
    overlap = len(discovered & TRUE_SUPPORT)
    return {
        "support_precision": overlap / len(discovered) if discovered else 0.0,
        "support_recall": overlap / len(TRUE_SUPPORT),
        "active_edges": len(discovered),
    }


def run_sweep(*, seeds=(7, 17, 29), mvp_configs=None,
              structure_configs=None, structure_epochs=60,
              structure_rounds=3, samples=512):
    if not seeds:
        raise ValueError("at least one seed is required")
    mvp_configs = mvp_configs or tuple(
        (rate, epochs) for rate, epochs in
        ((2.1, 120), (4.2, 120), (8.4, 120),
         (2.1, 240), (4.2, 240), (8.4, 240))
    )
    structure_configs = structure_configs or tuple(
        (rate, penalty, normalized)
        for rate, penalty, normalized in itertools.product(
            (2.1, 4.2), (0.003, 0.03), (False, True)
        )
    )
    mvp_records = []
    for seed in seeds:
        train = make_dataset(1024, seed=seed, sparse_teacher=True)
        test = make_dataset(256, seed=seed + 1, sparse_teacher=True)
        for rate, epochs in mvp_configs:
            model = CpgEiTransitionModel.create()
            losses = model.train(
                train, epochs=epochs, learning_rate=rate,
                gate_l1=0.01, edge_group_l1=0.03,
            )
            metrics = evaluate(model, test)
            active = {
                FEATURE_NAMES[index]
                for index in range(7, len(FEATURE_NAMES))
                if math.sqrt(sum(model.weights[h][index] ** 2 for h in range(6))) > 1e-5
            }
            mvp_records.append({
                "seed": seed, "learning_rate": rate, "epochs": epochs,
                "initial_loss": losses[0], "final_loss": losses[-1],
                "bit_accuracy": metrics["bit_accuracy"],
                **_metrics(active),
            })

    structure_records = []
    for seed in seeds:
        train = make_dataset(samples, seed=seed, sparse_teacher=True)
        validation = make_dataset(max(128, samples // 4), seed=seed + 100, sparse_teacher=True)
        for rate, penalty, normalized in structure_configs:
            model = CpgEiTransitionModel.create(active_relation_indices=set())
            result = grow_relation_graph(
                model, train, validation,
                rounds=structure_rounds, edges_per_round=3,
                epochs_per_round=structure_epochs,
                learning_rate=rate, gate_l1=0.01,
                edge_group_l1=penalty,
                normalize_candidate_scores=normalized,
            )
            discovered = set(result["active_edges"])
            structure_records.append({
                "seed": seed, "learning_rate": rate,
                "edge_group_l1": penalty,
                "normalized_candidate_scores": normalized,
                "bit_accuracy": result["validation"]["bit_accuracy"],
                **_metrics(discovered),
            })

    def aggregate(records, keys):
        groups = defaultdict(list)
        for row in records:
            groups[tuple(row[key] for key in keys)].append(row)
        summary = []
        for config, rows in sorted(groups.items(), key=lambda item: str(item[0])):
            summary.append({
                **dict(zip(keys, config)),
                "seeds": len(rows),
                "mean_bit_accuracy": sum(x["bit_accuracy"] for x in rows) / len(rows),
                "mean_support_precision": sum(x["support_precision"] for x in rows) / len(rows),
                "mean_support_recall": sum(x["support_recall"] for x in rows) / len(rows),
                "exact_support_recovery": sum(
                    x["support_precision"] == 1.0 and x["support_recall"] == 1.0
                    for x in rows
                ),
                "mean_active_edges": sum(x["active_edges"] for x in rows) / len(rows),
            })
        return summary

    return {
        "benchmark": "cpg-ei-greedy-discovery-diagnostics-v1",
        "seeds": list(seeds),
        "teacher": "fixed sparse logistic teacher; 3 pair + 3 triple relations",
        "selection_boundary": (
            "Training data fits candidate models; residual correlations rank edges; "
            "validation is report-only; true support is post-hoc scoring only."
        ),
        "mvp": {
            "summary": aggregate(mvp_records, ("learning_rate", "epochs")),
            "records": mvp_records,
        },
        "structure_discovery": {
            "summary": aggregate(
                structure_records,
                ("learning_rate", "edge_group_l1", "normalized_candidate_scores"),
            ),
            "records": structure_records,
        },
        "claim_boundary": (
            "Finite synthetic six-bit benchmark only; no claim of open-world relation "
            "induction, natural-language reasoning, or production readiness."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="7,17,29")
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--structure-epochs", type=int, default=60)
    args = parser.parse_args()
    seeds = tuple(int(part) for part in args.seeds.split(",") if part.strip())
    report = run_sweep(
        seeds=seeds, samples=args.samples,
        structure_epochs=args.structure_epochs,
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
