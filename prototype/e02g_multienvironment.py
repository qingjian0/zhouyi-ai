"""E02-G: repeated multi-environment relation stability classification.

The learner discovers a bounded interaction candidate using training data
from multiple environments, then uses independent repeated gates to classify
whether the relation is stable, context-conditional, or sign-drifting.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    sample_id: str
    values: tuple[int, ...]
    label: int


@dataclass(frozen=True)
class Candidate:
    members: tuple[int, ...]


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("invalid binomial counts")
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / denom
    return max(0.0, center - radius), min(1.0, center + radius)


def make_rows(*, seed: int, count: int, target: tuple[int, ...],
              environment: int, regime: str, noise: float = 0.02,
              width: int = 8) -> list[Row]:
    if count < 4 or width < 4 or not target or len(set(target)) != len(target):
        raise ValueError("invalid dimensions or target")
    if any(i < 0 or i >= width for i in target):
        raise ValueError("target outside feature width")
    if regime not in {"stable", "conditional", "drift"}:
        raise ValueError("unknown regime")
    if environment not in (0, 1) or not 0 <= noise < 0.5:
        raise ValueError("invalid environment or noise")
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        values = tuple(rng.choice((-1, 1)) for _ in range(width))
        signal = 1
        for member in target:
            signal *= values[member]
        if regime == "conditional" and environment == 1:
            label = rng.choice((-1, 1))
        else:
            if regime == "drift" and environment == 1:
                signal *= -1
            label = signal
        if rng.random() < noise:
            label *= -1
        rows.append(Row(f"{seed}:{i}", values, label))
    return rows


def correlation(rows: list[Row], members: tuple[int, ...]) -> float:
    if not rows:
        raise ValueError("rows cannot be empty")
    total = 0
    for row in rows:
        interaction = 1
        for member in members:
            interaction *= row.values[member]
        total += row.label * interaction
    return total / len(rows)


def discover(train_by_env: dict[int, list[Row]], *,
             min_order: int = 2, max_order: int = 4) -> Candidate:
    if set(train_by_env) != {0, 1} or min_order < 1 or max_order < min_order:
        raise ValueError("invalid training environments or candidate orders")
    width = len(train_by_env[0][0].values)
    if any(not rows or any(len(r.values) != width for r in rows)
           for rows in train_by_env.values()):
        raise ValueError("empty or inconsistent training data")
    ranked = []
    for order in range(min_order, min(max_order, width) + 1):
        for members in itertools.combinations(range(width), order):
            env_corrs = [correlation(train_by_env[e], members) for e in (0, 1)]
            # Max-across-environments preserves candidates whose relation is
            # active in only one context or reverses sign across contexts.
            score = max(abs(c) for c in env_corrs)
            ranked.append((score, members))
    ranked.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return Candidate(ranked[0][1])


def evaluate_environment(rows: list[Row], candidate: Candidate,
                         direction: int) -> dict:
    correct = 0
    for row in rows:
        pred = direction
        for member in candidate.members:
            pred *= row.values[member]
        correct += pred == row.label
    low, high = wilson_interval(correct, len(rows))
    return {
        "correct": correct, "total": len(rows),
        "accuracy": correct / len(rows),
        "wilson_95": [low, high],
        "direction": direction,
        "active": low > 0.75,
        "inactive": high < 0.75,
    }


def run_episode(*, seed: int, regime: str, train_n: int = 512,
                gate_n: int = 256, repeats: int = 5,
                noise: float = 0.02) -> dict:
    if repeats < 2:
        raise ValueError("at least two independent gate repeats are required")
    rng = random.Random(seed * 7919 + 23)
    target = tuple(sorted(rng.sample(range(8), 3)))
    train = {
        env: make_rows(seed=seed * 1009 + env + 1, count=train_n,
                       target=target, environment=env, regime=regime, noise=noise)
        for env in (0, 1)
    }
    candidate = discover(train)
    gates = {0: [], 1: []}
    train_directions = {}
    for env in (0, 1):
        train_directions[env] = 1 if correlation(train[env], candidate.members) >= 0 else -1
        for rep in range(repeats):
            gate = make_rows(
                seed=seed * 1000003 + env * 1009 + rep + 100,
                count=gate_n, target=target, environment=env,
                regime=regime, noise=noise,
            )
            gates[env].append(evaluate_environment(
                gate, candidate, train_directions[env]
            ))

    aggregate = {}
    for env in (0, 1):
        correct = sum(g["correct"] for g in gates[env])
        total = sum(g["total"] for g in gates[env])
        low, high = wilson_interval(correct, total)
        aggregate[env] = {
            "correct": correct, "total": total, "accuracy": correct / total,
            "wilson_95": [low, high], "active": low > 0.75,
            "inactive": high < 0.75,
            "direction": train_directions[env],
            "repeat_accuracies": [g["accuracy"] for g in gates[env]],
        }

    active = [aggregate[e]["active"] for e in (0, 1)]
    dirs = [aggregate[e]["direction"] for e in (0, 1)]
    if all(active) and dirs[0] == dirs[1]:
        classification = "stable"
    elif all(active) and dirs[0] != dirs[1]:
        classification = "drift"
    elif active[0] != active[1]:
        classification = "conditional"
    else:
        classification = "unresolved"

    return {
        "seed": seed, "candidate_members": list(candidate.members),
        "target_for_audit_only": list(target),
        "classification": classification, "expected_regime_for_audit_only": regime,
        "environments": aggregate,
    }


def run(*, seeds: int = 50, start_seed: int = 700,
        train_n: int = 512, gate_n: int = 256,
        repeats: int = 5, noise: float = 0.02) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    conditions = {}
    for regime in ("stable", "conditional", "drift"):
        rows = [run_episode(seed=start_seed + i, regime=regime,
                            train_n=train_n, gate_n=gate_n,
                            repeats=repeats, noise=noise)
                for i in range(seeds)]
        conditions[regime] = {
            "episodes": rows,
            "correct_classification_rate": sum(
                r["classification"] == regime for r in rows) / seeds,
            "candidate_recovery_rate": sum(
                set(r["candidate_members"]) == set(r["target_for_audit_only"])
                for r in rows) / seeds,
            "classification_counts": {
                label: sum(r["classification"] == label for r in rows)
                for label in ("stable", "conditional", "drift", "unresolved")
            },
        }
    return {
        "task": "E02G_multienvironment_relation_stability",
        "seeds": seeds, "settings": {
            "train_n_per_environment": train_n,
            "gate_n_per_environment_per_repeat": gate_n,
            "independent_gate_repeats": repeats, "noise": noise,
            "candidate_orders": "2..4",
            "active_rule": "95% Wilson lower bound > 0.75",
            "inactive_rule": "95% Wilson upper bound < 0.75",
        },
        "conditions": conditions,
        "limitations": [
            "Synthetic binary multiplicative interaction family only.",
            "Two environments and three predeclared regimes; not open-ended drift discovery.",
            "Candidate language remains bounded to interaction subsets.",
            "Wilson intervals quantify binomial accuracy uncertainty, not search-wide post-selection error.",
            "The audit target and regime are never passed to discovery or classification."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=700)
    parser.add_argument("--train", type=int, default=512)
    parser.add_argument("--gate", type=int, default=256)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--noise", type=float, default=0.02)
    args = parser.parse_args()
    print(json.dumps(run(seeds=args.seeds, start_seed=args.start_seed,
                         train_n=args.train, gate_n=args.gate,
                         repeats=args.repeats, noise=args.noise), indent=2))


if __name__ == "__main__":
    main()
