"""E02-B ternary finite-field relation diagnostic.

A query fixes (a, b) in Z_3^2. The three candidates are c in Z_3;
the unique correct candidate satisfies a + b + c == 0 (mod 3).
Each complete block contains all nine (a, b) queries exactly once.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import product


VALUES = (0, 1, 2)
QUERIES = tuple(product(VALUES, repeat=2))


@dataclass(frozen=True)
class Example:
    candidates: tuple[tuple[int, int, int], ...]
    target: int


def make_dataset(n: int, seed: int) -> list[Example]:
    """Create n examples in complete nine-query blocks.

    Candidate order and query order are independently shuffled per block.
    The target is determined by the ternary additive relation, not by a
    sampled lookup table. n must be divisible by nine for exact balance.
    """
    if n <= 0 or n % 9:
        raise ValueError("n must be a positive multiple of 9")
    rng = random.Random(seed)
    out: list[Example] = []
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


def pair_marginal_counts(data: list[Example]) -> dict[str, dict[tuple[int, int], int]]:
    """Count role-pair values separately for positive and negative choices."""
    counts = {"positive": {}, "negative": {}}
    for ex in data:
        for i, triple in enumerate(ex.candidates):
            label = "positive" if i == ex.target else "negative"
            for pair_name, pair in (
                ("ab", (triple[0], triple[1])),
                ("ac", (triple[0], triple[2])),
                ("bc", (triple[1], triple[2])),
            ):
                key = (pair_name, *pair)
                counts[label][key] = counts[label].get(key, 0) + 1
    return counts


def assert_pairwise_balanced(data: list[Example]) -> None:
    """Raise AssertionError unless every role-pair cell is class-balanced."""
    counts = pair_marginal_counts(data)
    positive, negative = counts["positive"], counts["negative"]
    if set(positive) != set(negative):
        raise AssertionError("positive and negative pair supports differ")
    for key in positive:
        if negative[key] != 2 * positive[key]:
            raise AssertionError(f"pair marginal imbalance at {key}: "
                                 f"{positive[key]} vs {negative[key]}")


def main() -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", type=int, default=900)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    data = make_dataset(args.examples, args.seed)
    assert_pairwise_balanced(data)
    print(json.dumps({
        "task": "ternary_mod3_additive_relation",
        "examples": len(data),
        "queries_per_block": 9,
        "candidates_per_query": 3,
        "pairwise_marginals_exactly_balanced": True,
        "rule": "(a + b + c) % 3 == 0",
        "seed": args.seed,
        "caveat": "Generator audit only; no learner comparison or OOD claim."
    }, indent=2))


if __name__ == "__main__":
    main()
