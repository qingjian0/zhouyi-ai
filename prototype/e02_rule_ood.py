"""E02-D: held-out rule-family generalization via symbolic relation induction.

The benchmark withholds complete modular rule parameterizations, not merely
random examples. The solver enumerates a declared hypothesis class and only
predicts when all support-consistent hypotheses agree. This is an exact
symbolic baseline, not a neural learner or evidence of general intelligence.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass

Z3 = (0, 1, 2)
QUERIES = tuple(itertools.product(Z3, repeat=2))
RULES = tuple((a, b, d) for a in Z3 for b in Z3 for d in Z3)


@dataclass(frozen=True)
class Episode:
    rule: tuple[int, int, int]
    support: tuple[tuple[int, int, int], ...]
    query: tuple[int, int]


def target_c(rule: tuple[int, int, int], a: int, b: int) -> int:
    alpha, beta, delta = rule
    return (-(alpha * a + beta * b + delta)) % 3


def make_episodes(seed: int, support_size: int = 6) -> list[Episode]:
    if not 1 <= support_size < len(QUERIES):
        raise ValueError("support_size must be between 1 and 8")
    rng = random.Random(seed)
    episodes = []
    for rule in RULES:
        queries = list(QUERIES)
        rng.shuffle(queries)
        support_queries = queries[:support_size]
        heldout_query = queries[support_size]
        support = tuple((a, b, target_c(rule, a, b))
                        for a, b in support_queries)
        episodes.append(Episode(rule, support, heldout_query))
    return episodes


def consistent_rules(support: tuple[tuple[int, int, int], ...]
                      ) -> tuple[tuple[int, int, int], ...]:
    return tuple(rule for rule in RULES
                 if all(target_c(rule, a, b) == c for a, b, c in support))


def infer(episode: Episode) -> dict:
    hypotheses = consistent_rules(episode.support)
    a, b = episode.query
    predictions = {target_c(rule, a, b) for rule in hypotheses}
    gold = target_c(episode.rule, a, b)
    unique = len(predictions) == 1
    prediction = next(iter(predictions)) if unique else None
    return {
        "gold": gold,
        "prediction": prediction,
        "correct": unique and prediction == gold,
        "identifiable": unique,
        "consistent_hypotheses": len(hypotheses),
    }


def run(seed: int = 17, support_size: int = 6) -> dict:
    episodes = make_episodes(seed, support_size)
    # Rule-level split is explicit and deterministic: all parameterizations
    # are evaluated, while each episode's target query is unseen in support.
    results = [infer(ep) for ep in episodes]
    n = len(results)
    identified = sum(r["identifiable"] for r in results)
    correct = sum(r["correct"] for r in results)
    return {
        "task": "Z3_affine_rule_family_induction",
        "rule": "(alpha*a + beta*b + c + delta) % 3 == 0",
        "hypothesis_class_size": len(RULES),
        "episodes": n,
        "support_queries_per_episode": support_size,
        "heldout_query_per_episode": 1,
        "identified_episode_count": identified,
        "identification_coverage": identified / n,
        "accuracy_on_all_episodes": correct / n,
        "accuracy_when_identified": correct / identified if identified else None,
        "memorization_unseen_rule_chance_baseline": 1 / 3,
        "mean_consistent_hypotheses": sum(
            r["consistent_hypotheses"] for r in results) / n,
        "limitations": [
            "This is an exact enumerative symbolic solver, not a trained neural model.",
            "The hypothesis class is known in advance and contains 27 affine rules.",
            "Each episode supplies labeled support examples from its own rule.",
            "Only one query is held out per episode; broader query coverage is future work.",
            "This does not test natural language, causal discovery, or learned dynamic hyperedges."
        ],
    }


def run_support_sweep(seeds: int = 20, start_seed: int = 7) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    rows = []
    for support_size in range(1, len(QUERIES)):
        runs = [run(seed=start_seed + offset, support_size=support_size)
                for offset in range(seeds)]
        rows.append({
            "support_size": support_size,
            "identification_coverage_mean": sum(
                r["identification_coverage"] for r in runs) / seeds,
            "all_episode_accuracy_mean": sum(
                r["accuracy_on_all_episodes"] for r in runs) / seeds,
            "identified_accuracy_pooled": (
                sum((r["accuracy_when_identified"] or 0.0)
                    * r["identified_episode_count"] for r in runs)
                / sum(r["identified_episode_count"] for r in runs)
                if sum(r["identified_episode_count"] for r in runs) else None
            ),
            "mean_consistent_hypotheses": sum(
                r["mean_consistent_hypotheses"] for r in runs) / seeds,
            "seeds": seeds,
        })
    return {
        "task": "Z3_affine_rule_family_support_sweep",
        "hypothesis_class_size": len(RULES),
        "seed_start": start_seed,
        "support_sweep": rows,
        "interpretation": (
            "Coverage is the fraction of episodes where all support-consistent "
            "hypotheses agree on the held-out query. It is not neural-model accuracy."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--support-size", type=int, default=6)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = (run_support_sweep(args.seeds, args.start_seed) if args.sweep
              else run(args.seed, args.support_size))
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
