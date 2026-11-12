"""Measure the dose-response curve of group sparsity in relation discovery.

The sweep isolates edge_group_l1 while holding the teacher, data protocol,
optimizer, learning rate, rounds, and candidate budget fixed. Validation is
report-only; teacher support is used only for post-hoc precision/recall.
"""
from __future__ import annotations

import itertools
import json
from collections import defaultdict

from prototype.cpg_ei_mvp import CpgEiTransitionModel, make_dataset
from prototype.cpg_ei_structure_discovery import grow_relation_graph

TRUE_SUPPORT = {
    "hyperedge_2_0_1", "hyperedge_2_0_5", "hyperedge_2_2_4",
    "hyperedge_3_0_1_3", "hyperedge_3_0_3_4", "hyperedge_3_1_4_5",
}
DEFAULT_SEEDS = (7, 17, 29, 41, 53)
DEFAULT_PENALTIES = (0.0003, 0.001, 0.003, 0.01, 0.03)


def _score(discovered: set[str], bit_accuracy: float) -> dict:
    overlap = len(discovered & TRUE_SUPPORT)
    return {
        "bit_accuracy": bit_accuracy,
        "support_precision": overlap / len(discovered) if discovered else 0.0,
        "support_recall": overlap / len(TRUE_SUPPORT),
        "active_edges": len(discovered),
        "false_discoveries": len(discovered - TRUE_SUPPORT),
        "exact_support_recovery": discovered == TRUE_SUPPORT,
    }


def _aggregate(records: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in records:
        key = (row["edge_group_l1"], row["normalized_candidate_scores"])
        groups[key].append(row)
    result = []
    for (penalty, normalized), rows in sorted(groups.items()):
        result.append({
            "edge_group_l1": penalty,
            "normalized_candidate_scores": normalized,
            "seeds": len(rows),
            "mean_bit_accuracy": sum(x["bit_accuracy"] for x in rows) / len(rows),
            "mean_support_precision": sum(x["support_precision"] for x in rows) / len(rows),
            "mean_support_recall": sum(x["support_recall"] for x in rows) / len(rows),
            "mean_active_edges": sum(x["active_edges"] for x in rows) / len(rows),
            "mean_false_discoveries": sum(x["false_discoveries"] for x in rows) / len(rows),
            "exact_support_recovery_count": sum(x["exact_support_recovery"] for x in rows),
        })
    return result


def run_sweep(*, seeds=DEFAULT_SEEDS, penalties=DEFAULT_PENALTIES,
              normalized_modes=(False, True), samples=512,
              learning_rate=4.2, epochs_per_round=100, rounds=3):
    if not seeds or not penalties or not normalized_modes:
        raise ValueError("seeds, penalties, and normalization modes must be non-empty")
    if any(value < 0 for value in penalties):
        raise ValueError("group-L1 penalties must be non-negative")
    records = []
    for seed in seeds:
        train = make_dataset(samples, seed=seed, sparse_teacher=True)
        validation = make_dataset(max(128, samples // 4), seed=seed + 100,
                                  sparse_teacher=True)
        for penalty, normalized in itertools.product(penalties, normalized_modes):
            model = CpgEiTransitionModel.create(active_relation_indices=set())
            result = grow_relation_graph(
                model, train, validation,
                rounds=rounds, edges_per_round=3,
                epochs_per_round=epochs_per_round,
                learning_rate=learning_rate, gate_l1=0.01,
                edge_group_l1=penalty,
                normalize_candidate_scores=normalized,
            )
            discovered = set(result["active_edges"])
            records.append({
                "seed": seed,
                "learning_rate": learning_rate,
                "epochs_per_round": epochs_per_round,
                "rounds": rounds,
                "edge_group_l1": penalty,
                "normalized_candidate_scores": normalized,
                **_score(discovered, result["validation"]["bit_accuracy"]),
            })
    return {
        "benchmark": "cpg-ei-group-l1-dose-response-v1",
        "protocol": {
            "seeds": list(seeds), "samples_per_seed": samples,
            "learning_rate": learning_rate, "epochs_per_round": epochs_per_round,
            "rounds": rounds, "penalties": list(penalties),
            "normalized_modes": list(normalized_modes),
            "validation_used_for_selection": False,
            "true_support_used_for_selection": False,
        },
        "records": records,
        "summary": _aggregate(records),
        "claim_boundary": (
            "Finite synthetic six-bit sparse logistic teacher only; no claim of "
            "open-world relation induction or natural-language reasoning."
        ),
    }


def main():
    report = run_sweep()
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
