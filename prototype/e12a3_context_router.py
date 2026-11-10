"""E12-A3-M1.2 Support-context task-structure router benchmark."""
from __future__ import annotations

import argparse
import json
import math
import random
from statistics import mean, stdev
from typing import Any, Sequence

from prototype.e12a3_adaptive_benchmark import (
    ADAPTIVE_FAMILIES,
    _adaptive_allocate,
    _fixed_select,
    _make_pools,
    _score_locked_test,
    _select_on_gate_final,
    make_four_way_world,
)
from prototype.e12a3_multi_proposer import (
    Observation,
    Proposal,
    allocate_equal_budget,
    allocate_round_robin,
)


TASKS = ("THRESHOLD", "PAIRWISE_DIFFERENCE", "PARITY")
METHODS = (
    "STAT", "RELATIONAL", "RANDOM", "BOUNDED_ENUM",
    "EQUAL", "ROUND_ROBIN", "UCB1_MEAN", "SUPPORT_CONTEXT_ROUTER",
)


def split_support_context(
    support: Sequence[Observation], seed: int, context_size: int = 16,
) -> tuple[tuple[Observation, ...], tuple[Observation, ...]]:
    """Stratified split: proposer discovery rows first, context rows second."""
    if context_size < 2 or context_size >= len(support):
        raise ValueError("context_size must be in [2, len(support)-1]")
    groups: dict[int, list[Observation]] = {0: [], 1: []}
    for row in support:
        groups[row.label].append(row)
    rng = random.Random(seed + 8_291)
    for rows in groups.values():
        rng.shuffle(rows)

    counts = {label: len(rows) * context_size / len(support)
              for label, rows in groups.items()}
    allocated = {label: int(counts[label]) for label in groups}
    remainder = context_size - sum(allocated.values())
    order = sorted(groups, key=lambda label: (-(counts[label] - allocated[label]), label))
    for label in order[:remainder]:
        allocated[label] += 1

    context = []
    proposal = []
    for label in (0, 1):
        count = allocated[label]
        context.extend(groups[label][:count])
        proposal.extend(groups[label][count:])
    rng.shuffle(context)
    rng.shuffle(proposal)
    if not context or not proposal:
        raise ValueError("both Support sub-partitions must be non-empty")
    return tuple(proposal), tuple(context)


def _accuracy(proposal: Proposal, rows: Sequence[Observation]) -> float:
    return sum(
        proposal.expression.evaluate(row.as_dict()) == row.label
        for row in rows
    ) / len(rows)


def _context_descriptors(
    pools: dict[str, tuple[Proposal, ...]],
    context_support: Sequence[Observation],
    top_k: int = 3,
    probe_limit: int = 4,
) -> dict[str, float]:
    if top_k < 1 or probe_limit < top_k:
        raise ValueError("probe_limit must be at least top_k")
    scores = {}
    for family in ADAPTIVE_FAMILIES:
        candidate_scores = sorted(
            (_accuracy(p, context_support) for p in pools[family][:probe_limit]),
            reverse=True,
        )
        scores[family] = (
            mean(candidate_scores[:top_k]) if candidate_scores else 0.0
        )
    return scores


def _unique_registry(proposals: Sequence[Proposal]) -> tuple[Proposal, ...]:
    from dataclasses import replace
    registry: dict[str, Proposal] = {}
    for proposal in proposals:
        key = proposal.canonical_expression
        old = registry.get(key)
        if old is None:
            registry[key] = proposal
        else:
            provenance = tuple(sorted(set(
                (old.supporting_families or (old.family,))
                + (proposal.supporting_families or (proposal.family,))
            )))
            registry[key] = replace(old, supporting_families=provenance)
    return tuple(registry.values())


def _context_route_allocate(
    proposal_support: Sequence[Observation],
    context_support: Sequence[Observation],
    seed: int,
    budget: int = 31,
    batch_size: int = 4,
) -> dict[str, Any]:
    """Route by a held-out Support context; no Gate-Dev/Final/Test input."""
    if budget < batch_size * len(ADAPTIVE_FAMILIES):
        raise ValueError("budget must fund one exploration batch per family")
    pools = _make_pools(proposal_support, seed)
    descriptors = _context_descriptors(
        pools, context_support, top_k=3, probe_limit=batch_size
    )
    offsets = {family: 0 for family in ADAPTIVE_FAMILIES}
    emitted: list[Proposal] = []
    trace = []
    allocations = {family: 0 for family in ADAPTIVE_FAMILIES}
    remaining = budget

    # Mandatory exploration: one batch per family, stable family-ID order.
    schedule = [(family, batch_size) for family in ADAPTIVE_FAMILIES]
    while remaining > 0:
        if schedule:
            family, requested = schedule.pop(0)
        else:
            family = sorted(
                ADAPTIVE_FAMILIES,
                key=lambda name: (-descriptors[name], name),
            )[0]
            requested = min(batch_size, remaining)
        requested = min(requested, remaining)
        batch = tuple(pools[family][offsets[family]:offsets[family] + requested])
        if len(batch) != requested:
            raise RuntimeError(f"{family} proposal pool exhausted")
        offsets[family] += len(batch)
        emitted.extend(batch)
        allocations[family] += len(batch)
        remaining -= len(batch)
        trace.append({
            "family": family,
            "slots": len(batch),
            "context_score": descriptors[family],
            "remaining_budget": remaining,
        })

    candidates = _unique_registry(emitted)
    return {
        "candidates": candidates,
        "context_scores": descriptors,
        "allocations": allocations,
        "trace": tuple(trace),
        "proposal_slots_used": budget,
        "candidate_count": len(candidates),
        "context_probe_evaluations": batch_size * len(ADAPTIVE_FAMILIES),
    }


def _paired_clustered(
    episodes: list[dict[str, Any]], method: str, comparator: str = "EQUAL",
) -> dict[str, Any]:
    by_seed: dict[int, list[float]] = {}
    for episode in episodes:
        a = episode["methods"][method]["locked_test_accuracy"]
        b = episode["methods"][comparator]["locked_test_accuracy"]
        by_seed.setdefault(episode["seed"], []).append(a - b)
    clusters = [mean(values) for _, values in sorted(by_seed.items())]
    avg = mean(clusters)
    sd = stdev(clusters) if len(clusters) > 1 else 0.0
    se = sd / math.sqrt(len(clusters)) if clusters else 0.0
    critical = 2.093 if len(clusters) == 20 else 1.96
    return {
        "mean_difference": avg,
        "ci95": [avg - critical * se, avg + critical * se],
        "seed_clusters": len(clusters),
        "wins": sum(x > 0 for x in clusters),
        "ties": sum(x == 0 for x in clusters),
        "losses": sum(x < 0 for x in clusters),
    }


def run_episode(seed: int, task: str, budget: int = 31) -> dict[str, Any]:
    support, gate_dev, gate_final, locked_test = make_four_way_world(seed, task)
    proposal_support, context_support = split_support_context(support, seed)
    pools = _make_pools(proposal_support, seed)
    methods: dict[str, dict[str, Any]] = {}

    for family in ("STAT", "RELATIONAL", "RANDOM", "BOUNDED_ENUM"):
        methods[family] = _fixed_select(
            pools[family], gate_final, locked_test, budget
        )

    equal = allocate_equal_budget(ADAPTIVE_FAMILIES, budget).as_dict()
    equal_candidates = []
    for family in ADAPTIVE_FAMILIES:
        equal_candidates.extend(pools[family][:equal[family]])
    methods["EQUAL"] = _fixed_select(
        equal_candidates, gate_final, locked_test, budget
    )

    rr = allocate_round_robin(
        {family: pools[family] for family in ADAPTIVE_FAMILIES}, budget
    )
    methods["ROUND_ROBIN"] = _fixed_select(rr, gate_final, locked_test, budget)

    ucb = _adaptive_allocate(proposal_support, gate_dev, seed, budget)
    ucb_selection = _select_on_gate_final(ucb["candidates"], gate_final)
    methods["UCB1_MEAN"] = {
        "locked_test_accuracy": _score_locked_test(ucb_selection, locked_test),
        "gate_final_accuracy": ucb_selection["gate_final_accuracy"],
        "candidate_count": ucb_selection["candidate_count"],
        "proposal_slots_used": ucb["proposal_slots_used"],
        "allocations": ucb["allocations"],
        "gate_dev_unique_evaluations": ucb["gate_dev_unique_evaluations"],
    }

    routed = _context_route_allocate(
        proposal_support, context_support, seed, budget
    )
    route_selection = _select_on_gate_final(routed["candidates"], gate_final)
    methods["SUPPORT_CONTEXT_ROUTER"] = {
        "locked_test_accuracy": _score_locked_test(route_selection, locked_test),
        "gate_final_accuracy": route_selection["gate_final_accuracy"],
        "candidate_count": route_selection["candidate_count"],
        "proposal_slots_used": routed["proposal_slots_used"],
        "allocations": routed["allocations"],
        "context_scores": routed["context_scores"],
        "trace": list(routed["trace"]),
        "context_probe_evaluations": routed["context_probe_evaluations"],
    }

    # Context probes are a shared 12-slot data-acquisition overhead, charged
    # equally to every method; only the router uses the resulting descriptor.
    for result in methods.values():
        result["context_probe_evaluations"] = routed["context_probe_evaluations"]

    for name, result in methods.items():
        if result["proposal_slots_used"] != budget:
            raise RuntimeError(f"{name} failed exact budget accounting")
    return {
        "seed": seed, "task": task, "budget": budget,
        "support_sizes": {
            "proposal_support": len(proposal_support),
            "context_support": len(context_support),
        },
        "methods": methods,
    }


def run_benchmark(
    seeds: int = 20, start_seed: int = 1, budget: int = 31,
) -> dict[str, Any]:
    if seeds < 1 or budget < 12:
        raise ValueError("seeds must be positive and budget must fund exploration")
    episodes = [
        run_episode(start_seed + offset, task, budget)
        for task in TASKS
        for offset in range(seeds)
    ]
    aggregate = {}
    for method in METHODS:
        scores = [
            episode["methods"][method]["locked_test_accuracy"]
            for episode in episodes
        ]
        aggregate[method] = {
            "episodes": len(scores),
            "mean_locked_test_accuracy": mean(scores),
            "mean_context_probe_evaluations": mean(
                e["methods"][method]["context_probe_evaluations"]
                for e in episodes
            ),
        }
    paired = {
        method: _paired_clustered(episodes, method)
        for method in ("UCB1_MEAN", "SUPPORT_CONTEXT_ROUTER")
    }
    task_metrics = {}
    for task in TASKS:
        task_episodes = [e for e in episodes if e["task"] == task]
        task_metrics[task] = {
            method: mean(
                e["methods"][method]["locked_test_accuracy"]
                for e in task_episodes
            )
            for method in METHODS
        }
    return {
        "protocol": (
            "Support 64 split into Proposal-Support 48 and Context-Support 16; "
            "Gate-Dev/Gate-Final/Locked-Test remain disjoint; three task families"
        ),
        "seeds_per_task": seeds,
        "start_seed": start_seed,
        "budget_per_method_episode": budget,
        "episode_count": len(episodes),
        "aggregate": aggregate,
        "task_metrics": task_metrics,
        "paired_vs_equal": paired,
        "episodes": episodes,
        "limitations": [
            "Three synthetic task families and a finite hand-specified grammar.",
            "Context descriptor uses only 16 Support rows and may be noisy.",
            "Proposal slots are matched; CPU and wall-clock costs are not.",
            "This is a static Support-context router, not a learned contextual bandit.",
            "API-level separation only; not process-isolated.",
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
