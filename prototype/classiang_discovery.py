"""Bounded, evidence-grounded unsupervised class candidate discovery.

This frequent-conjunction baseline sees only observed object features and
provenance, never evaluator labels or hidden class schemas.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Sequence

from prototype.classiang_engine import FeatureAtom


@dataclass(frozen=True)
class ObjectView:
    object_id: str
    features: tuple[FeatureAtom, ...]
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        _text(self.object_id, "object_id")
        _unique_texts(self.evidence_refs, "evidence_refs", allow_empty=False)
        if not isinstance(self.features, tuple):
            raise ValueError("features must be a tuple")
        for feature in self.features:
            if not isinstance(feature, FeatureAtom):
                raise ValueError("features must contain FeatureAtom")
            feature.validate()
        if self.features != tuple(sorted(set(self.features))):
            raise ValueError("features must be sorted and unique")


@dataclass(frozen=True)
class ClassCandidate:
    candidate_id: str
    features: tuple[FeatureAtom, ...]
    support_count: int
    support: float
    member_object_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    status: str = "unreviewed_candidate"


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[ClassCandidate, ...]
    candidate_evaluations: int
    max_candidate_evaluations: int
    search_truncated: bool
    results_truncated: bool
    object_count: int
    vocabulary_size: int


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")


def _unique_texts(values: tuple[str, ...], field: str, *, allow_empty: bool) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be a tuple")
    for value in values:
        _text(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique")
    if not allow_empty and not values:
        raise ValueError(f"{field} must not be empty")


def _validate_objects(objects: Sequence[ObjectView]) -> tuple[ObjectView, ...]:
    if not isinstance(objects, Sequence) or not objects:
        raise ValueError("objects must be a non-empty sequence")
    rows = tuple(objects)
    ids = []
    for row in rows:
        if not isinstance(row, ObjectView):
            raise ValueError("objects must contain ObjectView")
        row.validate()
        ids.append(row.object_id)
    if len(ids) != len(set(ids)):
        raise ValueError("object IDs must be unique")
    return rows


def _join_candidates(previous: tuple[tuple[FeatureAtom, ...], ...], order: int):
    """Generate candidates only when every immediate subset was frequent."""
    previous_set = set(previous)
    proposed: set[tuple[FeatureAtom, ...]] = set()
    for left, right in combinations(previous, 2):
        merged = tuple(sorted(set(left) | set(right)))
        if len(merged) != order:
            continue
        if all(tuple(subset) in previous_set
               for subset in combinations(merged, order - 1)):
            proposed.add(merged)
    return tuple(sorted(proposed))


def discover_classes(
    objects: Sequence[ObjectView],
    *,
    min_support: float = 0.1,
    max_order: int = 3,
    max_candidate_evaluations: int = 10000,
    max_results: int = 100,
) -> DiscoveryResult:
    """Propose recurring feature conjunctions with explicit search budgets.

    Search is Apriori-pruned: a conjunction is considered only if every
    immediate subset met the support threshold. Truncation makes no
    completeness or optimality claim. Candidates remain unreviewed hypotheses.
    """
    rows = _validate_objects(objects)
    if (isinstance(min_support, bool) or not isinstance(min_support, (int, float))
            or not math.isfinite(min_support) or not 0.0 < min_support <= 1.0):
        raise ValueError("min_support must be finite and in (0, 1]")
    if isinstance(max_order, bool) or not isinstance(max_order, int) or not 1 <= max_order <= 5:
        raise ValueError("max_order must be an integer between 1 and 5")
    if (isinstance(max_candidate_evaluations, bool)
            or not isinstance(max_candidate_evaluations, int)
            or max_candidate_evaluations < 1):
        raise ValueError("max_candidate_evaluations must be a positive integer")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 1:
        raise ValueError("max_results must be a positive integer")

    vocabulary = tuple(sorted(set().union(*(set(row.features) for row in rows))))
    min_count = math.ceil(min_support * len(rows))
    frequent: tuple[tuple[FeatureAtom, ...], ...] = tuple((item,) for item in vocabulary)
    evaluated = 0
    retained: list[tuple[tuple[FeatureAtom, ...], tuple[str, ...], tuple[str, ...]]] = []
    truncated = False

    for order in range(1, max_order + 1):
        candidates = frequent if order == 1 else _join_candidates(frequent, order)
        if not candidates:
            break
        next_frequent = []
        for candidate in candidates:
            if evaluated >= max_candidate_evaluations:
                truncated = True
                break
            members = tuple(
                row for row in rows if set(candidate).issubset(set(row.features))
            )
            evaluated += 1
            if len(members) < min_count:
                continue
            next_frequent.append(candidate)
            member_ids = tuple(sorted(row.object_id for row in members))
            evidence = tuple(sorted({
                ref for row in members for ref in row.evidence_refs
            }))
            retained.append((candidate, member_ids, evidence))
        frequent = tuple(next_frequent)
        if truncated or not frequent:
            break

    retained.sort(key=lambda item: (
        -len(item[1]) / len(rows), -len(item[0]), item[0]
    ))
    all_candidates = tuple(
        ClassCandidate(
            candidate_id=f"class-candidate-{index:05d}",
            features=features,
            support_count=len(member_ids),
            support=len(member_ids) / len(rows),
            member_object_ids=member_ids,
            evidence_refs=evidence,
        )
        for index, (features, member_ids, evidence) in enumerate(retained, start=1)
    )
    return DiscoveryResult(
        candidates=all_candidates[:max_results],
        candidate_evaluations=evaluated,
        max_candidate_evaluations=max_candidate_evaluations,
        search_truncated=truncated,
        results_truncated=len(all_candidates) > max_results,
        object_count=len(rows),
        vocabulary_size=len(vocabulary),
    )
