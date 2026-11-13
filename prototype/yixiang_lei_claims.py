"""Typed claim ledger for four non-interchangeable uses of classical 'lei'.

This is a conservative data-quality gate. It does not infer claims from texts,
prove causality, or convert a textual assertion into an empirical result.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class ClaimKind(str, Enum):
    TAXONOMIC_SIMILARITY = "taxonomic_similarity"
    ARGUMENTATIVE_ANALOGY = "argumentative_analogy"
    ACTION_OUTCOME = "action_outcome"
    PRACTICAL_UTILITY = "practical_utility"
    SYMBOLIC_CORRESPONDENCE = "symbolic_correspondence"
    CORRELATIVE_CAUSATION = "correlative_causation"


class EvidenceKind(str, Enum):
    CLASSICAL_TEXT = "classical_text"
    COMMENTARY = "commentary"
    MODERN_SCHOLARSHIP = "modern_scholarship"
    OBSERVATION = "observation"
    INTERVENTION = "intervention"
    MODEL_OUTPUT = "model_output"


class ClaimDecision(str, Enum):
    SCOPE_RECORDED = "scope_recorded"
    ABSTAIN = "abstain"
    REFUSE = "refuse"


@dataclass(frozen=True)
class LeiClaim:
    claim_id: str
    kind: ClaimKind
    subject: str
    predicate_or_target: str
    shared_basis: Tuple[str, ...]
    differences: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    evidence_kind: EvidenceKind
    # Action/outcome dimensions are deliberately separate.
    actor_intention: str = ""
    action_method: str = ""
    operating_conditions: Tuple[str, ...] = ()
    observed_outcomes: Tuple[str, ...] = ()
    delayed_outcomes: Tuple[str, ...] = ()
    utility_criteria: Tuple[str, ...] = ()
    causal_identification: str = "not_asserted"


@dataclass(frozen=True)
class LeiClaimAssessment:
    claim_id: str
    decision: ClaimDecision
    reason_codes: Tuple[str, ...]
    scope_only: bool = True
    causal_conclusion: str = "not_established"


def _validate(claim: LeiClaim) -> None:
    if not isinstance(claim.claim_id, str) or not claim.claim_id.strip():
        raise ValueError("claim_id is required")
    if not isinstance(claim.kind, ClaimKind):
        raise ValueError("kind must use ClaimKind")
    if not isinstance(claim.evidence_kind, EvidenceKind):
        raise ValueError("evidence_kind must use EvidenceKind")
    for name in ("subject", "predicate_or_target"):
        value = getattr(claim, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    tuple_fields = (
        "shared_basis", "differences", "scope_conditions", "evidence_refs",
        "operating_conditions", "observed_outcomes", "delayed_outcomes",
        "utility_criteria",
    )
    for name in tuple_fields:
        value = getattr(claim, name)
        if not isinstance(value, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError(f"{name} must be a tuple of non-empty strings")
    for name in ("actor_intention", "action_method", "causal_identification"):
        if not isinstance(getattr(claim, name), str):
            raise ValueError(f"{name} must be a string")


def assess_lei_claim(claim: LeiClaim) -> LeiClaimAssessment:
    """Check claim completeness without promoting evidence beyond its type."""
    _validate(claim)
    reasons = []
    if not claim.shared_basis:
        reasons.append("NO_EXPLICIT_BASIS")
    if not claim.scope_conditions:
        reasons.append("MISSING_SCOPE")
    if not claim.evidence_refs:
        reasons.append("MISSING_EVIDENCE_REFERENCE")
    if claim.evidence_kind == EvidenceKind.MODEL_OUTPUT:
        reasons.append("MODEL_OUTPUT_IS_NOT_INDEPENDENT_EVIDENCE")

    if claim.kind == ClaimKind.ACTION_OUTCOME:
        if claim.causal_identification not in ("not_asserted", "intervention_or_identification_evidence"):
            reasons.append("CAUSAL_IDENTIFICATION_UNRECOGNIZED")
        if (claim.causal_identification == "intervention_or_identification_evidence"
                and claim.evidence_kind != EvidenceKind.INTERVENTION):
            reasons.append("CAUSAL_EVIDENCE_KIND_MISMATCH")
        if not claim.actor_intention:
            reasons.append("INTENTION_NOT_RECORDED")
        if not claim.action_method:
            reasons.append("ACTION_METHOD_NOT_RECORDED")
        if not claim.operating_conditions:
            reasons.append("OPERATING_CONDITIONS_NOT_RECORDED")
        if not claim.observed_outcomes:
            reasons.append("OUTCOME_NOT_OBSERVED")
        if claim.causal_identification == "not_asserted":
            reasons.append("CAUSALITY_NOT_ESTABLISHED")

    if claim.kind == ClaimKind.CORRELATIVE_CAUSATION:
        if claim.causal_identification == "not_asserted":
            reasons.append("CORRELATIVE_CAUSALITY_NOT_EMPIRICALLY_IDENTIFIED")
        elif claim.causal_identification == "intervention_or_identification_evidence":
            if claim.evidence_kind != EvidenceKind.INTERVENTION:
                reasons.append("CAUSAL_EVIDENCE_KIND_MISMATCH")
        else:
            reasons.append("CAUSAL_IDENTIFICATION_UNRECOGNIZED")

    if claim.kind == ClaimKind.SYMBOLIC_CORRESPONDENCE and claim.causal_identification != "not_asserted":
        reasons.append("SYMBOLIC_CORRESPONDENCE_CANNOT_ESTABLISH_EMPIRICAL_CAUSALITY")

    if claim.kind == ClaimKind.PRACTICAL_UTILITY:
        if not claim.utility_criteria:
            reasons.append("UTILITY_CRITERIA_MISSING")
        if not claim.observed_outcomes:
            reasons.append("PRACTICAL_RESULT_NOT_OBSERVED")
        if not claim.delayed_outcomes:
            reasons.append("DELAYED_RESULT_NOT_RECORDED")

    hard_fail = {"NO_EXPLICIT_BASIS"}
    if hard_fail.intersection(reasons):
        decision = ClaimDecision.REFUSE
    elif reasons:
        decision = ClaimDecision.ABSTAIN
    else:
        decision = ClaimDecision.SCOPE_RECORDED

    # Even a complete record is only a scoped record. Empirical causality
    # requires a separate, reviewed identification protocol and is not inferred.
    causal = (
        "candidate_intervention_evidence_requires_review"
        if (claim.causal_identification == "intervention_or_identification_evidence"
            and claim.kind != ClaimKind.SYMBOLIC_CORRESPONDENCE)
        else "not_established"
    )
    return LeiClaimAssessment(
        claim_id=claim.claim_id,
        decision=decision,
        reason_codes=tuple(reasons),
        scope_only=True,
        causal_conclusion=causal,
    )
