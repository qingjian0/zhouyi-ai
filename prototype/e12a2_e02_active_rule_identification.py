"""E12-A2 x E02-D: active identification of finite affine rule hypotheses.

The learner sees only support observations and the declared query domain.
The target rule is used only by the episode runner's environment reveal.
This is a finite symbolic benchmark, not a learned neural model.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
import random
from typing import Iterable

from prototype.e12a2_active_measurement import Probe, select_probe

VALUES = (0, 1, 2)
QUERIES = tuple((a, b) for a in VALUES for b in VALUES)
RULES = tuple((alpha, beta, delta)
              for alpha in VALUES for beta in VALUES for delta in VALUES)


def predict(rule: tuple[int, int, int], query: tuple[int, int]) -> int:
    alpha, beta, delta = rule
    a, b = query
    return (-(alpha * a + beta * b + delta)) % 3


def consistent_rules(evidence: Iterable[tuple[tuple[int, int], int]]) -> tuple:
    rows = tuple(evidence)
    return tuple(rule for rule in RULES
                 if all(predict(rule, query) == outcome for query, outcome in rows))


def _probe(query: tuple[int, int], hypotheses: tuple) -> Probe:
    outcomes = {}
    for outcome in VALUES:
        outcomes[str(outcome)] = {
            _rule_id(rule): float(predict(rule, query) == outcome)
            for rule in hypotheses
        }
    return Probe(_query_id(query), 1.0, outcomes)


def _rule_id(rule: tuple[int, int, int]) -> str:
    return f"r:{rule[0]}:{rule[1]}:{rule[2]}"


def _query_id(query: tuple[int, int]) -> str:
    return f"q:{query[0]}:{query[1]}"


def initial_query_for_seed(seed: int) -> tuple[int, int]:
    """Choose Support query independently of the hidden target rule."""
    return random.Random(seed).choice(QUERIES)


def _decode_query(action_id: str) -> tuple[int, int]:
    _, a, b = action_id.split(":")
    return int(a), int(b)


def select_information_gain(evidence: tuple, available: tuple) -> tuple[int, int] | None:
    hypotheses = consistent_rules(evidence)
    if len(hypotheses) <= 1:
        return None
    priors = {_rule_id(rule): 1.0 / len(hypotheses) for rule in hypotheses}
    probes = [_probe(query, hypotheses) for query in available]
    result = select_probe(priors, probes, remaining_budget=float(len(available)))
    if result["status"] != "SELECTED":
        return None
    return _decode_query(result["selected"])


def _partition(hypotheses: tuple, query: tuple) -> tuple[tuple, ...]:
    groups = []
    for outcome in VALUES:
        group = tuple(rule for rule in hypotheses
                      if predict(rule, query) == outcome)
        if group:
            groups.append(group)
    return tuple(groups)


@lru_cache(maxsize=None)
def optimal_expected_remaining(
    hypothesis_ids: tuple[tuple[int, int, int], ...],
    available: tuple[tuple[int, int], ...],
) -> float:
    """Exact Bellman oracle for expected additional unit-cost queries.

    The oracle knows the declared finite hypothesis class, not the hidden
    target identity. It is an upper-bound policy diagnostic, not a learner.
    """
    if len(hypothesis_ids) <= 1:
        return 0.0
    best = float("inf")
    for query in available:
        groups = _partition(hypothesis_ids, query)
        if len(groups) <= 1:
            continue
        remaining = tuple(q for q in available if q != query)
        value = 1.0 + sum(
            len(group) / len(hypothesis_ids)
            * optimal_expected_remaining(tuple(sorted(group)), remaining)
            for group in groups
        )
        best = min(best, value)
    return best


def select_oracle(evidence: tuple, available: tuple) -> tuple[int, int] | None:
    hypotheses = consistent_rules(evidence)
    if len(hypotheses) <= 1:
        return None
    scored = []
    for query in available:
        groups = _partition(hypotheses, query)
        if len(groups) <= 1:
            continue
        remaining = tuple(q for q in available if q != query)
        value = 1.0 + sum(
            len(group) / len(hypotheses)
            * optimal_expected_remaining(tuple(sorted(group)), remaining)
            for group in groups
        )
        scored.append((value, query))
    return min(scored, default=(float("inf"), None), key=lambda x: (x[0], x[1]))[1]


def run_episode(
    target_rule: tuple[int, int, int],
    initial_query: tuple[int, int],
    policy: str,
    seed: int,
) -> dict:
    """Run with target_rule kept in the environment side of this function."""
    rng = random.Random(seed)
    evidence = ((initial_query, predict(target_rule, initial_query)),)
    available = tuple(query for query in QUERIES if query != initial_query)
    steps = 0
    trace = []
    while len(consistent_rules(evidence)) > 1 and available:
        hypotheses = consistent_rules(evidence)
        if policy == "information_gain":
            query = select_information_gain(evidence, available)
        elif policy == "random":
            query = rng.choice(available)
        elif policy == "fixed":
            query = min(available)
        elif policy == "exact_oracle":
            query = select_oracle(evidence, available)
        else:
            raise ValueError(f"unknown policy: {policy}")
        if query is None:
            break
        # Environment reveal: only this line uses the hidden target rule.
        outcome = predict(target_rule, query)
        trace.append({
            "query": query,
            "candidate_count_before": len(hypotheses),
            "outcome": outcome,
        })
        evidence += ((query, outcome),)
        available = tuple(item for item in available if item != query)
        steps += 1
    remaining = consistent_rules(evidence)
    identified = len(remaining) == 1
    return {
        "policy": policy,
        "target": _rule_id(target_rule),
        "initial_query": initial_query,
        "additional_measurements": steps,
        "total_measurements": steps + 1,
        "identified": identified,
        "remaining_hypotheses": len(remaining),
        "trace": trace,
    }


def run_benchmark(seeds: int = 100, start_seed: int = 100) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    policies = ("information_gain", "random", "fixed", "exact_oracle")
    rows = {policy: [] for policy in policies}
    for offset in range(seeds):
        seed = start_seed + offset
        initial_query = initial_query_for_seed(seed)
        for target in RULES:
            for policy in policies:
                rows[policy].append(run_episode(target, initial_query, policy, seed))
    summary = {}
    for policy, episodes in rows.items():
        summary[policy] = {
            "episodes": len(episodes),
            "identification_rate": sum(e["identified"] for e in episodes) / len(episodes),
            "mean_additional_measurements": sum(
                e["additional_measurements"] for e in episodes) / len(episodes),
            "max_additional_measurements": max(
                e["additional_measurements"] for e in episodes),
            "mean_remaining_hypotheses": sum(
                e["remaining_hypotheses"] for e in episodes) / len(episodes),
        }
    return {
        "experiment": "E12-A2-E02-D-active-affine-rule-identification",
        "hypothesis_class": "27 affine rules over Z3",
        "query_domain_size": len(QUERIES),
        "initial_support_measurements": 1,
        "seeds": seeds,
        "seed_start": start_seed,
        "policies": summary,
        "interpretation": [
            "Information gain is evaluated from the current consistent hypothesis set and uniform prior.",
            "The exact oracle minimizes expected remaining unit-cost queries by dynamic programming.",
            "Random and fixed policies receive the same query domain and unit measurement costs.",
            "The target rule is used only by the environment reveal in each episode.",
            "This is finite symbolic active identification, not neural learning or open-world discovery.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--start-seed", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.seeds, args.start_seed)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
