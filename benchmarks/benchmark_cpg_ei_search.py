"""Matched Exact Product vs admissible branch-and-bound search benchmark.

Measures prediction wall time, expansion counters, and upper-bound evaluations.
Candidate generation and model initialization are outside the timed region.
This is a synthetic finite-pool search benchmark, not a language-model benchmark.
"""
from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import time

from prototype.n09_learnable_srok import LearnableSROK, Node, RoleSpec


ROLES = tuple(
    RoleSpec(f"r{index}", frozenset({f"r{index}"}), frozenset({"eligible"}))
    for index in range(3)
)


def build_case(seed: int, pool_size: int, scenario: str):
    rng = random.Random(seed * 1009 + pool_size * 9176 + len(scenario))
    feature_dim = 2
    model = LearnableSROK(ROLES, feature_dim=feature_dim)

    if scenario == "mixed_random":
        model.weights = [rng.uniform(-0.8, 0.8) for _ in model.weights]
        nodes = [
            Node(
                f"{role}-{index:04d}", role,
                (rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)),
                frozenset({"eligible"}),
            )
            for role in ("r0", "r1", "r2")
            for index in range(pool_size)
        ]
    elif scenario == "unary_dominant":
        model.weights = [rng.uniform(-0.015, 0.015) for _ in model.weights]
        for role_index in range(len(ROLES)):
            model.weights[role_index * feature_dim] = 1.0
            model.weights[role_index * feature_dim + 1] = -0.35
        nodes = [
            Node(
                f"{role}-{index:04d}", role,
                (rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)),
                frozenset({"eligible"}),
            )
            for role in ("r0", "r1", "r2")
            for index in range(pool_size)
        ]
    elif scenario == "pure_third_order":
        model.weights = [0.0] * len(model.weights)
        model.weights[-1] = 1.0
        nodes = []
        for role in ("r0", "r1", "r2"):
            nodes.extend(
                Node(
                    f"{role}-{index:04d}", role, (0.0, 0.0),
                    frozenset({"eligible"}),
                )
                for index in range(pool_size - 1)
            )
            nodes.append(
                Node(
                    f"{role}-{pool_size - 1:04d}", role, (0.0, 1.0),
                    frozenset({"eligible"}),
                )
            )
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return model, tuple(nodes)


def _signature(prediction):
    return (
        prediction.abstained,
        prediction.reason,
        tuple(item.role_bindings for item in prediction.candidates),
    )


def measure_strategy(model, nodes, pool_size, strategy, repeats):
    max_expansions = (
        pool_size ** 3
        if strategy == "product"
        else max(10_000, pool_size ** 3 * 4)
    )
    original_bound = model._assignment_upper_bound
    durations = []
    expansion_counts = []
    bound_evaluations = []
    result = None

    for repeat in range(repeats + 1):
        calls = 0

        if strategy == "branch_bound":
            def counted_bound(prefix, pools):
                nonlocal calls
                calls += 1
                return original_bound(prefix, pools)
            model._assignment_upper_bound = counted_bound

        started = time.perf_counter()
        try:
            result = model.predict(
                nodes,
                retrieval_mode="joint",
                search_strategy=strategy,
                max_expansions=max_expansions,
                result_limit=5,
            )
        finally:
            model._assignment_upper_bound = original_bound
        elapsed = time.perf_counter() - started

        if repeat > 0:
            durations.append(elapsed)
            expansion_counts.append(result.expanded_search_states)
            bound_evaluations.append(calls)

    return {
        "prediction": result,
        "median_seconds": statistics.median(durations),
        "median_expanded_search_states": statistics.median(expansion_counts),
        "median_upper_bound_evaluations": statistics.median(bound_evaluations),
    }


def run_benchmark(
    *, pool_sizes=(4, 8, 12, 16), seeds=5, repeats=3,
    scenarios=("mixed_random", "unary_dominant", "pure_third_order"),
):
    rows = []
    for scenario in scenarios:
        for pool_size in pool_sizes:
            for seed in range(11, 11 + seeds):
                model, nodes = build_case(seed, pool_size, scenario)
                exact = measure_strategy(
                    model, nodes, pool_size, "product", repeats
                )
                bounded = measure_strategy(
                    model, nodes, pool_size, "branch_bound", repeats
                )
                if _signature(exact["prediction"]) != _signature(bounded["prediction"]):
                    raise AssertionError(
                        f"branch-bound disagreed with Exact Product: "
                        f"{scenario=}, {pool_size=}, {seed=}"
                    )
                rows.append({
                    "scenario": scenario,
                    "pool_size_per_role": pool_size,
                    "seed": seed,
                    "exact_seconds": exact["median_seconds"],
                    "branch_bound_seconds": bounded["median_seconds"],
                    "wall_time_ratio": (
                        bounded["median_seconds"] / exact["median_seconds"]
                    ),
                    "exact_expanded_states": exact["median_expanded_search_states"],
                    "branch_bound_expanded_states": bounded["median_expanded_search_states"],
                    "expansion_count_ratio": (
                        bounded["median_expanded_search_states"]
                        / exact["median_expanded_search_states"]
                    ),
                    "upper_bound_evaluations": bounded["median_upper_bound_evaluations"],
                    "exact_agreement": True,
                })

    summaries = []
    for scenario in scenarios:
        for pool_size in pool_sizes:
            subset = [
                row for row in rows
                if row["scenario"] == scenario
                and row["pool_size_per_role"] == pool_size
            ]
            summaries.append({
                "scenario": scenario,
                "pool_size_per_role": pool_size,
                "seed_count": len(subset),
                "median_exact_seconds": round(
                    statistics.median(row["exact_seconds"] for row in subset), 6
                ),
                "median_branch_bound_seconds": round(
                    statistics.median(row["branch_bound_seconds"] for row in subset), 6
                ),
                "median_wall_time_ratio": round(
                    statistics.median(row["wall_time_ratio"] for row in subset), 4
                ),
                "median_expansion_count_ratio": round(
                    statistics.median(row["expansion_count_ratio"] for row in subset), 4
                ),
                "median_upper_bound_evaluations": round(
                    statistics.median(row["upper_bound_evaluations"] for row in subset), 1
                ),
                "all_exact": all(row["exact_agreement"] for row in subset),
            })

    return {
        "benchmark": "cpg_ei_exact_vs_admissible_branch_bound",
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        },
        "measurement_scope": (
            "model.predict wall time; candidate generation and model initialization "
            "excluded; branch-bound upper-bound calculations included in elapsed time"
        ),
        "repeats_per_strategy": repeats,
        "warmup_runs_per_strategy": 1,
        "scenarios": list(scenarios),
        "summaries": summaries,
        "raw": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[4, 8, 12, 16])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if any(size < 2 for size in args.sizes):
        parser.error("every pool size must be at least two")
    if args.seeds < 1 or args.repeats < 1:
        parser.error("seeds and repeats must be positive")
    print(json.dumps(
        run_benchmark(
            pool_sizes=tuple(args.sizes),
            seeds=args.seeds,
            repeats=args.repeats,
        ),
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
