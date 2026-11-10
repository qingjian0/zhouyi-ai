"""E12-A3 preliminary equal-budget proposer benchmark.

Evaluator-side world generation and Locked Test scoring live in this module.
Proposal functions receive only Support observations. Gate selects; Test scores once.
This is a small synthetic protocol check, not a general benchmark.
"""
from __future__ import annotations

import argparse
import json
import random
from statistics import mean
from typing import Any, Sequence

from prototype.e12a3_multi_proposer import (
    Observation,
    Proposal,
    allocate_round_robin,
    propose_exhaustive,
    propose_random,
    propose_relational,
    propose_statistical,
)


FAMILIES = ("STAT", "RELATIONAL", "RANDOM", "EXHAUSTIVE", "PORTFOLIO")


def _make_world(seed: int, task: str) -> tuple[tuple[Observation, ...], tuple[Observation, ...], tuple[Observation, ...]]:
    if task not in ("THRESHOLD", "PAIRWISE_DIFFERENCE"):
        raise ValueError("unsupported task")
    rng = random.Random(seed)
    rows = []
    for i in range(90):
        x = rng.randrange(10)
        y = rng.randrange(10)
        z = max(0, min(9, x + rng.choice((-2, -1, 0, 1, 2))))
        label = int(x >= 6) if task == "THRESHOLD" else int(x - y >= 3)
        rows.append(Observation(
            f"{task.lower()}-{seed}-{i:03d}",
            (("x", x), ("y", y), ("z", z)),
            label,
        ))
    rng.shuffle(rows)
    return tuple(rows[:45]), tuple(rows[45:68]), tuple(rows[68:])


def _accuracy(proposal: Proposal, rows: Sequence[Observation]) -> float:
    return sum(proposal.expression.evaluate(row.as_dict()) == row.label
               for row in rows) / len(rows)


def _choose_on_gate(candidates: Sequence[Proposal],
                    support: Sequence[Observation],
                    gate: Sequence[Observation]) -> tuple[Proposal | None, float | None, int]:
    # Exact Support consistency is a deliberately strict first baseline.
    screened = [p for p in candidates if _accuracy(p, support) == 1.0]
    if not screened:
        return None, None, 0
    ranked = sorted(screened, key=lambda p: (-_accuracy(p, gate),
                                             p.canonical_expression, p.family))
    selected = ranked[0]
    return selected, _accuracy(selected, gate), len(screened)


def _budgeted_family_pools(support: Sequence[Observation], seed: int) -> dict[str, tuple[Proposal, ...]]:
    return {
        "STAT": propose_statistical(support),
        "RELATIONAL": propose_relational(support),
        "RANDOM": propose_random(support, seed=seed + 100_003, count=160),
        "EXHAUSTIVE": propose_exhaustive(support, limit=512),
    }


def run_episode(seed: int, task: str, budget: int = 32) -> dict[str, Any]:
    support, gate, test = _make_world(seed, task)
    pools = _budgeted_family_pools(support, seed)
    methods: dict[str, tuple[Proposal, ...]] = {}
    for family, proposals in pools.items():
        methods[family] = tuple(proposals[:budget])
    methods["PORTFOLIO"] = allocate_round_robin(pools, budget)

    results = {}
    for method, candidates in methods.items():
        selected, gate_accuracy, screened_count = _choose_on_gate(candidates, support, gate)
        test_accuracy = _accuracy(selected, test) if selected is not None else None
        results[method] = {
            "candidate_budget_used": len(candidates),
            "support_consistent_count": screened_count,
            "selected_family": selected.family if selected else None,
            "gate_accuracy": gate_accuracy,
            "locked_test_accuracy": test_accuracy,
            "abstained": selected is None,
        }
    return {"seed": seed, "task": task, "budget": budget, "methods": results}


def run_benchmark(seeds: int = 20, start_seed: int = 1,
                  budget: int = 32) -> dict[str, Any]:
    if seeds < 1 or budget < 1:
        raise ValueError("seeds and budget must be positive")
    episodes = [
        run_episode(start_seed + offset, task, budget)
        for task in ("THRESHOLD", "PAIRWISE_DIFFERENCE")
        for offset in range(seeds)
    ]
    aggregate = {}
    for method in FAMILIES:
        values = [ep["methods"][method] for ep in episodes]
        covered = [v["locked_test_accuracy"] for v in values
                   if v["locked_test_accuracy"] is not None]
        aggregate[method] = {
            "episodes": len(values),
            "coverage": len(covered) / len(values),
            "mean_locked_test_accuracy_when_selected": mean(covered) if covered else None,
            "mean_support_consistent_candidates": mean(
                v["support_consistent_count"] for v in values
            ),
            "mean_gate_accuracy_when_selected": mean(
                v["gate_accuracy"] for v in values if v["gate_accuracy"] is not None
            ) if covered else None,
        }
    return {
        "protocol": "E12-A3 equal proposal-slot budget; exact Support screen; Gate selection; one-time Locked Test",
        "seeds_per_task": seeds,
        "start_seed": start_seed,
        "budget_per_method_episode": budget,
        "episode_count": len(episodes),
        "aggregate": aggregate,
        "episodes": episodes,
        "limitations": [
            "Synthetic two-task benchmark only.",
            "Proposal slots are matched; CPU operations and wall-clock costs are not yet matched.",
            "The current methods share a small hand-specified predicate grammar.",
            "Locked Test is evaluator-side and is not used for candidate selection.",
            "Results do not establish generalization beyond these world generators.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument("--budget", type=int, default=32)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.seeds, args.start_seed, args.budget)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
