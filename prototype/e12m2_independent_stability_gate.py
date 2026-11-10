"""E12-M2.4: independent validation gate for unlabeled motif candidates.

This module separates motif proposal from stability assessment. Candidates are
mined only from proposal observations; validation observations can reject or
retain them but can never introduce a new candidate.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from prototype.e12m2_motif_discovery import Motif, discover_motifs


@dataclass(frozen=True)
class MotifValidation:
    members: tuple[str, ...]
    proposal_count: int
    proposal_support: float
    proposal_lift: float
    validation_count: int
    validation_support: float
    validation_lift: float
    status: str
    reason: str | None


def _transactions(rows: Iterable[Iterable[str]]) -> list[frozenset[str]]:
    result = []
    for row in rows:
        items = frozenset(row)
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise ValueError("items must be non-empty strings")
        result.append(items)
    return result


def _stats(rows: list[frozenset[str]], members: tuple[str, ...]) -> tuple[int, float, float]:
    if not rows:
        return 0, 0.0, 0.0
    n = len(rows)
    count = sum(set(members).issubset(row) for row in rows)
    support = count / n
    singleton = {
        item: sum(item in row for row in rows) / n
        for item in members
    }
    expected = math.prod(singleton.values())
    lift = support / expected if expected > 0 else 0.0
    return count, support, lift


def validate_motif_candidates(
    proposal_observations: Iterable[Iterable[str]],
    validation_observations: Iterable[Iterable[str]],
    *,
    proposal_min_support: float = 0.08,
    proposal_min_lift: float = 1.2,
    validation_min_support: float = 0.05,
    validation_min_lift: float = 1.1,
    validation_min_count: int = 3,
    max_order: int = 3,
    max_candidates: int = 100,
) -> tuple[MotifValidation, ...]:
    """Propose on one unlabeled partition and independently validate on another.

    A STABLE_MOTIF result is only a replicated co-occurrence candidate. This
    routine does not perform a conditional permutation test, correct for
    multiple comparisons, infer semantics, or establish transfer.
    """
    for name, value in (
        ("proposal_min_support", proposal_min_support),
        ("validation_min_support", validation_min_support),
    ):
        if not math.isfinite(value) or not 0.0 < value <= 1.0:
            raise ValueError(f"{name} must be finite and in (0, 1]")
    for name, value in (
        ("proposal_min_lift", proposal_min_lift),
        ("validation_min_lift", validation_min_lift),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if isinstance(validation_min_count, bool) or not isinstance(validation_min_count, int) or validation_min_count < 1:
        raise ValueError("validation_min_count must be a positive integer")

    proposal_rows = _transactions(proposal_observations)
    validation_rows = _transactions(validation_observations)
    proposals: tuple[Motif, ...] = tuple(discover_motifs(
        proposal_rows,
        min_support=proposal_min_support,
        min_lift=proposal_min_lift,
        max_order=max_order,
        max_candidates=max_candidates,
    ))

    results = []
    for motif in proposals:
        count, support, lift = _stats(validation_rows, motif.members)
        reasons = []
        if not validation_rows:
            reasons.append("empty_validation_partition")
        if count < validation_min_count:
            reasons.append("insufficient_validation_count")
        if support < validation_min_support:
            reasons.append("validation_support_below_threshold")
        if lift < validation_min_lift:
            reasons.append("validation_lift_below_threshold")
        results.append(MotifValidation(
            members=motif.members,
            proposal_count=motif.count,
            proposal_support=motif.support,
            proposal_lift=motif.lift,
            validation_count=count,
            validation_support=support,
            validation_lift=lift,
            status="STABLE_MOTIF" if not reasons else "REJECTED",
            reason=None if not reasons else ";".join(reasons),
        ))
    return tuple(results)
