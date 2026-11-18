"""E12-M2: unsupervised recurring-motif discovery from discrete observations.

The output is a set of statistically recurring co-occurrence candidates, not
human-interpretable semantic primitives. No labels or target variable are used.
"""
from __future__ import annotations

import itertools
import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Motif:
    members: tuple[str, ...]
    count: int
    support: float
    independence_expected_support: float
    lift: float
    score: float


def discover_motifs(
    observations: Iterable[Iterable[str]],
    *,
    min_support: float = 0.1,
    max_order: int = 3,
    min_lift: float = 1.2,
    max_candidates: int = 100,
) -> list[Motif]:
    """Mine positive co-occurrence motifs using support and independence lift.

    Each observation is a set-like transaction. Duplicate items within a
    transaction are ignored. The independence expectation is the product of
    singleton marginal supports; it is a baseline, not a causal model.
    """
    if not math.isfinite(min_support) or not 0.0 < min_support <= 1.0:
        raise ValueError("min_support must be finite and in (0, 1]")
    if isinstance(max_order, bool) or not isinstance(max_order, int) or max_order < 2:
        raise ValueError("max_order must be an integer >= 2")
    if not math.isfinite(min_lift) or min_lift <= 0:
        raise ValueError("min_lift must be finite and positive")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")

    transactions: list[frozenset[str]] = []
    for row in observations:
        items = frozenset(row)
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError("items must be non-empty strings")
        transactions.append(items)
    n = len(transactions)
    if n == 0:
        return []

    singleton_counts: Counter[str] = Counter()
    item_universe: set[str] = set()
    for row in transactions:
        singleton_counts.update(row)
        item_universe.update(row)
    items = sorted(item_universe)
    singleton_support = {item: singleton_counts[item] / n for item in items}

    counts: Counter[tuple[str, ...]] = Counter()
    for row in transactions:
        ordered = sorted(row)
        for order in range(2, min(max_order, len(ordered)) + 1):
            counts.update(itertools.combinations(ordered, order))

    motifs: list[Motif] = []
    for members, count in counts.items():
        support = count / n
        if support < min_support:
            continue
        expected = math.prod(singleton_support[item] for item in members)
        if expected <= 0:
            continue
        lift = support / expected
        if lift < min_lift:
            continue
        # Reward repeatability while discounting very common, weakly associated sets.
        score = math.log(lift) * math.sqrt(support)
        motifs.append(Motif(members, count, support, expected, lift, score))

    motifs.sort(key=lambda m: (-m.score, -m.support, m.members))
    return motifs[:max_candidates]
