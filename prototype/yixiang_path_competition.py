"""M12: condition-bounded competition among alternative yixiang pathways.

This is a structural evidence gate, not a path optimizer, predictor or causal
discovery engine. Competing routes are preserved rather than collapsed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class PathOutcome(str, Enum):
    VIABLE = "viable"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PathCompetitionDecision(str, Enum):
    BLOCKED = "blocked_incomplete_or_inconsistent"
    HUMAN_REVIEW = "ready_for_human_review"


@dataclass(frozen=True)
class PathCandidate:
    path_id: str
    source_node: str
    target_node: str
    ordered_states: Tuple[str, ...]
    relation_signatures: Tuple[str, ...]
    context_axes: Tuple[Tuple[str, str], ...]
    outcome: PathOutcome
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class PathCompetitionResult:
    decision: PathCompetitionDecision
    reason_codes: Tuple[str, ...]
    viable_path_ids: Tuple[str, ...]
    failed_path_ids: Tuple[str, ...]
    unresolved_path_ids: Tuple[str, ...]
    context_mismatch_path_ids: Tuple[str, ...]
    candidate_count: int
    interpretation_ceiling: str = "condition_bounded_path_comparison_only"
    non_claims: Tuple[str, ...] = (
        "not_optimal_path_selection",
        "not_future_prediction",
        "not_causal_identification",
        "not_proof_of_classical_universal_law",
    )


def _nonempty(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _string_sequence(values: Tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field} must be a non-empty tuple")
    for value in values:
        _nonempty(value, field)


def _unique_strings(values: Tuple[str, ...], field: str) -> None:
    _string_sequence(values, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} entries must be unique")


def _axes(values: Tuple[Tuple[str, str], ...], field: str) -> dict[str, str]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be a tuple")
    result = {}
    for pair in values:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError(f"{field} entries must be (axis, value) pairs")
        axis, value = pair
        _nonempty(axis, f"{field}.axis")
        _nonempty(value, f"{field}.value")
        if axis in result:
            raise ValueError(f"{field} axis names must be unique")
        result[axis] = value
    return result


def audit_path_competition(
    candidates: Tuple[PathCandidate, ...],
    *,
    required_context_axes: Tuple[str, ...],
    target_context_axes: Tuple[Tuple[str, str], ...],
) -> PathCompetitionResult:
    """Compare at least two routes with identical endpoints under fixed axes.

    A route is viable/failed only when its supplied outcome and evidence pass
    structural checks and its required context axes match the target context.
    Unknown outcomes or context mismatches remain unresolved. No winner is
    selected; every route remains inspectable.
    """
    if not isinstance(candidates, tuple) or len(candidates) < 2:
        raise ValueError("at least two PathCandidate values are required")
    _unique_strings(required_context_axes, "required_context_axes")
    target_axes = _axes(target_context_axes, "target_context_axes")
    if set(required_context_axes) - set(target_axes):
        raise ValueError("target_context_axes must define every required axis")

    ids, endpoints, evidence_seen = [], set(), set()
    viable, failed, unresolved, mismatched = [], [], [], []
    reasons = []
    for candidate in candidates:
        if not isinstance(candidate, PathCandidate):
            raise ValueError("candidates must contain PathCandidate values")
        for field in ("path_id", "source_node", "target_node"):
            _nonempty(getattr(candidate, field), field)
        _string_sequence(candidate.ordered_states, "ordered_states")
        _string_sequence(candidate.relation_signatures, "relation_signatures")
        _unique_strings(candidate.evidence_refs, "evidence_refs")
        if candidate.ordered_states[0] != candidate.source_node or candidate.ordered_states[-1] != candidate.target_node:
            reasons.append(f"PATH_ENDPOINT_SEQUENCE_MISMATCH:{candidate.path_id}")
        if not isinstance(candidate.outcome, PathOutcome):
            raise ValueError("outcome must be a PathOutcome")
        axes = _axes(candidate.context_axes, "context_axes")
        ids.append(candidate.path_id)
        endpoints.add((candidate.source_node, candidate.target_node))
        overlap = evidence_seen.intersection(candidate.evidence_refs)
        if overlap:
            reasons.append("EVIDENCE_REUSED_ACROSS_COMPETING_PATHS")
        evidence_seen.update(candidate.evidence_refs)

        if set(required_context_axes) - set(axes):
            reasons.append(f"PATH_REQUIRED_CONTEXT_MISSING:{candidate.path_id}")
            unresolved.append(candidate.path_id)
            continue
        mismatch = any(axes[axis] != target_axes[axis] for axis in required_context_axes)
        if mismatch:
            mismatched.append(candidate.path_id)
            unresolved.append(candidate.path_id)
            continue

        if candidate.outcome is PathOutcome.VIABLE:
            viable.append(candidate.path_id)
        elif candidate.outcome is PathOutcome.FAILED:
            failed.append(candidate.path_id)
        else:
            unresolved.append(candidate.path_id)

    if len(ids) != len(set(ids)):
        reasons.append("PATH_IDS_MUST_BE_UNIQUE")
    if len(endpoints) != 1:
        reasons.append("COMPETING_PATHS_MUST_SHARE_ENDPOINTS")

    return PathCompetitionResult(
        decision=(PathCompetitionDecision.BLOCKED if reasons
                  else PathCompetitionDecision.HUMAN_REVIEW),
        reason_codes=tuple(sorted(set(reasons))),
        viable_path_ids=tuple(sorted(viable)),
        failed_path_ids=tuple(sorted(failed)),
        unresolved_path_ids=tuple(sorted(set(unresolved))),
        context_mismatch_path_ids=tuple(sorted(mismatched)),
        candidate_count=len(candidates),
    )
