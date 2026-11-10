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
    "EQUAL", "ROUND_ROBIN", "UCB1_MEAN",
    "SUPPORT_CONTEXT_ROUTER", "SUPPORT_CONTEXT_ROUTER_STRATIFIED",
    "SUPPORT_CONTEXT_ROUTER_STRATIFIED_TOP2",
    "SUPPORT_CONTEXT_ROUTER_STRATIFIED_MAX",
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


def _random_probe_candidates(
    pools: dict[str, tuple[Proposal, ...]], batch_size: int = 4,
) -> dict[str, tuple[Proposal, ...]]:
    return {
        family: tuple(pools[family][:batch_size])
        for family in ADAPTIVE_FAMILIES
    }


def _balanced_probe_candidates(
    pools: dict[str, tuple[Proposal, ...]], batch_size: int = 4,
) -> dict[str, tuple[Proposal, ...]]:
    """Choose operator-diverse probes, then distinct feature-role candidates."""
    result = {}
    for family in ADAPTIVE_FAMILIES:
        proposals = list(pools[family])
        chosen: list[Proposal] = []
        seen_operators = set()
        for proposal in proposals:
            operator = proposal.expression.operator
            if operator not in seen_operators:
                chosen.append(proposal)
                seen_operators.add(operator)
            if len(chosen) == batch_size:
                break

        seen_roles = {
            (p.expression.feature, p.expression.other_feature)
            for p in chosen
        }
        if len(chosen) < batch_size:
            for proposal in proposals:
                role = (proposal.expression.feature,
                        proposal.expression.other_feature)
                if proposal not in chosen and role not in seen_roles:
                    chosen.append(proposal)
                    seen_roles.add(role)
                if len(chosen) == batch_size:
                    break

        if len(chosen) < batch_size:
            for proposal in proposals:
                if proposal not in chosen:
                    chosen.append(proposal)
                if len(chosen) == batch_size:
                    break
        if len(chosen) != batch_size:
            raise RuntimeError(f"{family} cannot supply {batch_size} context probes")
        result[family] = tuple(chosen)
    return result


def _context_descriptors(
    probes: dict[str, tuple[Proposal, ...]],
    context_support: Sequence[Observation],
    top_k: int = 3,
    aggregation: str = "TOP3_MEAN",
) -> dict[str, float]:
    if aggregation not in ("TOP3_MEAN", "TOP2_MEAN", "MAX"):
        raise ValueError("unsupported context aggregation")
    scores = {}
    for family in ADAPTIVE_FAMILIES:
        candidate_scores = sorted(
            (_accuracy(p, context_support) for p in probes[family]),
            reverse=True,
        )
        if not candidate_scores:
            scores[family] = 0.0
        elif aggregation == "MAX":
            scores[family] = max(candidate_scores)
        elif aggregation == "TOP2_MEAN":
            scores[family] = mean(candidate_scores[:2])
        else:
            scores[family] = mean(candidate_scores[:top_k])
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
    pools: dict[str, tuple[Proposal, ...]],
    descriptors: dict[str, float],
    probes: dict[str, tuple[Proposal, ...]],
    budget: int = 31,
    batch_size: int = 4,
    probe_strategy: str = "RANDOM",
) -> dict[str, Any]:
    """Route from precomputed Support context; no Gate/Test input."""
    if budget < batch_size * len(ADAPTIVE_FAMILIES):
        raise ValueError("budget must fund one exploration batch per family")
    if set(descriptors) != set(ADAPTIVE_FAMILIES):
        raise ValueError("context descriptors must cover every proposer family")
    if set(probes) != set(ADAPTIVE_FAMILIES) or any(
        len(probes[name]) != batch_size for name in ADAPTIVE_FAMILIES
    ):
        raise ValueError("each family must have exactly one full probe batch")

    emitted: list[Proposal] = []
    trace = []
    allocations = {family: 0 for family in ADAPTIVE_FAMILIES}
    remaining = budget

    # The context probes are also the mandatory exploration batch.
    for family in ADAPTIVE_FAMILIES:
        batch = probes[family]
        emitted.extend(batch)
        allocations[family] += len(batch)
        remaining -= len(batch)
        trace.append({
            "family": family, "slots": len(batch),
            "context_score": descriptors[family],
            "probe_strategy": probe_strategy,
            "remaining_budget": remaining,
        })

    probe_ids = {
        family: {proposal.proposal_id for proposal in probes[family]}
        for family in ADAPTIVE_FAMILIES
    }
    queues = {
        family: [
            proposal for proposal in pools[family]
            if proposal.proposal_id not in probe_ids[family]
        ]
        for family in ADAPTIVE_FAMILIES
    }
    offsets = {family: 0 for family in ADAPTIVE_FAMILIES}

    while remaining > 0:
        family = sorted(
            ADAPTIVE_FAMILIES,
            key=lambda name: (-descriptors[name], name),
        )[0]
        requested = min(batch_size, remaining)
        batch = tuple(queues[family][offsets[family]:offsets[family] + requested])
        if len(batch) != requested:
            raise RuntimeError(f"{family} proposal pool exhausted")
        offsets[family] += len(batch)
        emitted.extend(batch)
        allocations[family] += len(batch)
        remaining -= len(batch)
        trace.append({
            "family": family, "slots": len(batch),
            "context_score": descriptors[family],
            "probe_strategy": "ROUTED_REMAINDER",
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
        "context_probe_evaluations": sum(
            len(probes[family]) for family in ADAPTIVE_FAMILIES
        ),
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
    # Compare random and grammar-stratified probes under the same 12-evaluation
    # Support-context budget. Each probe batch is also the exploration batch.
    random_probes = _random_probe_candidates(pools, batch_size=4)
    random_context_scores = _context_descriptors(
        random_probes, context_support, top_k=3
    )
    stratified_probes = _balanced_probe_candidates(pools, batch_size=4)
    stratified_context_scores = _context_descriptors(
        stratified_probes, context_support, top_k=3,
        aggregation="TOP3_MEAN",
    )
    stratified_top2_scores = _context_descriptors(
        stratified_probes, context_support, aggregation="TOP2_MEAN",
    )
    stratified_max_scores = _context_descriptors(
        stratified_probes, context_support, aggregation="MAX",
    )
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
        pools, random_context_scores, random_probes, budget,
        probe_strategy="RANDOM",
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

    stratified = _context_route_allocate(
        pools, stratified_context_scores, stratified_probes, budget,
        probe_strategy="GRAMMAR_STRATIFIED",
    )
    stratified_selection = _select_on_gate_final(
        stratified["candidates"], gate_final
    )
    methods["SUPPORT_CONTEXT_ROUTER_STRATIFIED"] = {
        "locked_test_accuracy": _score_locked_test(stratified_selection, locked_test),
        "gate_final_accuracy": stratified_selection["gate_final_accuracy"],
        "candidate_count": stratified_selection["candidate_count"],
        "proposal_slots_used": stratified["proposal_slots_used"],
        "allocations": stratified["allocations"],
        "context_scores": stratified["context_scores"],
        "trace": list(stratified["trace"]),
        "context_probe_evaluations": stratified["context_probe_evaluations"],
    }

    stratified_top2 = _context_route_allocate(
        pools, stratified_top2_scores, stratified_probes, budget,
        probe_strategy="GRAMMAR_STRATIFIED_TOP2_MEAN",
    )
    top2_selection = _select_on_gate_final(
        stratified_top2["candidates"], gate_final
    )
    methods["SUPPORT_CONTEXT_ROUTER_STRATIFIED_TOP2"] = {
        "locked_test_accuracy": _score_locked_test(top2_selection, locked_test),
        "gate_final_accuracy": top2_selection["gate_final_accuracy"],
        "candidate_count": top2_selection["candidate_count"],
        "proposal_slots_used": stratified_top2["proposal_slots_used"],
        "allocations": stratified_top2["allocations"],
        "context_scores": stratified_top2["context_scores"],
        "trace": list(stratified_top2["trace"]),
        "context_probe_evaluations": stratified_top2["context_probe_evaluations"],
    }

    stratified_max = _context_route_allocate(
        pools, stratified_max_scores, stratified_probes, budget,
        probe_strategy="GRAMMAR_STRATIFIED_MAX",
    )
    max_selection = _select_on_gate_final(
        stratified_max["candidates"], gate_final
    )
    methods["SUPPORT_CONTEXT_ROUTER_STRATIFIED_MAX"] = {
        "locked_test_accuracy": _score_locked_test(max_selection, locked_test),
        "gate_final_accuracy": max_selection["gate_final_accuracy"],
        "candidate_count": max_selection["candidate_count"],
        "proposal_slots_used": stratified_max["proposal_slots_used"],
        "allocations": stratified_max["allocations"],
        "context_scores": stratified_max["context_scores"],
        "trace": list(stratified_max["trace"]),
        "context_probe_evaluations": stratified_max["context_probe_evaluations"],
    }

    # Each policy variant uses the same 12-evaluation context-probe budget.
    shared_probe_cost = 12
    for result in methods.values():
        result["context_probe_evaluations"] = shared_probe_cost

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
        for method in ("UCB1_MEAN", "SUPPORT_CONTEXT_ROUTER",
                       "SUPPORT_CONTEXT_ROUTER_STRATIFIED",
                       "SUPPORT_CONTEXT_ROUTER_STRATIFIED_TOP2",
                       "SUPPORT_CONTEXT_ROUTER_STRATIFIED_MAX")
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
