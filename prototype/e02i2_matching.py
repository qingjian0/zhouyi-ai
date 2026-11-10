"""E02-I2-B: deterministic candidate-to-identity matching baselines.

These methods are explicit baselines, not learned identity discovery. They only
propose one-to-one continuity links and can abstain when evidence is weak or
ambiguous. Split/merge inference is deliberately out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from prototype.e02i2_lineage import RelationVersion


class MatchingMethod(str, Enum):
    EXACT = "exact"
    JACCARD = "jaccard"
    ROLE_ALIGNED = "role_aligned"
    HUNGARIAN = "hungarian"


@dataclass(frozen=True)
class RelationCandidate:
    candidate_id: str
    members: tuple[str, ...]
    roles: tuple[str, ...]
    operator: str
    rule_signature: str
    context_signature: str = "global"

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate ID must be non-empty")
        if not self.members or len(set(self.members)) != len(self.members):
            raise ValueError("candidate members must be non-empty and unique")
        if len(self.roles) != len(self.members):
            raise ValueError("candidate needs one role per member")
        if any(not x.strip() for x in (*self.members, *self.roles)):
            raise ValueError("candidate members and roles must be non-empty")


@dataclass(frozen=True)
class MatchDecision:
    candidate_id: str
    identity_id: str | None
    score: float
    method: MatchingMethod
    abstained: bool
    reason: str


def _current_version(version: RelationVersion) -> tuple:
    return (
        version.members, version.roles, version.operator,
        version.rule_signature, version.context_signature,
    )


def _candidate_signature(candidate: RelationCandidate) -> tuple:
    return (
        candidate.members, candidate.roles, candidate.operator,
        candidate.rule_signature, candidate.context_signature,
    )


def _jaccard(left: Iterable[object], right: Iterable[object]) -> float:
    a, b = set(left), set(right)
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def similarity(candidate: RelationCandidate, version: RelationVersion) -> float:
    """Role-aware transparent score; coefficients are fixed, not learned."""
    member_score = _jaccard(candidate.members, version.members)
    role_score = _jaccard(
        zip(candidate.members, candidate.roles),
        zip(version.members, version.roles),
    )
    rule_score = float(candidate.rule_signature == version.rule_signature)
    operator_score = float(candidate.operator == version.operator)
    context_score = float(candidate.context_signature == version.context_signature)
    return (
        0.30 * member_score
        + 0.25 * role_score
        + 0.25 * rule_score
        + 0.10 * operator_score
        + 0.10 * context_score
    )


def _hungarian_max(weights: list[list[float]]) -> list[int]:
    """Maximum-weight rectangular assignment; rows <= columns."""
    n = len(weights)
    if n == 0:
        return []
    m = len(weights[0])
    if n > m or any(len(row) != m for row in weights):
        raise ValueError("assignment matrix must be rectangular with rows <= columns")
    max_weight = max((max(row) for row in weights), default=0.0)
    costs = [[max_weight - value for value in row] for row in weights]
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [-1] * n
    for j in range(1, m + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    return assignment


def match_candidates(
    candidates: tuple[RelationCandidate, ...],
    identities: dict[str, RelationVersion],
    *,
    method: MatchingMethod,
    min_score: float = 0.70,
    min_margin: float = 0.05,
) -> tuple[MatchDecision, ...]:
    """Match each candidate to at most one prior identity, or explicitly abstain.

    identities must contain only the current version of each eligible,
    non-terminal identity. The resolver never reads hidden identity labels.
    """
    if not 0.0 <= min_score <= 1.0 or not 0.0 <= min_margin <= 1.0:
        raise ValueError("score and margin thresholds must be in [0, 1]")
    if len({c.candidate_id for c in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be unique")
    original_order = tuple(candidate.candidate_id for candidate in candidates)
    # Stable row order makes assignment tie-breaking independent of caller order.
    candidates = tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))

    identity_ids = tuple(sorted(identities))
    score_rows: list[list[float]] = []
    for candidate in candidates:
        row = []
        for identity_id in identity_ids:
            version = identities[identity_id]
            if method == MatchingMethod.EXACT:
                score = float(_candidate_signature(candidate) == _current_version(version))
            elif method == MatchingMethod.JACCARD:
                score = _jaccard(candidate.members, version.members)
            else:
                score = similarity(candidate, version)
            row.append(score)
        score_rows.append(row)

    if method == MatchingMethod.HUNGARIAN:
        # A private dummy column per candidate makes abstention part of the
        # optimization instead of forcing every candidate onto an identity.
        weights = [
            [score if score >= min_score else 0.0 for score in row]
            + [0.0] * len(candidates)
            for row in score_rows
        ]
        assigned = _hungarian_max(weights)
    else:
        # Global deterministic greedy matching avoids input-order dependence.
        assigned = [-1] * len(candidates)
        edges = sorted(
            (
                (-score, candidates[row_index].candidate_id, identity_ids[column], row_index, column)
                for row_index, row in enumerate(score_rows)
                for column, score in enumerate(row)
                if score >= min_score
            )
        )
        used_candidates: set[int] = set()
        used_identities: set[int] = set()
        for _, _, _, row_index, column in edges:
            if row_index in used_candidates or column in used_identities:
                continue
            assigned[row_index] = column
            used_candidates.add(row_index)
            used_identities.add(column)

    decisions = []
    for candidate, row, column in zip(candidates, score_rows, assigned):
        best = row[column] if 0 <= column < len(identity_ids) else 0.0
        if not identity_ids or column < 0 or best < min_score:
            decisions.append(MatchDecision(
                candidate.candidate_id, None, best, method, True,
                "no eligible identity reaches min_score",
            ))
            continue
        alternatives = [score for idx, score in enumerate(row) if idx != column]
        second = max(alternatives, default=0.0)
        if best - second < min_margin:
            decisions.append(MatchDecision(
                candidate.candidate_id, None, best, method, True,
                "top identity is insufficiently separated from alternative",
            ))
            continue
        decisions.append(MatchDecision(
            candidate.candidate_id, identity_ids[column], best, method, False,
            "matched by configured baseline",
        ))
    by_candidate = {decision.candidate_id: decision for decision in decisions}
    return tuple(by_candidate[candidate_id] for candidate_id in original_order)
