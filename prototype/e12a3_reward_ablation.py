"""E12-A3-M1.1 reward-function ablation under four-way data isolation."""
from __future__ import annotations

import argparse
import json
import math
from statistics import mean, stdev
from typing import Any

from prototype.e12a3_adaptive_benchmark import (
    _adaptive_allocate,
    _score_locked_test,
    _select_on_gate_final,
    make_four_way_world,
    run_episode,
)
from prototype.e12a3_multi_proposer import Proposal


REWARD_MODES = ("MEAN", "MAX", "TOP2_MEAN", "DELTA_BEST", "MEAN_NOVELTY")
CONTROL_METHODS = ("EQUAL", "ROUND_ROBIN", "BOUNDED_ENUM", "RELATIONAL")


def _adaptive_result(
    support, gate_dev, gate_final, locked_test, seed: int,
    budget: int, reward_mode: str,
) -> dict[str, Any]:
    allocation = _adaptive_allocate(
        support, gate_dev, seed, budget=budget, reward_mode=reward_mode,
    )
    selection = _select_on_gate_final(allocation["candidates"], gate_final)
    locked_score = _score_locked_test(selection, locked_test)
    return {
        "selected": selection.get("selected"),
        "selected_family": selection.get("selected_family"),
        "selected_families": selection.get("selected_families", []),
        "gate_final_accuracy": selection.get("gate_final_accuracy"),
        "locked_test_accuracy": locked_score,
        "candidate_count": selection["candidate_count"],
        "proposal_slots_used": allocation["proposal_slots_used"],
        "gate_dev_unique_evaluations": allocation["gate_dev_unique_evaluations"],
        "gate_final_unique_evaluations": allocation["gate_final_unique_evaluations"],
        "allocations": allocation["allocations"],
        "trace": list(allocation["trace"]),
        "reward_mode": reward_mode,
    }


def _clustered_difference(
    episodes: list[dict[str, Any]], method: str, comparator: str,
) -> dict[str, Any]:
    by_seed: dict[int, list[float]] = {}
    for episode in episodes:
        left = episode["methods"][method]["locked_test_accuracy"]
        right = episode["methods"][comparator]["locked_test_accuracy"]
        by_seed.setdefault(episode["seed"], []).append(left - right)
    cluster_means = [mean(values) for _, values in sorted(by_seed.items())]
    avg = mean(cluster_means)
    sd = stdev(cluster_means) if len(cluster_means) > 1 else 0.0
    se = sd / math.sqrt(len(cluster_means)) if cluster_means else 0.0
    # Conservative two-sided 95% t critical for 20 clusters (df=19).
    critical = 2.093 if len(cluster_means) == 20 else 1.96
    return {
        "mean_difference": avg,
        "ci95": [avg - critical * se, avg + critical * se],
        "seed_clusters": len(cluster_means),
        "wins": sum(value > 0 for value in cluster_means),
        "ties": sum(value == 0 for value in cluster_means),
        "losses": sum(value < 0 for value in cluster_means),
    }


def run_episode(seed: int, task: str, budget: int = 31) -> dict[str, Any]:
    support, gate_dev, gate_final, locked_test = make_four_way_world(seed, task)
    # run_episode supplies fixed controls and the current MEAN reward baseline.
    baseline = run_episode.__globals__["run_episode"](seed, task, budget)
    methods = {
        name: baseline["methods"][name]
        for name in ("STAT", "RELATIONAL", "RANDOM", "BOUNDED_ENUM",
                     "EQUAL", "ROUND_ROBIN", "UCB1_ADAPTIVE")
    }
    for mode in REWARD_MODES:
        if mode == "MEAN":
            continue
        methods[f"UCB1_{mode}"] = _adaptive_result(
            support, gate_dev, gate_final, locked_test, seed, budget, mode,
        )
    for name, result in methods.items():
        if result["proposal_slots_used"] != budget:
            raise RuntimeError(
                f"{name} consumed {result['proposal_slots_used']} of {budget} slots"
            )
    return {"seed": seed, "task": task, "budget": budget, "methods": methods}


def run_benchmark(
    seeds: int = 20, start_seed: int = 1, budget: int = 31,
) -> dict[str, Any]:
    if seeds < 1 or budget < 1:
        raise ValueError("seeds and budget must be positive")
    episodes = [
        run_episode(start_seed + offset, task, budget)
        for task in ("THRESHOLD", "PAIRWISE_DIFFERENCE")
        for offset in range(seeds)
    ]
    method_names = list(episodes[0]["methods"])
    aggregate = {}
    for method in method_names:
        values = [episode["methods"][method] for episode in episodes]
        scores = [value["locked_test_accuracy"] for value in values]
        aggregate[method] = {
            "episodes": len(values),
            "mean_locked_test_accuracy": mean(scores),
            "mean_proposal_slots": mean(v["proposal_slots_used"] for v in values),
            "mean_gate_dev_unique_evaluations": mean(
                v.get("gate_dev_unique_evaluations", 0) for v in values
            ),
            "mean_gate_final_unique_evaluations": mean(
                v.get("gate_final_unique_evaluations", 0) for v in values
            ),
        }
    paired = {
        method: _clustered_difference(episodes, method, "EQUAL")
        for method in method_names
        if method.startswith("UCB1_") or method == "UCB1_ADAPTIVE"
    }
    return {
        "protocol": "four-way split; 20-seed x 2-task reward ablation; exact proposal-slot budget",
        "seeds_per_task": seeds,
        "start_seed": start_seed,
        "budget_per_method_episode": budget,
        "episode_count": len(episodes),
        "aggregate": aggregate,
        "paired_vs_equal": paired,
        "episodes": episodes,
        "reward_modes": list(REWARD_MODES),
        "limitations": [
            "Two synthetic task families only.",
            "Finite hand-specified proposer pools.",
            "Gate-Dev rewards are adaptive and may be overfit; Gate-Final is held for one-time selection.",
            "UCB1 is a finite-pool heuristic with non-stationary rewards, not a stationary-bandit regret guarantee.",
            "Proposal slots are matched; CPU and wall-clock costs are not.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument("--budget", type=int, default=31)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    print(json.dumps(
        run_benchmark(args.seeds, args.start_seed, args.budget),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
