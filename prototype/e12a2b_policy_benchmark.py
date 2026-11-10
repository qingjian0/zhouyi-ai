"""E12-A2-B: held-out finite-world benchmark for active measurement policies.

Policies see only the current version space, public action predictions, costs,
and remaining budget. The hidden target hypothesis is used only by the episode
environment to emit an observation.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Callable


@dataclass(frozen=True)
class WorldAction:
    action_id: str
    cost: int
    # Outcome at each hypothesis index. Index ordering is public and stable.
    outcomes: tuple[str, ...]


@dataclass(frozen=True)
class WorldFamily:
    family_id: str
    hypothesis_ids: tuple[str, ...]
    actions: tuple[WorldAction, ...]


@dataclass(frozen=True)
class EpisodeResult:
    policy: str
    family_id: str
    target_hypothesis: str
    identified: bool
    residual_entropy_bits: float
    posterior_map_confidence: float
    spent_cost: int
    measurements: int


POLICIES = (
    "random",
    "fixed",
    "max_disagreement",
    "expected_ig",
    "cost_normalized_ig",
    "exact_optimal",
)


def _entropy_from_counts(counts: tuple[int, ...]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts if count
    )


def _active_indices(counts: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(index for index, count in enumerate(counts) if count > 0)


def _action_partition(
    action: WorldAction, active: tuple[int, ...]
) -> dict[str, tuple[int, ...]]:
    groups: dict[str, list[int]] = {}
    for index in active:
        groups.setdefault(action.outcomes[index], []).append(index)
    return {key: tuple(value) for key, value in groups.items()}


def _information_gain(action: WorldAction, active: tuple[int, ...]) -> float:
    # Deterministic measurement: outcome entropy equals mutual information.
    before = math.log2(len(active)) if active else 0.0
    expected_after = sum(
        len(group) / len(active) * math.log2(len(group))
        for group in _action_partition(action, active).values()
    ) if active else 0.0
    return max(0.0, before - expected_after)


def _gini_disagreement(action: WorldAction, active: tuple[int, ...]) -> float:
    if not active:
        return 0.0
    groups = _action_partition(action, active).values()
    return 1.0 - sum((len(group) / len(active)) ** 2 for group in groups)


def _exact_optimal_action(
    actions: tuple[WorldAction, ...],
    active: tuple[int, ...],
    available: tuple[int, ...],
    budget: int,
) -> int | None:
    """Exact DP minimizing expected terminal posterior entropy."""
    @lru_cache(maxsize=None)
    def value(
        current: tuple[int, ...],
        remaining: tuple[int, ...],
        money: int,
    ) -> tuple[float, int | None]:
        current_entropy = math.log2(len(current)) if current else 0.0
        best_value = current_entropy
        best_action: int | None = None
        for action_index in remaining:
            action = actions[action_index]
            if action.cost > money:
                continue
            groups = _action_partition(action, current)
            if len(groups) <= 1:
                continue
            next_remaining = tuple(i for i in remaining if i != action_index)
            expected_entropy = 0.0
            for group in groups.values():
                probability = len(group) / len(current)
                child_value, _ = value(
                    group, next_remaining, money - action.cost
                )
                expected_entropy += probability * child_value
            if (
                expected_entropy < best_value - 1e-12
                or (
                    abs(expected_entropy - best_value) <= 1e-12
                    and best_action is not None
                    and (action.cost, action.action_id)
                    < (actions[best_action].cost, actions[best_action].action_id)
                )
            ):
                best_value = expected_entropy
                best_action = action_index
        return best_value, best_action

    return value(active, available, budget)[1]


def select_policy_action(
    policy: str,
    actions: tuple[WorldAction, ...],
    active: tuple[int, ...],
    available: tuple[int, ...],
    remaining_budget: int,
    rng: random.Random,
) -> int | None:
    """Truth-free policy API: there is deliberately no target-hypothesis input."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    feasible = tuple(
        index for index in available
        if actions[index].cost <= remaining_budget
    )
    if not feasible or len(active) <= 1:
        return None
    if policy == "random":
        informative = tuple(
            i for i in feasible
            if len(_action_partition(actions[i], active)) > 1
        )
        return rng.choice(informative) if informative else None
    if policy == "fixed":
        informative = tuple(
            i for i in feasible
            if len(_action_partition(actions[i], active)) > 1
        )
        return min(informative, key=lambda i: actions[i].action_id) if informative else None
    if policy == "max_disagreement":
        return max(
            feasible,
            key=lambda i: (
                _gini_disagreement(actions[i], active),
                -actions[i].cost,
                tuple(-ord(c) for c in actions[i].action_id),
            ),
        ) if any(_gini_disagreement(actions[i], active) > 0 for i in feasible) else None
    if policy == "expected_ig":
        scored = [(i, _information_gain(actions[i], active)) for i in feasible]
        best = max(score for _, score in scored)
        if best <= 1e-12:
            return None
        return min(
            (i for i, score in scored if abs(score - best) <= 1e-12),
            key=lambda i: (actions[i].cost, actions[i].action_id),
        )
    if policy == "cost_normalized_ig":
        scored = [
            (i, _information_gain(actions[i], active) / actions[i].cost)
            for i in feasible
        ]
        best = max(score for _, score in scored)
        if best <= 1e-12:
            return None
        return min(
            (i for i, score in scored if abs(score - best) <= 1e-12),
            key=lambda i: (actions[i].cost, actions[i].action_id),
        )
    if policy == "exact_optimal":
        return _exact_optimal_action(actions, active, feasible, remaining_budget)
    raise ValueError(f"unknown policy: {policy}")


def _partition_from_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    return labels


def make_world_family(family: str, seed: int) -> WorldFamily:
    """Create a reproducible public action set with a hidden target per episode."""
    rng = random.Random(seed)
    n = 8
    ids = tuple(f"h{i}" for i in range(n))
    actions: list[WorldAction] = []

    def add(action_id: str, labels: tuple[str, ...], cost: int = 1) -> None:
        actions.append(WorldAction(action_id, cost, _partition_from_labels(labels)))

    if family == "balanced":
        for j in range(4):
            perm = list(range(n))
            rng.shuffle(perm)
            labels = [""] * n
            for rank, index in enumerate(perm):
                labels[index] = str(rank % 2)
            add(f"balanced_{j}", tuple(labels), 1 + (j % 2))
        # A three-way action tests disagreement metrics beyond binary splits.
        perm = list(range(n))
        rng.shuffle(perm)
        labels = [""] * n
        for rank, index in enumerate(perm):
            labels[index] = str(rank % 3)
        add("three_way", tuple(labels), 2)
    elif family == "skewed":
        for split in (1, 2, 3, 4):
            perm = list(range(n))
            rng.shuffle(perm)
            labels = ["1"] * n
            for index in perm[:split]:
                labels[index] = "0"
            add(f"split_{split}_vs_{n-split}", tuple(labels), 1)
        perm = list(range(n))
        rng.shuffle(perm)
        labels = ["2"] * n
        for index in perm[:1]:
            labels[index] = "0"
        for index in perm[1:2]:
            labels[index] = "1"
        add("rare_three_way", tuple(labels), 1)
    elif family == "redundant":
        base: list[tuple[str, ...]] = []
        for j in range(2):
            perm = list(range(n))
            rng.shuffle(perm)
            labels = [""] * n
            for rank, index in enumerate(perm):
                labels[index] = str(rank % 2)
            base.append(tuple(labels))
        add("base_a", base[0], 1)
        add("base_a_duplicate", base[0], 2)
        add("base_b", base[1], 1)
        # Refinement and a unique but expensive measurement.
        refined = tuple(f"{base[0][i]}{base[1][i]}" for i in range(n))
        add("joint_refinement", refined, 2)
        add("direct_id", tuple(str(i) for i in range(n)), 4)
    else:
        raise ValueError("family must be balanced, skewed, or redundant")

    return WorldFamily(f"{family}_{seed}", ids, tuple(actions))


def run_episode(
    world: WorldFamily,
    target_index: int,
    policy: str,
    budget: int,
    seed: int,
) -> EpisodeResult:
    rng = random.Random(seed)
    counts = tuple(1 for _ in world.hypothesis_ids)
    available = tuple(range(len(world.actions)))
    spent = 0
    measurements = 0

    while True:
        active = _active_indices(counts)
        selected = select_policy_action(
            policy, world.actions, active, available, budget - spent, rng
        )
        if selected is None:
            break
        action = world.actions[selected]
        observed = action.outcomes[target_index]
        counts = tuple(
            count if action.outcomes[index] == observed else 0
            for index, count in enumerate(counts)
        )
        spent += action.cost
        measurements += 1
        available = tuple(index for index in available if index != selected)

    active_count = sum(1 for count in counts if count > 0)
    posterior_entropy = math.log2(active_count) if active_count else 0.0
    return EpisodeResult(
        policy=policy,
        family_id=world.family_id,
        target_hypothesis=world.hypothesis_ids[target_index],
        identified=active_count == 1,
        residual_entropy_bits=posterior_entropy,
        posterior_map_confidence=(1.0 / active_count if active_count else 0.0),
        spent_cost=spent,
        measurements=measurements,
    )


def run_benchmark(seeds: int = 20, budget: int = 4, start_seed: int = 100) -> dict:
    if seeds < 1 or budget < 0:
        raise ValueError("seeds must be positive and budget non-negative")
    families = ("balanced", "skewed", "redundant")
    all_results: list[EpisodeResult] = []
    for family in families:
        for offset in range(seeds):
            seed = start_seed + offset
            world = make_world_family(family, seed)
            for policy_index, policy in enumerate(POLICIES):
                for target_index in range(len(world.hypothesis_ids)):
                    all_results.append(run_episode(
                        world, target_index, policy, budget,
                        seed * 1009 + policy_index * 97 + target_index,
                    ))

    summary = []
    for policy in POLICIES:
        rows = [item for item in all_results if item.policy == policy]
        count = len(rows)
        summary.append({
            "policy": policy,
            "episodes": count,
            "identification_rate": sum(item.identified for item in rows) / count,
            "mean_residual_entropy_bits": sum(
                item.residual_entropy_bits for item in rows
            ) / count,
            "mean_map_confidence": sum(
                item.posterior_map_confidence for item in rows
            ) / count,
            "mean_cost_spent": sum(item.spent_cost for item in rows) / count,
            "mean_measurements": sum(item.measurements for item in rows) / count,
        })

    return {
        "benchmark": "E12-A2-B finite-world active measurement",
        "seeds_per_family": seeds,
        "families": list(families),
        "hypotheses_per_world": 8,
        "budget": budget,
        "policies": list(POLICIES),
        "episode_count": len(all_results),
        "summary": summary,
        "protocol": {
            "target_selection": "uniform over the 8 hypotheses; exhaustive per world",
            "learner_visibility": "current version space, public action outcomes/costs, remaining budget",
            "hidden_from_policy": ["target hypothesis index", "future observations"],
            "outcome_model": "deterministic categorical measurements",
            "stopping": "identified, no informative affordable action, or budget exhausted",
            "exact_optimal": "dynamic programming minimizing expected terminal posterior entropy",
        },
        "limitations": [
            "Synthetic finite hypothesis spaces only; no natural-world or language task.",
            "Uniform priors and deterministic observations; noisy and misspecified-prior tests are future work.",
            "Action outcome tables are supplied to all policies; autonomous action-model learning is not tested.",
            "The exact-optimal policy is an oracle over the declared finite action set, not an unconstrained real-world agent.",
            "No Yijing-specific structure is included in this generic baseline.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--budget", type=int, default=4)
    parser.add_argument("--start-seed", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.seeds, args.budget, args.start_seed)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))


if __name__ == "__main__":
    main()
