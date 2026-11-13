"""M9 multi-view yixiang proposals and provenance-safe composition.

This module records morphology/structure/function/mechanism/time/context views
without collapsing them into a single similarity score. Composition is only
proposed when an explicit bridge is supplied; it is never inferred silently.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Tuple


class XiangAxis(str, Enum):
    MORPHOLOGICAL = "morphological"
    STRUCTURAL = "structural"
    FUNCTIONAL = "functional"
    MECHANISM = "process_mechanism"
    TEMPORAL = "temporal"
    SITUATED = "situated"
    SYMBOLIC_NORMATIVE = "symbolic_normative"


class EvidenceKind(str, Enum):
    DIRECT_OBSERVATION = "direct_observation"
    PRIMARY_TEXT = "primary_text"
    CRITICAL_EDITION = "critical_edition"
    REPORTED_OBSERVATION = "reported_observation"
    COMMENTARY = "commentary"
    MODEL_INFERENCE = "model_inference"


class ProposalStatus(str, Enum):
    HUMAN_REVIEW = "human_review"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AxisEvidence:
    axis: XiangAxis
    source_value: str
    target_value: str
    correspondence: str
    source_ref: str
    target_ref: str
    source_kind: EvidenceKind
    target_kind: EvidenceKind


@dataclass(frozen=True)
class ViewCandidate:
    candidate_id: str
    source_observation_id: str
    target_observation_id: str
    axis: XiangAxis
    evidence: AxisEvidence
    scope_conditions: Tuple[str, ...]
    known_differences: Tuple[str, ...]
    status: ProposalStatus = ProposalStatus.HUMAN_REVIEW
    claim_ceiling: str = "axis_specific_correspondence_only"


@dataclass(frozen=True)
class CompositionBridge:
    bridge_id: str
    member_candidate_ids: Tuple[str, ...]
    relation: str
    scope_conditions: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    rationale: str



@dataclass(frozen=True)
class ContextAssessment:
    subject_id: str
    status: ProposalStatus
    missing_conditions: Tuple[str, ...]
    reason_codes: Tuple[str, ...]


@dataclass(frozen=True)
class CompositeProposal:
    proposal_id: str
    member_candidate_ids: Tuple[str, ...]
    axes: Tuple[XiangAxis, ...]
    bridge: CompositionBridge
    status: ProposalStatus = ProposalStatus.HUMAN_REVIEW
    claim_ceiling: str = "composed_hypothesis_for_human_review_only"
    non_claims: Tuple[str, ...] = (
        "not_proof_of_shared_mechanism",
        "not_causal_validation",
        "not_universal_generalization",
        "not_automatic_class_membership",
    )


def _required(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def validate_view(candidate: ViewCandidate) -> None:
    if not isinstance(candidate, ViewCandidate):
        raise ValueError("candidate must be ViewCandidate")
    for field in ("candidate_id", "source_observation_id", "target_observation_id"):
        _required(getattr(candidate, field), field)
    if candidate.source_observation_id == candidate.target_observation_id:
        raise ValueError("source and target observations must differ")
    if not isinstance(candidate.axis, XiangAxis) or not isinstance(candidate.status, ProposalStatus):
        raise ValueError("axis and status must use declared enums")
    if not isinstance(candidate.evidence, AxisEvidence):
        raise ValueError("evidence must be AxisEvidence")
    e = candidate.evidence
    if e.axis != candidate.axis:
        raise ValueError("evidence axis must match candidate axis")
    for field in ("source_value", "target_value", "correspondence", "source_ref", "target_ref"):
        _required(getattr(e, field), f"evidence.{field}")
    if not isinstance(e.source_kind, EvidenceKind) or not isinstance(e.target_kind, EvidenceKind):
        raise ValueError("evidence kinds must use EvidenceKind")
    for field in ("scope_conditions", "known_differences"):
        values = getattr(candidate, field)
        if not isinstance(values, tuple) or not values:
            raise ValueError(f"{field} must be a non-empty tuple")
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f"{field} entries must be non-empty strings")
        if len(set(values)) != len(values):
            raise ValueError(f"{field} entries must be unique")


def group_competing_views(candidates: Tuple[ViewCandidate, ...]) -> Tuple[Tuple[str, ...], ...]:
    """Return competing candidate-ID groups for the same ordered observation pair.

    Candidates are not ranked. Different axes remain distinct explanations.
    """
    if not isinstance(candidates, tuple):
        raise ValueError("candidates must be a tuple")
    seen = set()
    groups = {}
    for candidate in candidates:
        validate_view(candidate)
        if candidate.candidate_id in seen:
            raise ValueError("candidate ids must be unique")
        seen.add(candidate.candidate_id)
        key = (candidate.source_observation_id, candidate.target_observation_id)
        groups.setdefault(key, []).append(candidate.candidate_id)
    return tuple(
        tuple(sorted(ids)) for _, ids in sorted(groups.items()) if len(ids) > 1
    )


def compose_views(
    candidates: Tuple[ViewCandidate, ...],
    bridge: CompositionBridge,
) -> CompositeProposal:
    """Propose a composition only from explicit members and an evidenced bridge."""
    if not isinstance(candidates, tuple) or len(candidates) < 2:
        raise ValueError("at least two view candidates are required")
    for candidate in candidates:
        validate_view(candidate)
    ids = [candidate.candidate_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate ids must be unique")
    if not isinstance(bridge, CompositionBridge):
        raise ValueError("bridge must be CompositionBridge")
    for field in ("bridge_id", "relation", "rationale"):
        _required(getattr(bridge, field), field)
    if not isinstance(bridge.member_candidate_ids, tuple) or set(bridge.member_candidate_ids) != set(ids):
        raise ValueError("bridge members must exactly match supplied candidates")
    if len(bridge.member_candidate_ids) != len(set(bridge.member_candidate_ids)):
        raise ValueError("bridge member ids must be unique")
    if not isinstance(bridge.scope_conditions, tuple) or not bridge.scope_conditions:
        raise ValueError("bridge scope_conditions must be non-empty")
    if any(not isinstance(x, str) or not x.strip() for x in bridge.scope_conditions):
        raise ValueError("bridge scope conditions must be non-empty strings")
    if not isinstance(bridge.evidence_refs, tuple) or not bridge.evidence_refs:
        raise ValueError("bridge evidence_refs must be non-empty")
    if any(not isinstance(x, str) or not x.strip() for x in bridge.evidence_refs):
        raise ValueError("bridge evidence refs must be non-empty strings")
    if len(set(bridge.evidence_refs)) != len(bridge.evidence_refs):
        raise ValueError("bridge evidence refs must be unique")
    member_refs = {
        ref for candidate in candidates
        for ref in (candidate.evidence.source_ref, candidate.evidence.target_ref)
    }
    if member_refs.intersection(bridge.evidence_refs):
        raise ValueError("bridge evidence must be distinct from member-view evidence")

    pairs = {(c.source_observation_id, c.target_observation_id) for c in candidates}
    if len(pairs) != 1:
        raise ValueError("all views must concern the same ordered observation pair")
    axes = tuple(sorted({c.axis for c in candidates}, key=lambda axis: axis.value))
    if len(axes) != len(candidates):
        raise ValueError("composition requires distinct axes; duplicate-axis evidence must be reconciled first")
    common_scope = set(candidates[0].scope_conditions)
    for candidate in candidates[1:]:
        common_scope.intersection_update(candidate.scope_conditions)
    if not common_scope.intersection(bridge.scope_conditions):
        raise ValueError("bridge scope must overlap every member's declared scope")
    if not bridge.evidence_refs:
        raise ValueError("composition bridge requires evidence")
    return CompositeProposal(
        proposal_id="ycx:" + "+".join(sorted(ids)),
        member_candidate_ids=tuple(sorted(ids)),
        axes=axes,
        bridge=bridge,
    )


def _validate_active_conditions(active_conditions: Tuple[str, ...]) -> None:
    if not isinstance(active_conditions, tuple) or any(
        not isinstance(x, str) or not x.strip() for x in active_conditions
    ):
        raise ValueError("active_conditions must be a tuple of non-empty strings")
    if len(set(active_conditions)) != len(active_conditions):
        raise ValueError("active_conditions must be unique")


def revalidate_view(
    candidate: ViewCandidate,
    active_conditions: Tuple[str, ...],
) -> ContextAssessment:
    """Re-evaluate scope against a newly observed context; never infer missing facts."""
    validate_view(candidate)
    _validate_active_conditions(active_conditions)
    missing = tuple(sorted(set(candidate.scope_conditions) - set(active_conditions)))
    return ContextAssessment(
        candidate.candidate_id,
        ProposalStatus.BLOCKED if missing else ProposalStatus.HUMAN_REVIEW,
        missing,
        ("SCOPE_CONDITION_NOT_ACTIVE",) if missing else (),
    )


def revalidate_composite(
    proposal: CompositeProposal,
    candidates: Tuple[ViewCandidate, ...],
    active_conditions: Tuple[str, ...],
) -> ContextAssessment:
    """Invalidate a composite when any member or its bridge leaves the active scope."""
    if not isinstance(proposal, CompositeProposal):
        raise ValueError("proposal must be CompositeProposal")
    if not isinstance(candidates, tuple):
        raise ValueError("candidates must be a tuple")
    _validate_active_conditions(active_conditions)
    by_id = {}
    for candidate in candidates:
        validate_view(candidate)
        if candidate.candidate_id in by_id:
            raise ValueError("candidate ids must be unique")
        by_id[candidate.candidate_id] = candidate
    missing_members = tuple(sorted(set(proposal.member_candidate_ids) - set(by_id)))
    if missing_members:
        return ContextAssessment(
            proposal.proposal_id, ProposalStatus.BLOCKED, missing_members,
            ("COMPOSITE_MEMBER_MISSING",),
        )
    missing = set(proposal.bridge.scope_conditions) - set(active_conditions)
    for candidate_id in proposal.member_candidate_ids:
        missing.update(set(by_id[candidate_id].scope_conditions) - set(active_conditions))
    missing_conditions = tuple(sorted(missing))
    return ContextAssessment(
        proposal.proposal_id,
        ProposalStatus.BLOCKED if missing_conditions else ProposalStatus.HUMAN_REVIEW,
        missing_conditions,
        ("COMPOSITE_SCOPE_INVALIDATED",) if missing_conditions else (),
    )
