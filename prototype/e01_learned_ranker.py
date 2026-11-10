"""E01: learn a sparse, non-adjacent composition rule from synthetic data.

The task provides a query vector and candidate feature vectors. A hidden
linear compatibility rule determines which k candidates belong to the target
composition. The learner sees many combinations and must rank candidates in
held-out examples. This isolates composition selection from language parsing.

This is a small CPU-friendly research baseline, not a language model.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Example:
    query: tuple[float, ...]
    candidates: tuple[tuple[float, ...], ...]
    targets: tuple[int, ...]


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def make_dataset(
    count: int,
    seed: int,
    candidate_count: int = 7,
    feature_dim: int = 6,
    choose_k: int = 3,
    noise_std: float = 0.04,
) -> list[Example]:
    if not 0 < choose_k < candidate_count:
        raise ValueError("choose_k must be between 1 and candidate_count - 1")
    rng = random.Random(seed)
    data = []
    for _ in range(count):
        query = tuple(rng.uniform(-1.0, 1.0) for _ in range(feature_dim))
        candidates = tuple(
            tuple(rng.uniform(-1.0, 1.0) for _ in range(feature_dim))
            for _ in range(candidate_count)
        )
        utilities = [
            dot(query, item) + rng.gauss(0.0, noise_std)
            for item in candidates
        ]
        targets = tuple(sorted(sorted(
            range(candidate_count), key=lambda i: utilities[i], reverse=True
        )[:choose_k]))
        data.append(Example(query, candidates, targets))
    return data


def interaction_features(query: Sequence[float], item: Sequence[float]) -> list[float]:
    return [q * x for q, x in zip(query, item)]


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def train_ranker(
    data: Sequence[Example],
    feature_dim: int,
    epochs: int = 180,
    learning_rate: float = 0.8,
    l2: float = 1e-4,
) -> list[float]:
    """Full-batch logistic ranking scorer trained with binary cross-entropy."""
    weights = [0.0] * feature_dim
    rows = []
    for example in data:
        target_set = set(example.targets)
        for index, item in enumerate(example.candidates):
            rows.append((
                interaction_features(example.query, item),
                1.0 if index in target_set else 0.0,
            ))

    for _ in range(epochs):
        gradients = [0.0] * feature_dim
        for features, label in rows:
            error = sigmoid(dot(weights, features)) - label
            for j, value in enumerate(features):
                gradients[j] += error * value
        scale = 1.0 / max(1, len(rows))
        for j in range(feature_dim):
            gradients[j] = gradients[j] * scale + l2 * weights[j]
            weights[j] -= learning_rate * gradients[j]
    return weights


def predict_indices(example: Example, weights: Sequence[float], k: int) -> tuple[int, ...]:
    scores = [
        dot(weights, interaction_features(example.query, item))
        for item in example.candidates
    ]
    return tuple(sorted(sorted(
        range(len(scores)), key=lambda i: scores[i], reverse=True
    )[:k]))


def score_predictions(
    data: Sequence[Example],
    predictions: Sequence[Sequence[int]],
) -> dict[str, float]:
    exact = 0
    tp = fp = fn = 0
    for example, predicted in zip(data, predictions):
        p, t = set(predicted), set(example.targets)
        exact += int(p == t)
        tp += len(p & t)
        fp += len(p - t)
        fn += len(t - p)
    total = max(1, len(data))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "exact_match": exact / total,
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": f1,
    }


def run_experiment(
    seed: int = 7,
    train_count: int = 1200,
    test_count: int = 400,
    candidate_count: int = 7,
    feature_dim: int = 6,
    choose_k: int = 3,
) -> dict:
    train = make_dataset(train_count, seed, candidate_count, feature_dim, choose_k)
    test = make_dataset(test_count, seed + 1, candidate_count, feature_dim, choose_k)
    weights = train_ranker(train, feature_dim)

    learned = [predict_indices(row, weights, choose_k) for row in test]
    adjacent = [tuple(range(choose_k)) for _ in test]

    random_predictions = []
    for i, _ in enumerate(test):
        rng = random.Random(seed * 100000 + i)
        random_predictions.append(tuple(sorted(
            rng.sample(range(candidate_count), choose_k)
        )))

    oracle = [row.targets for row in test]
    return {
        "experiment": "E01-learned-sparse-composition",
        "seed": seed,
        "train_samples": train_count,
        "test_samples": test_count,
        "candidate_count": candidate_count,
        "feature_dim": feature_dim,
        "selected_per_example": choose_k,
        "metrics": {
            "learned_ranker": score_predictions(test, learned),
            "adjacent_prefix_baseline": score_predictions(test, adjacent),
            "random_baseline": score_predictions(test, random_predictions),
            "oracle_upper_bound": score_predictions(test, oracle),
        },
        "learned_weights": weights,
        "interpretation": (
            "Synthetic controlled task only. Results do not establish natural-language "
            "understanding, general intelligence, or superiority to Transformer models."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=1200)
    parser.add_argument("--test-samples", type=int, default=400)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_experiment(args.seed, args.train_samples, args.test_samples)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
