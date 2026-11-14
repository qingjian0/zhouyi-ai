"""Four-layer firewall for classical yixiang interpretation and transfer."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class Resolution(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"

class EvidenceLayer(str, Enum):
    PRIMARY_TEXT = "primary_text"
    COMMENTARY = "commentary"
    MODERN_SCHOLARSHIP = "modern_scholarship"
    OBSERVATION = "observation"
    MODEL_OUTPUT = "model_output"

class PredicateKind(str, Enum):
    TAXONOMIC = "taxonomic"
    ATTRIBUTE = "attribute"
    FUNCTIONAL = "functional"
    STRUCTURAL = "structural"
    CAUSAL = "causal"
    SYMBOLIC = "symbolic"
    NORMATIVE = "normative"
    RHETORICAL = "rhetorical"

class Decision(str, Enum):
    SCOPE_RECORDED = "scope_recorded"
    ABSTAIN = "abstain"
    REFUSE = "refuse"

@dataclass(frozen=True)
class YixiangInterpretationClaim:
    claim_id: str
    lexeme_resolution: Resolution
    referent_resolution: Resolution
    category_resolution: Resolution
    predicate_kind: PredicateKind
    source_text_ref: str
    interpretation_ref: str
    evidence_layer: EvidenceLayer
    contextual_conditions: Tuple[str, ...]
    competing_readings: Tuple[str, ...] = ()
    independent_witness_refs: Tuple[str, ...] = ()
    model_output_used_as_evidence: bool = False
    causal_status: str = "not_asserted"

@dataclass(frozen=True)
class Assessment:
    claim_id: str
    decision: Decision
    reason_codes: Tuple[str, ...]
    interpretation_scope_only: bool = True
    empirical_causality_established: bool = False

def _validate(claim: YixiangInterpretationClaim) -> None:
    if not isinstance(claim.claim_id, str) or not claim.claim_id.strip():
        raise ValueError("claim_id is required")
    for name, expected in (
        ("lexeme_resolution", Resolution), ("referent_resolution", Resolution),
        ("category_resolution", Resolution), ("predicate_kind", PredicateKind),
        ("evidence_layer", EvidenceLayer),
    ):
        if not isinstance(getattr(claim, name), expected):
            raise ValueError(f"{name} must use {expected.__name__}")
    for name in ("source_text_ref", "interpretation_ref"):
        value = getattr(claim, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    for name in ("contextual_conditions", "competing_readings", "independent_witness_refs"):
        value = getattr(claim, name)
        if not isinstance(value, tuple) or any(not isinstance(x, str) or not x.strip() for x in value):
            raise ValueError(f"{name} must be a tuple of non-empty strings")
    if not isinstance(claim.model_output_used_as_evidence, bool):
        raise ValueError("model_output_used_as_evidence must be bool")
    if not isinstance(claim.causal_status, str):
        raise ValueError("causal_status must be a string")

def assess_interpretation(claim: YixiangInterpretationClaim) -> Assessment:
    """Apply staged evidence gates without collapsing uncertainty to false."""
    _validate(claim)
    reasons = []
    if claim.lexeme_resolution != Resolution.RESOLVED:
        reasons.append("LEXEME_NOT_RESOLVED")
    if claim.referent_resolution != Resolution.RESOLVED:
        reasons.append("REFERENT_NOT_RESOLVED")
    if claim.category_resolution != Resolution.RESOLVED:
        reasons.append("CATEGORY_NOT_RESOLVED")
    if not claim.contextual_conditions:
        reasons.append("TEXTUAL_CONTEXT_NOT_RECORDED")
    if claim.competing_readings:
        reasons.append("COMPETING_READING_REQUIRES_ADJUDICATION")
    if claim.evidence_layer == EvidenceLayer.MODEL_OUTPUT or claim.model_output_used_as_evidence:
        reasons.append("MODEL_OUTPUT_CANNOT_AUTHENTICATE_INTERPRETATION")
    if claim.evidence_layer in (EvidenceLayer.COMMENTARY, EvidenceLayer.MODERN_SCHOLARSHIP):
        reasons.append("INTERPRETIVE_SOURCE_MUST_REMAIN_LAYERED")
    if claim.predicate_kind == PredicateKind.CAUSAL and claim.causal_status != "not_asserted":
        reasons.append("TEXTUAL_CAUSAL_CLAIM_REQUIRES_SEPARATE_EMPIRICAL_IDENTIFICATION")
    if len(set(claim.independent_witness_refs)) != len(claim.independent_witness_refs):
        reasons.append("DUPLICATE_WITNESS_REFERENCE")
    hard_refuse = claim.lexeme_resolution == Resolution.AMBIGUOUS and claim.referent_resolution == Resolution.RESOLVED
    decision = Decision.REFUSE if hard_refuse else (Decision.ABSTAIN if reasons else Decision.SCOPE_RECORDED)
    return Assessment(claim.claim_id, decision, tuple(reasons), True, False)
