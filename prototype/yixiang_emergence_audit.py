"""Auditable claim contract for emergent properties of composed yixiang views.

The audit checks explicit baselines, independent evidence references, scope,
alternatives, and falsification conditions. It never certifies emergence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class EmergenceDecision(str, Enum):
    BLOCKED = "blocked_incomplete_or_circular"
    HUMAN_REVIEW = "ready_for_human_review"


@dataclass(frozen=True)
class EmergenceClaim:
    claim_id: str
    composite_proposal_id: str
    emergent_property: str
    member_only_predictions: Tuple[str, ...]
    member_baseline_refs: Tuple[str, ...]
    bridge_evidence_refs: Tuple[str, ...]
    composite_level_evidence_refs: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    alternative_explanations: Tuple[str, ...]
    falsification_conditions: Tuple[str, ...]


@dataclass(frozen=True)
class EmergenceAudit:
    claim_id: str
    decision: EmergenceDecision
    reason_codes: Tuple[str, ...]
    claim_ceiling: str = "emergence_claim_structure_and_traceability_only"
    non_claims: Tuple[str, ...] = (
        "not_proof_of_ontological_emergence",
        "not_causal_validation",
        "not_universal_novelty",
        "not_independent_source_authentication",
    )


def _strings(values: Tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{field} must be a non-empty tuple")
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"{field} entries must be non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} entries must be unique")


def audit_emergence_claim(claim: EmergenceClaim) -> EmergenceAudit:
    """Audit a proposed emergence claim without deciding its truth."""
    if not isinstance(claim, EmergenceClaim):
        raise ValueError("claim must be EmergenceClaim")
    for field in ("claim_id", "composite_proposal_id", "emergent_property"):
        value = getattr(claim, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
    for field in (
        "member_only_predictions", "member_baseline_refs", "bridge_evidence_refs",
        "composite_level_evidence_refs", "scope_conditions",
        "alternative_explanations", "falsification_conditions",
    ):
        _strings(getattr(claim, field), field)

    reasons = []
    if claim.emergent_property in claim.member_only_predictions:
        reasons.append("PROPERTY_ALREADY_PRESENT_IN_MEMBER_ONLY_BASELINE")
    member_refs = set(claim.member_baseline_refs)
    bridge_refs = set(claim.bridge_evidence_refs)
    composite_refs = set(claim.composite_level_evidence_refs)
    if member_refs & bridge_refs:
        reasons.append("MEMBER_AND_BRIDGE_EVIDENCE_OVERLAP")
    if member_refs & composite_refs:
        reasons.append("MEMBER_AND_COMPOSITE_EVIDENCE_OVERLAP")
    if bridge_refs & composite_refs:
        reasons.append("BRIDGE_AND_COMPOSITE_EVIDENCE_OVERLAP")
    return EmergenceAudit(
        claim.claim_id,
        EmergenceDecision.BLOCKED if reasons else EmergenceDecision.HUMAN_REVIEW,
        tuple(reasons),
    )
