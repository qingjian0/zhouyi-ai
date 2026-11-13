"""Audit the structure of classical inference moves without certifying truth."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class InferenceMove(str, Enum):
    EXEMPLIFICATION = "pi"
    PARALLEL_FORM = "mou"
    PRECEDENT_APPEAL = "yuan"
    CLASS_EXTENSION = "tui"
    STANDARD_COMPARISON = "xiao"


class AuditDecision(str, Enum):
    BLOCKED = "blocked_incomplete_or_untraceable"
    HUMAN_REVIEW = "ready_for_human_review"


class AnchorRole(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    PRECEDENT = "precedent"
    STANDARD = "standard"


@dataclass(frozen=True)
class EvidenceAnchor:
    role: AnchorRole
    evidence_ref: str
    description: str


@dataclass(frozen=True)
class InferenceMoveClaim:
    claim_id: str
    move: InferenceMove
    source_observation_id: str
    target_observation_id: str
    shared_basis: Tuple[str, ...]
    warrant: str
    conclusion: str
    scope_conditions: Tuple[str, ...]
    known_differences: Tuple[str, ...]
    anchors: Tuple[EvidenceAnchor, ...]


@dataclass(frozen=True)
class InferenceMoveAudit:
    claim_id: str
    decision: AuditDecision
    reason_codes: Tuple[str, ...]
    required_roles: Tuple[AnchorRole, ...]
    present_roles: Tuple[AnchorRole, ...]
    claim_ceiling: str = "argument_form_and_traceability_only"
    explicit_non_claims: Tuple[str, ...] = (
        "not_truth_certified", "not_causal_validation",
        "not_universal_generalization", "not_proof_of_class_membership",
    )


_REQUIRED_ROLES = {
    InferenceMove.EXEMPLIFICATION: (AnchorRole.SOURCE, AnchorRole.TARGET),
    InferenceMove.PARALLEL_FORM: (AnchorRole.SOURCE, AnchorRole.TARGET),
    InferenceMove.PRECEDENT_APPEAL: (AnchorRole.PRECEDENT, AnchorRole.TARGET),
    InferenceMove.CLASS_EXTENSION: (AnchorRole.SOURCE, AnchorRole.TARGET),
    InferenceMove.STANDARD_COMPARISON: (AnchorRole.STANDARD, AnchorRole.TARGET),
}


def audit_inference_move(claim: InferenceMoveClaim) -> InferenceMoveAudit:
    """Check argument completeness and traceability, never semantic truth."""
    if not isinstance(claim, InferenceMoveClaim):
        raise ValueError("claim must be InferenceMoveClaim")
    for field in ("claim_id", "source_observation_id", "target_observation_id", "warrant", "conclusion"):
        value = getattr(claim, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be non-empty")
    if claim.source_observation_id == claim.target_observation_id:
        raise ValueError("source and target observations must differ")
    if not isinstance(claim.move, InferenceMove):
        raise ValueError("move must use InferenceMove")
    for field in ("shared_basis", "scope_conditions", "known_differences", "anchors"):
        if not isinstance(getattr(claim, field), tuple):
            raise ValueError(f"{field} must be a tuple")
    for field in ("shared_basis", "scope_conditions", "known_differences"):
        if any(not isinstance(v, str) or not v.strip() for v in getattr(claim, field)):
            raise ValueError(f"{field} entries must be non-empty strings")
    if any(not isinstance(a, EvidenceAnchor) for a in claim.anchors):
        raise ValueError("anchors must contain EvidenceAnchor")
    for anchor in claim.anchors:
        if not isinstance(anchor.role, AnchorRole):
            raise ValueError("anchor role must use AnchorRole")
        if not isinstance(anchor.evidence_ref, str) or not anchor.evidence_ref.strip():
            raise ValueError("anchor evidence_ref must be non-empty")
        if not isinstance(anchor.description, str) or not anchor.description.strip():
            raise ValueError("anchor description must be non-empty")
    required = _REQUIRED_ROLES[claim.move]
    present = tuple(sorted({a.role for a in claim.anchors}, key=lambda x: x.value))
    reasons = []
    if not claim.shared_basis:
        reasons.append("MISSING_EXPLICIT_SHARED_BASIS")
    if not claim.scope_conditions:
        reasons.append("MISSING_SCOPE_CONDITIONS")
    if not claim.known_differences:
        reasons.append("MISSING_KNOWN_DIFFERENCES")
    refs = [a.evidence_ref for a in claim.anchors]
    if len(refs) != len(set(refs)):
        reasons.append("DUPLICATE_EVIDENCE_ANCHOR")
    if set(required) - set(present):
        reasons.append("MISSING_MOVE_SPECIFIC_EVIDENCE_ROLE")
    decision = AuditDecision.BLOCKED if reasons else AuditDecision.HUMAN_REVIEW
    return InferenceMoveAudit(claim.claim_id, decision, tuple(reasons), required, present)
