"""TX-02A episode generator for multi-cardinality relation induction.

The generator creates support/query episodes for hidden affine rules over
finite cyclic groups. Visible symbols are independently permuted per episode.
It is a benchmark data source, not a learner or a performance claim.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Triple:
    a: int
    b: int
    c: int


@dataclass(frozen=True)
class Episode:
    cardinality: int
    support: tuple[Triple, ...]
    queries: tuple[tuple[int, int], ...]
    candidates: tuple[tuple[int, ...], ...]
    targets: tuple[int, ...]
    # Ground-truth fields are available to tests/evaluators only and are never
    # serialized into the learner-visible episode payload.
    hidden_rule: tuple[int, int, int]
    visible_symbols: tuple[int, ...]
    symbol_mapping: str


def _validate_cardinality(k: int) -> None:
    if type(k) is not int or k < 2:
        raise ValueError("cardinality must be an integer >= 2")


def _permutation(k: int, rng: random.Random) -> tuple[int, ...]:
    values = list(range(k))
    rng.shuffle(values)
    return tuple(values)


def make_episode(
    cardinality: int,
    seed: int,
    support_size: int,
    query_count: int = 1,
    symbol_mapping: str = "permuted",
    rule: tuple[int, int, int] | None = None,
) -> Episode:
    """Create one episode with disjoint support and query input pairs.

    Hidden rule: c=(alpha*a + beta*b + delta) mod K in canonical symbols.
    Each episode uses a fresh visible-symbol bijection and shuffled candidates.
    """
    _validate_cardinality(cardinality)
    total = cardinality * cardinality
    if type(support_size) is not int or not 1 <= support_size < total:
        raise ValueError("support_size must be in [1, K*K)")
    if type(query_count) is not int or not 1 <= query_count <= total - support_size:
        raise ValueError("query_count must fit among pairs not used by support")

    if symbol_mapping not in ("canonical", "permuted"):
        raise ValueError("symbol_mapping must be 'canonical' or 'permuted'")
    rng = random.Random(seed)
    k = cardinality
    if rule is None:
        alpha, beta, delta = (rng.randrange(k) for _ in range(3))
    else:
        if (not isinstance(rule, tuple) or len(rule) != 3 or
                any(type(value) is not int or not 0 <= value < k for value in rule)):
            raise ValueError("rule must be a tuple of three integers in [0, K)")
        alpha, beta, delta = rule
    visible = tuple(range(k)) if symbol_mapping == "canonical" else _permutation(k, rng)

    pairs = [(a, b) for a in range(k) for b in range(k)]
    rng.shuffle(pairs)
    support_pairs = pairs[:support_size]
    query_pairs = pairs[support_size:support_size + query_count]

    support = tuple(
        Triple(visible[a], visible[b], visible[(alpha * a + beta * b + delta) % k])
        for a, b in support_pairs
    )

    candidate_rows: list[tuple[int, ...]] = []
    targets: list[int] = []
    for a, b in query_pairs:
        candidates = list(range(k))
        rng.shuffle(candidates)
        correct = visible[(alpha * a + beta * b + delta) % k]
        candidate_rows.append(tuple(candidates))
        targets.append(candidates.index(correct))

    return Episode(
        cardinality=k,
        support=support,
        queries=tuple((visible[a], visible[b]) for a, b in query_pairs),
        candidates=tuple(candidate_rows),
        targets=tuple(targets),
        hidden_rule=(alpha, beta, delta),
        visible_symbols=visible,
        symbol_mapping=symbol_mapping,
    )


def episode_to_dict(episode: Episode) -> dict[str, Any]:
    """Return only learner-visible information; never leak hidden rule fields."""
    return {
        "cardinality": episode.cardinality,
        "symbol_mapping": episode.symbol_mapping,
        "support": [[x.a, x.b, x.c] for x in episode.support],
        "queries": [list(x) for x in episode.queries],
        "candidates": [list(x) for x in episode.candidates],
        "targets": list(episode.targets),
        "target_semantics": "index into the corresponding shuffled candidate row",
    }


def make_benchmark(
    cardinalities: tuple[int, ...] = (2, 3, 4, 5),
    episodes_per_cardinality: int = 20,
    support_size: int = 2,
    query_count: int = 2,
    seed: int = 20261111,
    symbol_mappings: tuple[str, ...] = ("canonical", "permuted"),
) -> dict[str, Any]:
    if episodes_per_cardinality < 1:
        raise ValueError("episodes_per_cardinality must be >= 1")
    rng = random.Random(seed)
    episodes = []
    for k in cardinalities:
        _validate_cardinality(k)
        for mapping in symbol_mappings:
            for _ in range(episodes_per_cardinality):
                episode_seed = rng.randrange(0, 2**63)
                episodes.append(episode_to_dict(
                    make_episode(k, episode_seed, support_size, query_count, mapping)
                ))
    return {
        "protocol": "TX-02A",
        "seed": seed,
        "episodes_per_cardinality": episodes_per_cardinality,
        "support_size": support_size,
        "query_count": query_count,
        "cardinalities": list(cardinalities),
        "symbol_mappings": list(symbol_mappings),
        "episode_count": len(episodes),
        "episodes": episodes,
        "limitations": [
            "Synthetic finite-cyclic affine rule family only.",
            "No learner is implemented by this module.",
            "Generated data does not demonstrate representation superiority.",
            "Rule coefficients and symbol permutations are hidden from episode output."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument("--episodes-per-cardinality", type=int, default=20)
    parser.add_argument("--support-size", type=int, default=2)
    parser.add_argument("--query-count", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = make_benchmark(
        episodes_per_cardinality=args.episodes_per_cardinality,
        support_size=args.support_size,
        query_count=args.query_count,
        seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else {
        key: value for key, value in result.items() if key != "episodes"
    })


if __name__ == "__main__":
    main()
