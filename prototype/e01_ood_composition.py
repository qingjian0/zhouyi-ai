"""E01-C: systematic composition OOD.

Training queries contain one active primitive at a time. Test queries combine
two or three already-seen primitives. A candidate is relevant iff it contains
all active query attributes. Distractors are hard negatives: each misses at
least one required attribute. This isolates compositional recombination.
"""
from __future__ import annotations

import argparse
import json
import random

from prototype.e01_learned_ranker import (
    Example,
    predict_indices,
    score_predictions,
    train_ranker,
)


def make_query_dataset(
    count: int,
    seed: int,
    query_cardinality: int,
    candidate_count: int = 7,
    feature_dim: int = 6,
) -> list[Example]:
    if not 1 <= query_cardinality <= feature_dim:
        raise ValueError("query_cardinality must be within feature_dim")
    if candidate_count < 2:
        raise ValueError("candidate_count must be at least 2")
    rng = random.Random(seed)
    data = []
    for _ in range(count):
        active = set(rng.sample(range(feature_dim), query_cardinality))
        query = tuple(1.0 if j in active else 0.0 for j in range(feature_dim))

        target = [rng.randint(0, 1) for _ in range(feature_dim)]
        for j in active:
            target[j] = 1

        candidates = []
        target_position = rng.randrange(candidate_count)
        for index in range(candidate_count):
            if index == target_position:
                item = list(target)
            else:
                item = [rng.randint(0, 1) for _ in range(feature_dim)]
                # A hard negative misses at least one required primitive.
                missing = rng.choice(tuple(active))
                for j in active:
                    item[j] = 1
                item[missing] = 0
            candidates.append(tuple(float(v) for v in item))

        data.append(Example(query, tuple(candidates), (target_position,)))
    return data


def run_ood_experiment(
    seed: int = 7,
    train_count: int = 1600,
    test_count: int = 500,
    train_query_cardinality: int = 1,
    test_query_cardinality: int = 2,
) -> dict:
    train = make_query_dataset(train_count, seed, train_query_cardinality)
    test = make_query_dataset(test_count, seed + 1, test_query_cardinality)
    weights = train_ranker(train, feature_dim=6, epochs=220, learning_rate=0.65)

    learned = [predict_indices(row, weights, k=1) for row in test]
    adjacent = [(0,) for _ in test]
    random_predictions = []
    for i, _ in enumerate(test):
        rng = random.Random(seed * 100000 + i)
        random_predictions.append((rng.randrange(7),))

    return {
        "experiment": "E01-C-compositional-OOD",
        "seed": seed,
        "train_query_cardinality": train_query_cardinality,
        "test_query_cardinality": test_query_cardinality,
        "train_samples": train_count,
        "test_samples": test_count,
        "candidate_count": 7,
        "feature_dim": 6,
        "metrics": {
            "learned_ranker": score_predictions(test, learned),
            "adjacent_prefix_baseline": score_predictions(test, adjacent),
            "random_baseline": score_predictions(test, random_predictions),
            "oracle_upper_bound": score_predictions(
                test, [row.targets for row in test]
            ),
        },
        "learned_weights": weights,
        "interpretation": (
            "Compositional OOD over binary attribute conjunctions: test queries "
            "combine primitives only observed individually during training. "
            "This is still a controlled synthetic task, not natural language."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=1600)
    parser.add_argument("--test-samples", type=int, default=500)
    parser.add_argument("--test-cardinality", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_ood_experiment(
        seed=args.seed,
        train_count=args.train_samples,
        test_count=args.test_samples,
        test_query_cardinality=args.test_cardinality,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
