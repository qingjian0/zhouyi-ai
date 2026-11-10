"""E02-B learner comparison on a ternary modular relation.

This is a controlled in-distribution diagnostic. Pairwise and static
third-order learners share the same optimizer, examples, and update budget.
It does not establish rule-family OOD generalization or dynamic hypergraph
learning.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from typing import Iterable

VALUES = (0, 1, 2)
QUERIES = tuple((a, b) for a in VALUES for b in VALUES)


@dataclass(frozen=True)
class Example:
    candidates: tuple[tuple[int, int, int], ...]
    target: int


def make_dataset(n: int, seed: int) -> list[Example]:
    if n <= 0 or n % 9:
        raise ValueError("n must be a positive multiple of 9")
    rng = random.Random(seed)
    out = []
    for _ in range(n // 9):
        queries = list(QUERIES)
        rng.shuffle(queries)
        for a, b in queries:
            candidates = [(a, b, c) for c in VALUES]
            rng.shuffle(candidates)
            target_c = (-(a + b)) % 3
            out.append(Example(tuple(candidates),
                               next(i for i, x in enumerate(candidates)
                                    if x[2] == target_c)))
    return out


def feature_vector(x: tuple[int, int, int], order: int) -> list[float]:
    """Categorical role features; order=2 has singles+pairs, order=3 adds triples."""
    a, b, c = x
    out = [0.0] * (9 + 27 + (27 if order >= 3 else 0))
    out[a] = 1.0
    out[3 + b] = 1.0
    out[6 + c] = 1.0
    out[9 + a * 3 + b] = 1.0
    out[18 + a * 3 + c] = 1.0
    out[27 + b * 3 + c] = 1.0
    if order >= 3:
        out[36 + (a * 3 + b) * 3 + c] = 1.0
    return out


def fit(data: Iterable[Example], order: int, epochs: int = 350,
        lr: float = 0.35, l2: float = 0.01) -> list[float]:
    rows = [(tuple(feature_vector(x, order) for x in ex.candidates), ex.target)
            for ex in data]
    if not rows:
        raise ValueError("training data must not be empty")
    width = len(rows[0][0][0])
    weights = [0.0] * width
    for _ in range(epochs):
        grad = [0.0] * width
        for candidates, target in rows:
            scores = [sum(w * v for w, v in zip(weights, x))
                      for x in candidates]
            peak = max(scores)
            exp_scores = [math.exp(s - peak) for s in scores]
            denom = sum(exp_scores)
            probs = [v / denom for v in exp_scores]
            for i, x in enumerate(candidates):
                error = probs[i] - (1.0 if i == target else 0.0)
                for j, value in enumerate(x):
                    grad[j] += error * value
        scale = 1.0 / len(rows)
        for j in range(width):
            weights[j] -= lr * (grad[j] * scale + l2 * weights[j])
    return weights


def predict(ex: Example, weights: list[float], order: int) -> int:
    scores = [sum(w * v for w, v in zip(weights, feature_vector(x, order)))
              for x in ex.candidates]
    return max(range(3), key=lambda i: (scores[i], -i))


def accuracy(data: list[Example], weights: list[float], order: int) -> float:
    if not data:
        raise ValueError("evaluation data must not be empty")
    return sum(predict(ex, weights, order) == ex.target for ex in data) / len(data)


def run_seed(seed: int, train_n: int = 900, val_n: int = 180,
             test_n: int = 180) -> dict:
    seeds = {"train": seed * 1009 + 11,
             "validation": seed * 1009 + 22,
             "test": seed * 1009 + 33}
    train = make_dataset(train_n, seeds["train"])
    val = make_dataset(val_n, seeds["validation"])
    test = make_dataset(test_n, seeds["test"])
    pair = fit(train, 2)
    triple = fit(train, 3)
    pair_val = accuracy(val, pair, 2)
    triple_val = accuracy(val, triple, 3)
    create = triple_val > pair_val + 0.01
    chosen, chosen_order = (triple, 3) if create else (pair, 2)
    return {
        "seed": seed,
        "data_seeds": seeds,
        "train_examples": train_n,
        "validation_examples": val_n,
        "test_examples": test_n,
        "pairwise_parameters": len(pair),
        "third_order_parameters": len(triple),
        "epochs": 350,
        "pairwise_validation_accuracy": pair_val,
        "third_order_validation_accuracy": triple_val,
        "pairwise_test_accuracy": accuracy(test, pair, 2),
        "third_order_test_accuracy": accuracy(test, triple, 3),
        "validation_gate_created_triple": create,
        "gated_test_accuracy": accuracy(test, chosen, chosen_order),
    }


def run(seeds: int = 5, start_seed: int = 7) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be >= 1")
    results = [run_seed(start_seed + i) for i in range(seeds)]
    metrics = ("pairwise_test_accuracy", "third_order_test_accuracy",
               "gated_test_accuracy")
    summary = {}
    for key in metrics:
        vals = [row[key] for row in results]
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        summary[key] = {"mean": mean, "sample_std": math.sqrt(variance)}
    summary["validation_gate_create_rate"] = sum(
        row["validation_gate_created_triple"] for row in results) / len(results)
    return {
        "task": "ternary_mod3_additive_relation",
        "evaluation": "in_distribution_randomized_query_and_candidate_order",
        "seeds": results,
        "summary": summary,
        "limitations": [
            "The nine query values are repeated across train, validation, and test.",
            "This does not test unseen rule families or symbol remapping.",
            "The third-order model has more parameters than the pairwise model.",
            "A validation gate is a simple baseline, not a learned dynamic hypergraph."
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seeds, args.start_seed)
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
