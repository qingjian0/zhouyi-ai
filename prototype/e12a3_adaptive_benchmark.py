"""E12-A3-M1: four-way, Gate-Dev-adaptive proposer budget benchmark.

This is a finite-pool UCB1-inspired heuristic experiment, not a claim of
classical stationary-bandit regret guarantees. Gate-Final and Locked Test
are intentionally absent from the adaptive allocation function.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import replace
from statistics import mean
from typing import Any, Sequence

from prototype.e12a3_adaptive_allocator import UCB1Allocator
from prototype.e12a3_multi_proposer import (
    Observation,
    Proposal,
    allocate_equal_budget,
    allocate_round_robin,
    propose_exhaustive,
    propose_random,
    propose_relational,
    propose_statistical,
    validate_observations,
)


ADAPTIVE_FAMILIES = ("STAT", "RELATIONAL", "RANDOM")
METHODS = ("STAT", "RELATIONAL", "RANDOM", "BOUNDED_ENUM",
           "EQUAL", "ROUND_ROBIN", "UCB1_ADAPTIVE")


def make_four_way_world(
    seed: int, task: str,
) -> tuple[tuple[Observation, ...], tuple[Observation, ...],
           tuple[Observation, ...], tuple[Observation, ...]]:
    """Generate disjoint Support/Gate-Dev/Gate-Final/Locked-Test partitions."""
    if task not in ("THRESHOLD", "PAIRWISE_DIFFERENCE"):
        raise ValueError("unsupported task")
    rng = random.Random(seed)
    rows = []
    for i in range(160):
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
    # 64 / 32 / 32 / 32; all splits are disjoint and fixed before learning.
    splits = (tuple(rows[:64]), tuple(rows[64:96]),
              tuple(rows[96:128]), tuple(rows[128:]))
    for split in splits:
        validate_observations(split)
    return splits


def _accuracy(proposal: Proposal, rows: Sequence[Observation]) -> float:
    return sum(
        proposal.expression.evaluate(row.as_dict()) == row.label
        for row in rows
    ) / len(rows)


def _make_pools(
    support: Sequence[Observation], seed: int,
) -> dict[str, tuple[Proposal, ...]]:
    """The proposal generators receive Support only, never Gate/Test data."""
    raw = {
        "STAT": propose_statistical(support),
        "RELATIONAL": propose_relational(support),
        "RANDOM": propose_random(support, seed=seed + 100_003, count=192),
        "BOUNDED_ENUM": propose_exhaustive(support, limit=512),
    }
    offsets = {"STAT": 11, "RELATIONAL": 23,
               "RANDOM": 37, "BOUNDED_ENUM": 53}
    shuffled = {}
    for family, proposals in raw.items():
        family_rng = random.Random(seed * 1_000_003 + offsets[family])
        items = list(proposals)
        family_rng.shuffle(items)
        shuffled[family] = tuple(items)
    return shuffled


def _take_batch(
    queue: Sequence[Proposal], offset: int, batch_size: int,
) -> tuple[Proposal, ...]:
    return tuple(queue[offset:offset + batch_size])


def _adaptive_allocate(
    support: Sequence[Observation],
    gate_dev: Sequence[Observation],
    seed: int,
    budget: int = 31,
    batch_size: int = 4,
    exploration_floor: int = 1,
    exploration_constant: float = 0.3,
) -> dict[str, Any]:
    """Allocate only from Support pools and Gate-Dev feedback.

    No Gate-Final or Locked-Test argument exists at this boundary.
    Each emitted proposal consumes one proposal slot. A duplicate expression
    consumes its proposal slot but is Gate-Dev-evaluated only once; subsequent
    emitters receive zero novelty reward for that duplicate.
    """
    if budget < 1 or batch_size < 1:
        raise ValueError("budget and batch_size must be positive")
    pools = _make_pools(support, seed)
    # Keep each family's raw queue. Shared expressions are deduplicated in the
    # candidate registry after emission, not assigned to a lexical owner arm.
    queues = {
        family: list(pools.get(family, ()))
        for family in ADAPTIVE_FAMILIES
    }
    offsets = {family: 0 for family in ADAPTIVE_FAMILIES}
    allocator = UCB1Allocator(
        ADAPTIVE_FAMILIES, budget, batch_size,
        exploration_floor, exploration_constant,
    )
    registry: dict[str, Proposal] = {}
    evaluated_gate_dev: dict[str, float] = {}
    trace: list[dict[str, Any]] = []
    slots_used = 0

    while slots_used < budget:
        family = allocator.choose_next_family()
        if family is None:
            break
        pending = allocator.pending
        assert pending is not None
        _, requested = pending
        batch = _take_batch(queues[family], offsets[family], requested)
        offsets[family] += len(batch)
        if batch and len(batch) != requested:
            raise RuntimeError(f"{family} pool cannot fill its requested batch")
        # The proposer invocation is budgeted by requested slots. If a pool is
        # exhausted, the unused slots are not silently reassigned.
        if not batch:
            allocator.observe_batch(family, 0.0, used_slots=requested)
            slots_used += requested
            trace.append({
                "family": family, "requested_slots": requested,
                "emitted": 0, "new_unique": 0, "reward": 0.0,
                "remaining_budget": allocator.remaining_budget,
            })
            continue

        newly_evaluated = []
        for proposal in batch:
            expression = proposal.canonical_expression
            existing = registry.get(expression)
            if existing is None:
                registry[expression] = proposal
            else:
                # Preserve multi-source provenance without adding a second
                # candidate identity or a second Gate-Dev evaluation.
                families = tuple(sorted(set(
                    (existing.supporting_families or (existing.family,))
                    + (proposal.supporting_families or (proposal.family,))
                )))
                from dataclasses import replace
                registry[expression] = replace(
                    existing, supporting_families=families
                )
            if expression not in evaluated_gate_dev:
                evaluated_gate_dev[expression] = _accuracy(proposal, gate_dev)
                newly_evaluated.append(expression)

        # Reward is the mean Gate-Dev score of newly evaluated unique proposals.
        # A batch containing only duplicates receives zero novelty reward.
        reward = (
            mean(evaluated_gate_dev[key] for key in newly_evaluated)
            if newly_evaluated else 0.0
        )
        allocator.observe_batch(family, reward, used_slots=len(batch))
        slots_used += len(batch)
        trace.append({
            "family": family, "requested_slots": requested,
            "emitted": len(batch), "new_unique": len(newly_evaluated),
            "reward": reward,
            "remaining_budget": allocator.remaining_budget,
        })

    # If a family exhausts early, continue with remaining non-empty families.
    # The normal benchmark pools are intentionally sized to avoid this path.
    if slots_used != budget:
        raise RuntimeError(
            f"adaptive allocator consumed {slots_used} of {budget} proposal slots"
        )
    return {
        "candidates": tuple(registry.values()),
        "trace": tuple(trace),
        "allocations": allocator.allocations,
        "gate_dev_unique_evaluations": len(evaluated_gate_dev),
        "gate_final_unique_evaluations": len(registry),
        "proposal_slots_used": slots_used,
    }


def _select_on_gate_final(
    candidates: Sequence[Proposal],
    gate_final: Sequence[Observation],
) -> dict[str, Any]:
    """Select once on Gate-Final; this function cannot inspect Locked Test."""
    if not candidates:
        return {"selected_proposal": None, "gate_final_accuracy": None,
                "candidate_count": 0}
    ranked = sorted(
        candidates,
        key=lambda p: (
            -_accuracy(p, gate_final),
            p.canonical_expression,
            p.family,
        ),
    )
    selected = ranked[0]
    return {
        "selected_proposal": selected,
        "selected": selected.canonical_expression,
        "selected_family": selected.family,
        "selected_families": list(
            selected.supporting_families or (selected.family,)
        ),
        "gate_final_accuracy": _accuracy(selected, gate_final),
        "candidate_count": len(candidates),
    }


def _score_locked_test(
    selection: dict[str, Any],
    locked_test: Sequence[Observation],
) -> float | None:
    """Score only the already-frozen Gate-Final selection."""
    selected = selection["selected_proposal"]
    return _accuracy(selected, locked_test) if selected is not None else None


def _unique_candidate_registry(
    proposals: Sequence[Proposal],
) -> tuple[Proposal, ...]:
    registry: dict[str, Proposal] = {}
    for proposal in proposals:
        key = proposal.canonical_expression
        existing = registry.get(key)
        if existing is None:
            registry[key] = proposal
        else:
            families = tuple(sorted(set(
                (existing.supporting_families or (existing.family,))
                + (proposal.supporting_families or (proposal.family,))
            )))
            registry[key] = replace(existing, supporting_families=families)
    return tuple(registry.values())


def _fixed_select(
    proposals: Sequence[Proposal],
    gate_final: Sequence[Observation],
    locked_test: Sequence[Observation],
    budget: int,
) -> dict[str, Any]:
    emitted = tuple(proposals[:budget])
    selected = _unique_candidate_registry(emitted)
    result = _select_on_gate_final(selected, gate_final)
    result["locked_test_accuracy"] = _score_locked_test(result, locked_test)
    result.pop("selected_proposal", None)
    result["proposal_slots_used"] = len(emitted)
    result["gate_dev_unique_evaluations"] = 0
    result["gate_final_unique_evaluations"] = len(selected)
    result["trace"] = []
    return result


def run_episode(seed: int, task: str, budget: int = 31) -> dict[str, Any]:
    support, gate_dev, gate_final, locked_test = make_four_way_world(seed, task)
    pools = _make_pools(support, seed)
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

    rr_candidates = allocate_round_robin(
        {family: pools[family] for family in ADAPTIVE_FAMILIES}, budget
    )
    methods["ROUND_ROBIN"] = _fixed_select(
        rr_candidates, gate_final, locked_test, budget
    )

    adaptive = _adaptive_allocate(support, gate_dev, seed, budget)
    adaptive_result = _select_on_gate_final(
        adaptive["candidates"], gate_final
    )
    adaptive_result["locked_test_accuracy"] = _score_locked_test(
        adaptive_result, locked_test
    )
    adaptive_result.pop("selected_proposal", None)
    adaptive_result.update({
        "proposal_slots_used": adaptive["proposal_slots_used"],
        "gate_dev_unique_evaluations": adaptive["gate_dev_unique_evaluations"],
        "gate_final_unique_evaluations": adaptive["gate_final_unique_evaluations"],
        "trace": list(adaptive["trace"]),
        "allocations": adaptive["allocations"],
    })
    methods["UCB1_ADAPTIVE"] = adaptive_result

    for name, result in methods.items():
        if result["proposal_slots_used"] != budget:
            raise RuntimeError(
                f"{name} consumed {result['proposal_slots_used']} of {budget} slots"
            )
    return {
        "seed": seed, "task": task, "budget": budget,
        "split_sizes": {
            "support": len(support), "gate_dev": len(gate_dev),
            "gate_final": len(gate_final), "locked_test": len(locked_test),
        },
        "methods": methods,
    }


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
    aggregate = {}
    for method in METHODS:
        values = [episode["methods"][method] for episode in episodes]
        covered = [
            item["locked_test_accuracy"] for item in values
            if item["locked_test_accuracy"] is not None
        ]
        aggregate[method] = {
            "episodes": len(values),
            "selection_coverage": len(covered) / len(values),
            "mean_locked_test_accuracy_when_selected":
                mean(covered) if covered else None,
            "mean_unconditional_locked_test_accuracy": mean(
                item["locked_test_accuracy"] or 0.0 for item in values
            ),
            "mean_proposal_slots": mean(
                item["proposal_slots_used"] for item in values
            ),
            "mean_gate_dev_unique_evaluations": mean(
                item["gate_dev_unique_evaluations"] for item in values
            ),
            "mean_gate_final_unique_evaluations": mean(
                item["gate_final_unique_evaluations"] for item in values
            ),
        }
    return {
        "protocol": (
            "four-way disjoint Support/Gate-Dev/Gate-Final/Locked-Test; "
            "equal proposal-slot budget; UCB1-inspired finite-pool heuristic"
        ),
        "seeds_per_task": seeds,
        "start_seed": start_seed,
        "budget_per_method_episode": budget,
        "episode_count": len(episodes),
        "aggregate": aggregate,
        "episodes": episodes,
        "limitations": [
            "Two synthetic task families only.",
            "Finite hand-specified predicate grammar.",
            "Proposal slots are matched; wall-clock and CPU costs are not.",
            "UCB1 rewards are non-stationary because candidate pools are finite and sampled without replacement.",
            "Gate-Dev rewards are adaptive feedback and can overfit; Gate-Final is held for one-time selection.",
            "Locked Test is not used for proposals, allocation, or selection.",
            "This is not a process-isolated security boundary.",
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
