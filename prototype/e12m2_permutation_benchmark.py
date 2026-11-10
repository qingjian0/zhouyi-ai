"""E12-M2.1: degree-preserving permutation tests for discovered motifs.

The null model preserves every observation's cardinality and every item's
marginal frequency. It randomizes only the bipartite row-item incidence graph.
This is a conditional association test, not a causal or semantic test.
"""
from __future__ import annotations

import itertools
import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PermutationResult:
    members: tuple[str, ...]
    observed_score: float
    null_mean_score: float
    p_value: float
    max_statistic_p_value: float
    attempted_swaps: int
    accepted_swaps: int
    acceptance_rate: float
    permutations: int


def _normalize(observations: Iterable[Iterable[str]]) -> list[set[str]]:
    rows: list[set[str]] = []
    for row in observations:
        items = set(row)
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError("items must be non-empty strings")
        rows.append(items)
    return rows


def _edge_list(rows: Sequence[set[str]]) -> list[tuple[int, str]]:
    return [(row_index, item) for row_index, row in enumerate(rows) for item in row]


def degree_preserving_swaps(
    observations: Iterable[Iterable[str]],
    *,
    swaps: int,
    seed: int = 0,
) -> tuple[list[set[str]], int]:
    """Perform bipartite 2-switches; preserve row and item degrees exactly.

    A switch replaces (r1, i1), (r2, i2) with (r1, i2), (r2, i1).
    It is accepted only when both cross edges are absent. The returned integer
    is the number of accepted switches; 'swaps' is the number of attempts.
    """
    if isinstance(swaps, bool) or not isinstance(swaps, int) or swaps < 0:
        raise ValueError("swaps must be a non-negative integer")
    rows = _normalize(observations)
    edges = _edge_list(rows)
    rng = random.Random(seed)
    accepted = 0
    if len(edges) < 2:
        return rows, accepted

    for _ in range(swaps):
        index1, index2 = rng.sample(range(len(edges)), 2)
        r1, i1 = edges[index1]
        r2, i2 = edges[index2]
        if r1 == r2 or i1 == i2:
            continue
        if i2 in rows[r1] or i1 in rows[r2]:
            continue
        rows[r1].remove(i1)
        rows[r2].remove(i2)
        rows[r1].add(i2)
        rows[r2].add(i1)
        # Keep the incidence-edge index synchronized in O(1); rebuilding it
        # after each accepted move would make long chains unnecessarily costly.
        edges[index1] = (r1, i2)
        edges[index2] = (r2, i1)
        accepted += 1
    return rows, accepted


def _motif_score(rows: Sequence[set[str]], members: tuple[str, ...]) -> float:
    n = len(rows)
    if n == 0:
        return 0.0
    if len(members) < 2 or len(set(members)) != len(members):
        raise ValueError("members must contain at least two distinct items")
    singleton = Counter(item for row in rows for item in row)
    if any(singleton[item] == 0 for item in members):
        return 0.0
    count = sum(all(item in row for item in members) for row in rows)
    support = count / n
    expected = math.prod(singleton[item] / n for item in members)
    if support <= 0 or expected <= 0:
        return 0.0
    return math.log(support / expected) * math.sqrt(support)


def _max_motif_score(rows: Sequence[set[str]], max_order: int) -> float:
    universe = sorted(set().union(*rows)) if rows else []
    scores = (
        _motif_score(rows, members)
        for order in range(2, min(max_order, len(universe)) + 1)
        for members in itertools.combinations(universe, order)
    )
    return max(scores, default=0.0)


def permutation_test(
    observations: Iterable[Iterable[str]],
    members: Sequence[str],
    *,
    permutations: int = 199,
    swaps_per_edge: int = 10,
    max_order: int = 3,
    seed: int = 0,
) -> PermutationResult:
    """Test one pre-specified motif against a degree-preserving null.

    p_value compares the same candidate's score in observed and null data.
    max_statistic_p_value additionally controls candidate-set selection by
    comparing the observed candidate score with each null dataset's maximum
    score over all combinations up to max_order.
    """
    if isinstance(permutations, bool) or not isinstance(permutations, int) or permutations < 1:
        raise ValueError("permutations must be a positive integer")
    if isinstance(swaps_per_edge, bool) or not isinstance(swaps_per_edge, int) or swaps_per_edge < 1:
        raise ValueError("swaps_per_edge must be a positive integer")
    if isinstance(max_order, bool) or not isinstance(max_order, int) or max_order < 2:
        raise ValueError("max_order must be an integer >= 2")
    candidate = tuple(sorted(members))
    if len(candidate) < 2 or len(set(candidate)) != len(candidate):
        raise ValueError("members must contain at least two distinct items")

    original = _normalize(observations)
    observed = _motif_score(original, candidate)
    edge_count = len(_edge_list(original))
    attempts_each = max(1, swaps_per_edge * edge_count)
    chain = [set(row) for row in original]
    rng = random.Random(seed)
    null_scores: list[float] = []
    null_maxima: list[float] = []
    attempted_total = accepted_total = 0

    for _ in range(permutations):
        # Draw a deterministic, continuing Markov chain rather than restarting
        # from the observed graph for every replicate.
        chain, accepted = degree_preserving_swaps(
            chain, swaps=attempts_each, seed=rng.randrange(0, 2**63)
        )
        attempted_total += attempts_each
        accepted_total += accepted
        null_scores.append(_motif_score(chain, candidate))
        null_maxima.append(_max_motif_score(chain, max_order))

    exceed = sum(score >= observed for score in null_scores)
    max_exceed = sum(score >= observed for score in null_maxima)
    return PermutationResult(
        members=candidate,
        observed_score=observed,
        null_mean_score=sum(null_scores) / permutations,
        p_value=(1 + exceed) / (permutations + 1),
        max_statistic_p_value=(1 + max_exceed) / (permutations + 1),
        attempted_swaps=attempted_total,
        accepted_swaps=accepted_total,
        acceptance_rate=(accepted_total / attempted_total) if attempted_total else 0.0,
        permutations=permutations,
    )
