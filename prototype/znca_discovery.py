"""ZNCA N3: bounded candidate discovery from state-transition observations.

This module proposes candidate interactions from data; it does not claim
causal identification. Candidate selection must be followed by held-out tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Iterable

from prototype.znca_dynamics import (
    InfluenceTerm, SourceSlot, StateSnapshot, TransitionExample,
)


class DiscoveryError(ValueError):
    """Invalid candidate-discovery configuration or data."""


@dataclass(frozen=True)
class CandidateScore:
    target: str
    source_keys: tuple[str, ...]
    negated_keys: tuple[str, ...]
    polarity: int
    score: float
    support: int


@dataclass(frozen=True)
class DiscoveryReport:
    candidates_considered: int
    candidates_selected: int
    budget_exhausted: bool
    scores: tuple[CandidateScore, ...]
    terms: tuple[InfluenceTerm, ...]


def _validate_examples(rows: tuple[TransitionExample, ...]) -> tuple[str, ...]:
    if not rows:
        raise DiscoveryError("at least one transition example is required")
    keys = tuple(sorted(rows[0].before.as_dict()))
    if any(tuple(sorted(row.before.as_dict())) != keys for row in rows):
        raise DiscoveryError("all before states must share one schema")
    if any(tuple(sorted(row.after.as_dict())) != keys for row in rows):
        raise DiscoveryError("all after states must share one schema")
    return keys


def discover_candidates(
    examples: Iterable[TransitionExample],
    *,
    max_arity: int = 3,
    candidate_budget: int = 10_000,
    max_terms_per_target: int = 8,
    min_abs_score: float = 1e-6,
) -> DiscoveryReport:
    """Rank interaction products by training-set residual association.

    For each target, the baseline is its training-set mean. Candidate features
    are conjunctions of literals: each selected variable may be positive x
    or complemented (1-x). The absolute centered covariance ranks candidates.
    The sign proposes promotion/inhibition. This is association, not causation.
    """
    rows = tuple(examples)
    keys = _validate_examples(rows)
    if max_arity < 1 or candidate_budget < 1 or max_terms_per_target < 1:
        raise DiscoveryError("arity, budget and max_terms_per_target must be positive")
    if not math.isfinite(min_abs_score) or min_abs_score < 0:
        raise DiscoveryError("min_abs_score must be finite and non-negative")

    before = [row.before.as_dict() for row in rows]
    after = [row.after.as_dict() for row in rows]
    evidence = tuple(sorted({row.evidence_ref for row in rows}))
    selected: list[CandidateScore] = []
    considered = 0
    exhausted = False

    for target in keys:
        y = [state[target] for state in after]
        mean_y = sum(y) / len(y)
        residual = [value - mean_y for value in y]
        ranked: list[CandidateScore] = []
        source_keys = [key for key in keys if key != target]
        for arity in range(1, min(max_arity, len(source_keys)) + 1):
            for combo in combinations(source_keys, arity):
                for mask in range(1 << arity):
                    if considered >= candidate_budget:
                        exhausted = True
                        break
                    considered += 1
                    negated = tuple(
                        key for index, key in enumerate(combo)
                        if mask & (1 << index)
                    )
                    products = [
                        math.prod(
                            (1.0 - state[key]) if key in negated else state[key]
                            for key in combo
                        )
                        for state in before
                    ]
                    mean_product = sum(products) / len(products)
                    score = sum(
                        (p - mean_product) * r
                        for p, r in zip(products, residual)
                    ) / len(rows)
                    if abs(score) < min_abs_score:
                        continue
                    support = sum(1 for p in products if p > 0.0)
                    ranked.append(CandidateScore(
                        target, tuple(combo), negated,
                        1 if score >= 0 else -1, abs(score), support,
                    ))
                if exhausted:
                    break
            if exhausted:
                break
        ranked.sort(key=lambda item: (
            -item.score, len(item.source_keys), item.source_keys,
            item.negated_keys, item.target
        ))
        selected.extend(ranked[:max_terms_per_target])
        if exhausted:
            break

    terms = tuple(
        InfluenceTerm(
            term_id=f"n3:{item.target}:{'+'.join(('!' if key in item.negated_keys else '') + key for key in item.source_keys)}",
            relation_type="discovered_association",
            sources=tuple(
                SourceSlot(f"source_{index}", key, key in item.negated_keys)
                for index, key in enumerate(item.source_keys)
            ),
            target=item.target,
            polarity=item.polarity,
            weight=0.1,
            evidence_refs=evidence,
        )
        for item in selected
    )
    return DiscoveryReport(
        considered, len(terms), exhausted, tuple(selected), terms
    )
