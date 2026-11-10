"""E12-A2-D: noisy-observation and prior-misspecification stress benchmark.

Finite Bayesian active measurement with binary stochastic sensors. The policy
sees only its own prior, public likelihood model, costs and remaining budget.
The evaluator samples hidden targets from a separate true prior and emits
stochastic observations; neither is passed to the selector.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class NoisyAction:
    action_id: str
    cost: int
    # P(observation == "1" | hypothesis_i), in stable hypothesis order.
    p_one: tuple[float, ...]


@dataclass(frozen=True)
class NoisyWorld:
    family: str
    hypothesis_ids: tuple[str, ...]
    true_prior: tuple[float, ...]
    actions: tuple[NoisyAction, ...]


POLICIES = ("random", "fixed", "expected_ig", "cost_normalized_ig", "exact_optimal")
PRIOR_ARMS = ("matched", "uniform", "anti_aligned")


def _entropy(weights: tuple[float, ...]) -> float:
    return -sum(p * math.log2(p) for p in weights if p > 0)


def _normalize(weights: tuple[float, ...]) -> tuple[float, ...]:
    total = sum(weights)
    if total <= 0:
        raise ValueError("posterior has zero mass")
    return tuple(w / total for w in weights)


def _validate(world: NoisyWorld, prior: tuple[float, ...]) -> None:
    n = len(world.hypothesis_ids)
    if n < 2 or len(set(world.hypothesis_ids)) != n or any(not x for x in world.hypothesis_ids):
        raise ValueError("hypothesis IDs must be unique and non-empty")
    for weights in (world.true_prior, prior):
        if len(weights) != n or any(not math.isfinite(x) or x < 0 for x in weights):
            raise ValueError("prior weights must be finite, non-negative and aligned")
        if not math.isclose(sum(weights), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("prior weights must sum to one")
    ids = [a.action_id for a in world.actions]
    if not ids or len(ids) != len(set(ids)) or any(not x for x in ids):
        raise ValueError("action IDs must be unique and non-empty")
    for action in world.actions:
        if isinstance(action.cost, bool) or not isinstance(action.cost, int) or action.cost < 1:
            raise ValueError("action costs must be positive integers")
        if len(action.p_one) != n or any(
            not math.isfinite(p) or p <= 0 or p >= 1 for p in action.p_one
        ):
            raise ValueError("each sensor probability must be strictly between zero and one")


def _posterior(
    prior: tuple[float, ...], action: NoisyAction, observed: int
) -> tuple[float, ...]:
    likelihoods = action.p_one if observed == 1 else tuple(1.0 - p for p in action.p_one)
    return _normalize(tuple(p * likelihood for p, likelihood in zip(prior, likelihoods)))


def _outcome_probability(prior: tuple[float, ...], action: NoisyAction, observed: int) -> float:
    likelihoods = action.p_one if observed == 1 else tuple(1.0 - p for p in action.p_one)
    return sum(p * likelihood for p, likelihood in zip(prior, likelihoods))


def information_gain(prior: tuple[float, ...], action: NoisyAction) -> float:
    expected = sum(
        _outcome_probability(prior, action, observed)
        * _entropy(_posterior(prior, action, observed))
        for observed in (0, 1)
    )
    return max(0.0, _entropy(prior) - expected)


def _exact_value(
    prior: tuple[float, ...],
    actions: tuple[NoisyAction, ...],
    remaining: tuple[int, ...],
    budget: int,
) -> tuple[float, int | None]:
    @lru_cache(maxsize=None)
    def solve(weights: tuple[float, ...], left: tuple[int, ...], money: int):
        best = _entropy(weights)
        best_action = None
        for index in left:
            action = actions[index]
            if action.cost > money:
                continue
            next_left = tuple(i for i in left if i != index)
            expected = 0.0
            for observed in (0, 1):
                probability = _outcome_probability(weights, action, observed)
                posterior = _posterior(weights, action, observed)
                child, _ = solve(posterior, next_left, money - action.cost)
                expected += probability * child
            if expected < best - 1e-12 or (
                abs(expected - best) <= 1e-12
                and (
                    best_action is None
                    or (action.cost, action.action_id)
                    < (actions[best_action].cost, actions[best_action].action_id)
                )
            ):
                best, best_action = expected, index
        return best, best_action

    return solve(prior, remaining, budget)


def select_action(
    policy: str,
    prior: tuple[float, ...],
    actions: tuple[NoisyAction, ...],
    available: tuple[int, ...],
    remaining_budget: int,
    rng: random.Random,
) -> int | None:
    if policy not in POLICIES:
        raise ValueError(f"unknown policy: {policy}")
    eligible = tuple(i for i in available if actions[i].cost <= remaining_budget)
    if not eligible:
        return None
    gains = {i: information_gain(prior, actions[i]) for i in eligible}
    informative = tuple(i for i in eligible if gains[i] > 1e-12)
    if not informative:
        return None
    if policy == "random":
        return rng.choice(informative)
    if policy == "fixed":
        return min(informative, key=lambda i: actions[i].action_id)
    if policy == "expected_ig":
        best = max(gains[i] for i in eligible)
        return min((i for i in eligible if best - gains[i] <= 1e-12),
                   key=lambda i: (actions[i].cost, actions[i].action_id))
    if policy == "cost_normalized_ig":
        utility = {i: gains[i] / actions[i].cost for i in eligible}
        best = max(utility.values())
        return min((i for i in eligible if best - utility[i] <= 1e-12),
                   key=lambda i: (actions[i].cost, actions[i].action_id))
    return _exact_value(prior, actions, eligible, remaining_budget)[1]


def _sample_target(prior: tuple[float, ...], rng: random.Random) -> int:
    draw = rng.random()
    cumulative = 0.0
    for index, weight in enumerate(prior):
        cumulative += weight
        if draw <= cumulative:
            return index
    return len(prior) - 1


def _sensor_rng(seed: int, action_id: str) -> random.Random:
    stable = sum((i + 1) * ord(char) for i, char in enumerate(action_id))
    return random.Random(seed * 1000003 + stable)


def run_episode(
    world: NoisyWorld,
    target_index: int,
    learner_prior: tuple[float, ...],
    policy: str,
    budget: int,
    seed: int,
) -> dict:
    _validate(world, learner_prior)
    if isinstance(target_index, bool) or not isinstance(target_index, int) or not 0 <= target_index < len(world.hypothesis_ids):
        raise ValueError("target_index is outside the hypothesis set")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
        raise ValueError("budget must be a non-negative integer")
    posterior = learner_prior
    available = tuple(range(len(world.actions)))
    spent = 0
    while True:
        selected = select_action(
            policy, posterior, world.actions, available, budget - spent,
            random.Random(seed + spent + len(available)),
        )
        if selected is None:
            break
        action = world.actions[selected]
        observed = int(_sensor_rng(seed, action.action_id).random() < action.p_one[target_index])
        posterior = _posterior(posterior, action, observed)
        spent += action.cost
        available = tuple(i for i in available if i != selected)

    map_index = max(range(len(posterior)), key=lambda i: (posterior[i], -i))
    target_vector = tuple(1.0 if i == target_index else 0.0 for i in range(len(posterior)))
    brier = sum((p - y) ** 2 for p, y in zip(posterior, target_vector))
    return {
        "correct": map_index == target_index,
        "identified_95": max(posterior) >= 0.95,
        "overconfident_wrong": max(posterior) >= 0.90 and map_index != target_index,
        "brier": brier,
        "log_loss": -math.log(max(posterior[target_index], 1e-12)),
        "posterior_entropy": _entropy(posterior),
        "map_confidence": max(posterior),
        "spent_cost": spent,
    }


def make_world(family: str) -> NoisyWorld:
    ids = ("h0", "h1", "h2", "h3")
    if family == "complementary":
        prior = (0.4, 0.3, 0.2, 0.1)
        actions = (
            NoisyAction("axis_a", 1, (0.9, 0.9, 0.1, 0.1)),
            NoisyAction("axis_b", 1, (0.9, 0.1, 0.9, 0.1)),
            NoisyAction("diagonal", 2, (0.95, 0.05, 0.05, 0.95)),
            NoisyAction("weak_a", 1, (0.65, 0.65, 0.35, 0.35)),
        )
    elif family == "rare":
        prior = (0.7, 0.1, 0.1, 0.1)
        actions = (
            NoisyAction("common_split", 1, (0.9, 0.9, 0.1, 0.1)),
            NoisyAction("rare_detector", 1, (0.95, 0.2, 0.2, 0.2)),
            NoisyAction("secondary_split", 1, (0.9, 0.1, 0.9, 0.1)),
            NoisyAction("expensive_joint", 2, (0.95, 0.8, 0.2, 0.05)),
        )
    elif family == "redundant":
        prior = (0.4, 0.3, 0.2, 0.1)
        actions = (
            NoisyAction("sensor_a", 1, (0.9, 0.9, 0.1, 0.1)),
            NoisyAction("sensor_a_copy", 2, (0.85, 0.85, 0.15, 0.15)),
            NoisyAction("sensor_b", 1, (0.9, 0.1, 0.9, 0.1)),
            NoisyAction("sensor_joint", 2, (0.95, 0.2, 0.2, 0.05)),
        )
    else:
        raise ValueError("family must be complementary, rare, or redundant")
    return NoisyWorld(family, ids, prior, actions)


def prior_for(world: NoisyWorld, arm: str) -> tuple[float, ...]:
    if arm == "matched":
        return world.true_prior
    if arm == "uniform":
        return tuple(1.0 / len(world.hypothesis_ids) for _ in world.hypothesis_ids)
    if arm == "anti_aligned":
        return tuple(reversed(world.true_prior))
    raise ValueError("unknown prior arm")


def _paired_delta(left: list[dict], right: list[dict], metric: str) -> dict:
    differences = [float(a[metric]) - float(b[metric]) for a, b in zip(left, right)]
    count = len(differences)
    mean = sum(differences) / count
    if count < 2:
        low = high = mean
    else:
        variance = sum((value - mean) ** 2 for value in differences) / (count - 1)
        margin = 1.96 * math.sqrt(variance / count)
        low, high = mean - margin, mean + margin
    return {"mean_delta": mean, "ci95_low": low, "ci95_high": high}


def run_benchmark(episodes: int = 100, budget: int = 3, start_seed: int = 2026) -> dict:
    if episodes < 1 or budget < 0:
        raise ValueError("episodes must be positive and budget non-negative")
    families = ("complementary", "rare", "redundant")
    rows = []
    for family_index, family in enumerate(families):
        world = make_world(family)
        results = {
            (arm, policy): []
            for arm in PRIOR_ARMS
            for policy in POLICIES
        }
        for episode in range(episodes):
            # The same target and action-specific sensor random streams are
            # shared across every prior/policy arm for paired comparisons.
            seed = start_seed + family_index * 100000 + episode
            target = _sample_target(world.true_prior, random.Random(seed))
            for arm in PRIOR_ARMS:
                learner_prior = prior_for(world, arm)
                for policy in POLICIES:
                    results[(arm, policy)].append(run_episode(
                        world, target, learner_prior, policy, budget, seed,
                    ))
        for arm in PRIOR_ARMS:
            for policy in POLICIES:
                items = results[(arm, policy)]
                count = len(items)
                rows.append({
                    "family": family,
                    "prior_arm": arm,
                    "policy": policy,
                    "episodes": count,
                    "accuracy": sum(x["correct"] for x in items) / count,
                    "identified_95_rate": sum(x["identified_95"] for x in items) / count,
                    "overconfident_wrong_rate": sum(x["overconfident_wrong"] for x in items) / count,
                    "mean_brier": sum(x["brier"] for x in items) / count,
                    "mean_log_loss": sum(x["log_loss"] for x in items) / count,
                    "mean_posterior_entropy_bits": sum(x["posterior_entropy"] for x in items) / count,
                    "mean_map_confidence": sum(x["map_confidence"] for x in items) / count,
                    "mean_cost": sum(x["spent_cost"] for x in items) / count,
                })
    contrasts = []
    for family in families:
        for policy in POLICIES:
            # Reconstruct paired episodes for uncertainty estimates.
            world = make_world(family)
            family_index = families.index(family)
            paired = {
                arm: [] for arm in PRIOR_ARMS
            }
            for episode in range(episodes):
                seed = start_seed + family_index * 100000 + episode
                target = _sample_target(world.true_prior, random.Random(seed))
                for arm in PRIOR_ARMS:
                    paired[arm].append(run_episode(
                        world, target, prior_for(world, arm), policy, budget, seed
                    ))
            for arm in ("matched", "anti_aligned"):
                contrasts.append({
                    "family": family,
                    "policy": policy,
                    "comparison": f"{arm}_minus_uniform",
                    "accuracy": _paired_delta(paired[arm], paired["uniform"], "correct"),
                    "brier": _paired_delta(paired[arm], paired["uniform"], "brier"),
                    "log_loss": _paired_delta(paired[arm], paired["uniform"], "log_loss"),
                    "overconfident_wrong": _paired_delta(
                        paired[arm], paired["uniform"], "overconfident_wrong"
                    ),
                })

    return {
        "benchmark": "E12-A2-D noisy measurement and prior misspecification",
        "episodes_per_cell": episodes,
        "budget": budget,
        "families": list(families),
        "prior_arms": list(PRIOR_ARMS),
        "policies": list(POLICIES),
        "rows": rows,
        "paired_prior_contrasts": contrasts,
        "protocol": {
            "target_distribution": "environment-private true prior per world family",
            "learner_visibility": "learner prior arm, public noisy likelihoods, costs, remaining budget",
            "observation_model": "binary stochastic sensors; each action can be used once",
            "paired_targets": "all policy arms share the same target draw within each family/prior cell",
            "metrics": "accuracy, Brier, log loss, posterior entropy, overconfident-wrong rate, cost",
        },
        "limitations": [
            "Small synthetic finite hypothesis spaces only.",
            "Likelihood tables are supplied; sensor-model learning is not evaluated.",
            "Monte Carlo target and observation sampling; confidence intervals are not yet included.",
            "No Yijing-specific prior is used; the arms are matched, uniform and anti-aligned generic controls.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument("--start-seed", type=int, default=2026)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.episodes, args.budget, args.start_seed),
                     ensure_ascii=False, indent=2 if args.json else None))


if __name__ == "__main__":
    main()
