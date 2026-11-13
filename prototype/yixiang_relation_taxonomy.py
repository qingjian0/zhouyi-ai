"""Conservative typed relation-transfer gate for classical yixiang research.

This module checks declared correspondence structure only. It does not infer
relations from text, authenticate sources, or establish empirical causality.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class RelationFamily(str, Enum):
    CLASSIFICATION = "classification"
    ATTRIBUTE = "attribute"
    FUNCTION = "function"
    STRUCTURAL = "structural"
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    GENERATIVE = "generative"
    CAUSAL = "causal"
    CORRESPONDENCE = "correspondence"
    SYMBOLIC = "symbolic"
    NORMATIVE = "normative"
    RHETORICAL = "rhetorical"
    LEXICAL = "lexical"


class EvidenceLayer(str, Enum):
    CLASSICAL_TEXT = "classical_text"
    COMMENTARY = "commentary"
    BIBLIOGRAPHIC = "bibliographic_record"
    MODERN_SCHOLARSHIP = "modern_scholarship"
    OBSERVATION = "field_observation"
    EXPERIMENT = "experiment"
    PROJECT_HYPOTHESIS = "research_hypothesis"
    MODEL_GENERATED = "model_generated"


class CausalStatus(str, Enum):
    NOT_ASSERTED = "not_asserted"
    TEXTUAL_ASSERTION = "textual_assertion"
    OBSERVED_ASSOCIATION = "observed_association"
    INTERVENTION_SUPPORTED = "intervention_supported"
    CHALLENGED = "challenged"
    UNKNOWN = "unknown"


class TransferDecision(str, Enum):
    SCOPE_SUPPORTED = "scope_supported"
    ABSTAIN = "abstain"
    REFUSE = "refuse"


@dataclass(frozen=True)
class RelationMapping:
    mapping_id: str
    source_family: RelationFamily
    target_family: RelationFamily
    shared_basis: Tuple[str, ...]
    non_shared_basis: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    source_evidence_refs: Tuple[str, ...]
    target_evidence_refs: Tuple[str, ...]
    source_layer: EvidenceLayer
    target_layer: EvidenceLayer
    causal_status: CausalStatus = CausalStatus.UNKNOWN
    known_counterexamples: Tuple[str, ...] = ()


@dataclass(frozen=True)
class TransferAssessment:
    mapping_id: str
    decision: TransferDecision
    reason_codes: Tuple[str, ...]
    scope_only: bool = True


def assess_relation_mapping(mapping: RelationMapping) -> TransferAssessment:
    """Assess declared mapping hygiene; never claim truth or causal validity."""
    if not isinstance(mapping.mapping_id, str) or not mapping.mapping_id.strip():
        raise ValueError("mapping_id is required")
    for field_name in ("shared_basis", "non_shared_basis", "scope_conditions",
                       "source_evidence_refs", "target_evidence_refs",
                       "known_counterexamples"):
        value = getattr(mapping, field_name)
        if not isinstance(value, tuple) or any(not isinstance(x, str) or not x.strip() for x in value):
            raise ValueError(f"{field_name} must be a tuple of non-empty strings")
    if not isinstance(mapping.source_family, RelationFamily) or not isinstance(mapping.target_family, RelationFamily):
        raise ValueError("relation families must use RelationFamily")
    if not isinstance(mapping.source_layer, EvidenceLayer) or not isinstance(mapping.target_layer, EvidenceLayer):
        raise ValueError("evidence layers must use EvidenceLayer")
    if not isinstance(mapping.causal_status, CausalStatus):
        raise ValueError("causal_status must use CausalStatus")

    reasons = []
    if mapping.source_family != mapping.target_family:
        reasons.append("RELATION_FAMILY_MISMATCH")
    if not mapping.shared_basis:
        reasons.append("NO_DECLARED_SHARED_BASIS")
    if not mapping.scope_conditions:
        reasons.append("MISSING_SCOPE_CONDITIONS")
    if not mapping.source_evidence_refs or not mapping.target_evidence_refs:
        reasons.append("MISSING_SIDE_SPECIFIC_EVIDENCE")
    if mapping.known_counterexamples:
        reasons.append("KNOWN_COUNTEREXAMPLE_REQUIRES_REVIEW")
    if mapping.causal_status in (CausalStatus.UNKNOWN, CausalStatus.CHALLENGED):
        reasons.append("CAUSAL_STATUS_UNRESOLVED")
    if mapping.source_layer == EvidenceLayer.MODEL_GENERATED or mapping.target_layer == EvidenceLayer.MODEL_GENERATED:
        reasons.append("MODEL_OUTPUT_CANNOT_AUTHENTICATE_MAPPING")

    hard_fail = {"RELATION_FAMILY_MISMATCH", "NO_DECLARED_SHARED_BASIS"}
    if hard_fail.intersection(reasons):
        decision = TransferDecision.REFUSE
    elif reasons:
        decision = TransferDecision.ABSTAIN
    else:
        decision = TransferDecision.SCOPE_SUPPORTED
    return TransferAssessment(mapping.mapping_id, decision, tuple(reasons), scope_only=True)
