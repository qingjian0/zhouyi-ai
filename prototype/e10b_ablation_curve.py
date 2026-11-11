"""E10-B.2 multi-seed positive-evidence ablation curve.

For each seed and relation, retain a deterministic random subset of positive
Support observations at fixed fractions while preserving every negative row.
Score the same object-disjoint Query split at every fraction. This is a
controlled evidence-sensitivity stress test, not a population estimate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import statistics
from typing import Any

from prototype.e10a_finite_relational_learner import FiniteRelationalVersionSpace
from prototype.e10a_object_disjoint import build_object_disjoint_task


DEFAULT_FRACTIONS = (1.0, 0.75, 0.5, 0.25, 0.0)


def _score(rows: list[dict[str, Any]], truth: dict[str, bool]) -> dict[str, Any]:
    covered = [row for row in rows if row["prediction"] is not None]
    correct = sum(row["prediction"] is truth[row["observation_id"]] for row in covered)
    total = len(rows)
    counts = {
        status: sum(row["decision_status"] == status for row in rows)
        for status in sorted({row["decision_status"] for row in rows})
    }
    return {
        "n": total,
        "covered": len(covered),
        "correct_covered": correct,
        "coverage": len(covered) / total if total else 0.0,
        "selective_accuracy": correct / len(covered) if covered else None,
        "strict_accuracy": correct / total if total else 0.0,
        "abstention_rate": 1 - len(covered) / total if total else 0.0,
        "decision_counts": counts,
    }


def _seed_for(seed: int, fraction: float, relation: str) -> int:
    raw = f"e10b2-positive-ablation-v1:{seed}:{fraction:.4f}:{relation}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _retain_positive_rows(
    observations: list[dict[str, Any]], *, seed: int, fraction: float
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    relations = sorted({row["relation_symbol"] for row in observations})
    retained_ids: set[str] = set()
    counts: dict[str, dict[str, int]] = {}
    for relation in relations:
        positives = [
            row for row in observations
            if row["relation_symbol"] == relation and row["outcome"] is True
        ]
        rng = random.Random(_seed_for(seed, fraction, relation))
        shuffled_ids = sorted(row["observation_id"] for row in positives)
        rng.shuffle(shuffled_ids)
        keep_count = int(len(shuffled_ids) * fraction)
        retained_ids.update(shuffled_ids[:keep_count])
        counts[relation] = {
            "original_positive": len(positives),
            "retained_positive": keep_count,
        }
    retained = [
        row for row in observations
        if row["outcome"] is False or row["observation_id"] in retained_ids
    ]
    return retained, counts


def run_seed(
    seed: int, *, instances_per_template: int = 6,
    fractions: tuple[float, ...] = DEFAULT_FRACTIONS,
) -> dict[str, Any]:
    support, query, truth_payload = build_object_disjoint_task(
        seed, instances_per_template=instances_per_template
    )
    truth = {row["observation_id"]: row["valid"]
             for row in truth_payload["query_truth"]}
    learner_support = {
        key: support[key]
        for key in ("schema_version", "phase", "objects", "observations")
    }
    curve: dict[str, Any] = {}
    for fraction in fractions:
        ablated = copy.deepcopy(learner_support)
        ablated_rows, retained_counts = _retain_positive_rows(
            ablated["observations"], seed=seed, fraction=fraction
        )
        ablated["observations"] = ablated_rows
        learner = FiniteRelationalVersionSpace().fit(ablated)
        objects = {row["object_id"]: row for row in query["objects"]}
        predictions = [
            learner.predict(
                row, [objects[object_id] for object_id in row["participants"]]
            )
            for row in query["observations"]
        ]
        report = learner.snapshot()["report"]
        curve[f"{fraction:.2f}"] = {
            "metrics": _score(predictions, truth),
            "support_rows": len(ablated_rows),
            "retained_positive_support": sum(
                item["retained_positive"] for item in retained_counts.values()
            ),
            "original_positive_support": sum(
                item["original_positive"] for item in retained_counts.values()
            ),
            "per_relation_support": retained_counts,
            "version_space_size": report["consistent_candidate_count"],
            "candidate_universe_size": report["candidate_universe_size"],
            "candidate_generation_evaluations": report[
                "candidate_generation_evaluations"
            ],
            "prediction_rule_match_evaluations": sum(
                row["compute_cost"]["rule_match_evaluations"]
                for row in predictions
            ),
        }
    return {
        "seed": seed,
        "instances_per_template": instances_per_template,
        "curve": curve,
    }


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "std": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


def run_sweep(
    *, seeds: int = 20, start_seed: int = 200,
    instances_per_template: int = 6,
    fractions: tuple[float, ...] = DEFAULT_FRACTIONS,
) -> dict[str, Any]:
    if not isinstance(seeds, int) or isinstance(seeds, bool) or seeds < 1:
        raise ValueError("seeds must be a positive integer")
    if not isinstance(start_seed, int) or isinstance(start_seed, bool):
        raise ValueError("start_seed must be an integer")
    if not fractions or any(not 0.0 <= value <= 1.0 for value in fractions):
        raise ValueError("fractions must be a non-empty sequence in [0, 1]")
    runs = [
        run_seed(start_seed + offset,
                 instances_per_template=instances_per_template,
                 fractions=fractions)
        for offset in range(seeds)
    ]
    aggregate: dict[str, Any] = {}
    for fraction in fractions:
        key = f"{fraction:.2f}"
        metrics = [run["curve"][key]["metrics"] for run in runs]
        aggregate[key] = {
            metric: _distribution([
                float(item[metric]) for item in metrics if item[metric] is not None
            ])
            for metric in (
                "coverage", "selective_accuracy", "strict_accuracy",
                "abstention_rate",
            )
        }
        for metric in (
            "retained_positive_support", "version_space_size",
            "candidate_generation_evaluations",
            "prediction_rule_match_evaluations",
        ):
            aggregate[key][metric] = _distribution([
                float(run["curve"][key][metric]) for run in runs
            ])
    return {
        "experiment": "E10-B.2 multi-seed positive-support ablation curve",
        "seeds": [run["seed"] for run in runs],
        "instances_per_template": instances_per_template,
        "fractions": list(fractions),
        "aggregate": aggregate,
        "per_seed": runs,
        "method": {
            "sampling": "deterministic random subset independently per seed and relation",
            "negative_support": "all negative Support observations are retained",
            "query": "identical untouched object-disjoint Query split at every fraction",
            "scoring": "coverage, selective accuracy, strict accuracy, abstention",
            "compute": "candidate generation and prediction rule-match evaluations reported separately",
        },
        "limitations": [
            "Synthetic generator and finite DSL remain matched; this is not open-world transfer.",
            "Ablation is a controlled stress test, not a population sampling estimate.",
            "Selective accuracy is undefined when coverage is zero and is excluded from its aggregate.",
            "No causal claim about real-world learning follows from this synthetic evidence curve.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=200)
    parser.add_argument("--instances-per-template", type=int, default=6)
    args = parser.parse_args()
    print(json.dumps(run_sweep(
        seeds=args.seeds, start_seed=args.start_seed,
        instances_per_template=args.instances_per_template,
    ), indent=2, ensure_ascii=False))
