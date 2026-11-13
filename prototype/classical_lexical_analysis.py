"""Evidence-first lexical and referent analysis for classical Chinese corpus.

The module validates explicit annotations; it does not perform automatic
historical lexicography, etymology, or object identification.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class LexicalRelation(str, Enum):
    SAME_FORM_DIFFERENT_SENSE = "same_form_different_sense"
    DIFFERENT_FORM_SAME_REFERENT = "different_form_same_referent"
    SAME_FORM_SAME_SENSE = "same_form_same_sense"
    UNRESOLVED = "unresolved"


class EvidenceStatus(str, Enum):
    VERIFIED_PRIMARY_WITNESS = "verified_primary_witness"
    EDITION_TRANSCRIPTION = "edition_transcription"
    SECONDARY_QUOTATION = "secondary_quotation"
    MODERN_INTERPRETATION = "modern_interpretation"
    MODEL_PROPOSAL = "model_proposal"
    UNKNOWN = "unknown"


class LexicalDecision(str, Enum):
    ACCEPT_AS_SCOPED = "accept_as_scoped"
    ABSTAIN = "abstain"
    REJECT = "reject"


@dataclass(frozen=True)
class LexicalOccurrence:
    occurrence_id: str
    surface_form: str
    work_id: str
    passage_ref: str
    sense_id: str
    referent_id: str
    period: str
    evidence_status: EvidenceStatus
    context: str


@dataclass(frozen=True)
class LexicalComparison:
    comparison_id: str
    left: LexicalOccurrence
    right: LexicalOccurrence
    proposed_relation: LexicalRelation
    left_witness_refs: Tuple[str, ...] = ()
    right_witness_refs: Tuple[str, ...] = ()
    distinction_notes: Tuple[str, ...] = ()
    scope_conditions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class LexicalAssessment:
    comparison_id: str
    decision: LexicalDecision
    reason_codes: Tuple[str, ...]


def assess_lexical_comparison(item: LexicalComparison) -> LexicalAssessment:
    if not item.comparison_id.strip():
        raise ValueError("comparison_id is required")
    if not isinstance(item.proposed_relation, LexicalRelation):
        raise ValueError("proposed_relation must use LexicalRelation")
    for name, values in (
        ("left_witness_refs", item.left_witness_refs),
        ("right_witness_refs", item.right_witness_refs),
        ("distinction_notes", item.distinction_notes),
        ("scope_conditions", item.scope_conditions),
    ):
        if not isinstance(values, tuple) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f"{name} must be a tuple of non-empty strings")
    for occurrence in (item.left, item.right):
        for name in ("occurrence_id", "surface_form", "work_id", "passage_ref",
                     "sense_id", "referent_id", "period", "context"):
            value = getattr(occurrence, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required on each occurrence")
        if not isinstance(occurrence.evidence_status, EvidenceStatus):
            raise ValueError("evidence_status must use EvidenceStatus")

    left, right = item.left, item.right
    reasons = []
    if left.evidence_status != EvidenceStatus.VERIFIED_PRIMARY_WITNESS or right.evidence_status != EvidenceStatus.VERIFIED_PRIMARY_WITNESS:
        reasons.append("PRIMARY_WITNESS_VERIFICATION_REQUIRED")
    if not item.left_witness_refs or not item.right_witness_refs:
        reasons.append("MISSING_SIDE_SPECIFIC_WITNESS_REFERENCES")
    if not item.scope_conditions:
        reasons.append("MISSING_SCOPE_CONDITIONS")

    relation = item.proposed_relation
    if relation == LexicalRelation.SAME_FORM_DIFFERENT_SENSE:
        if left.surface_form != right.surface_form or left.sense_id == right.sense_id:
            return LexicalAssessment(item.comparison_id, LexicalDecision.REJECT, ("RELATION_CONTRADICTS_ANNOTATED_FIELDS",))
        if not item.distinction_notes:
            reasons.append("MISSING_SENSE_DISTINCTION")
    elif relation == LexicalRelation.DIFFERENT_FORM_SAME_REFERENT:
        if left.surface_form == right.surface_form or left.referent_id != right.referent_id:
            return LexicalAssessment(item.comparison_id, LexicalDecision.REJECT, ("RELATION_CONTRADICTS_ANNOTATED_FIELDS",))
        if not item.distinction_notes:
            reasons.append("MISSING_REFERENT_IDENTIFICATION_BASIS")
    elif relation == LexicalRelation.SAME_FORM_SAME_SENSE:
        if left.surface_form != right.surface_form or left.sense_id != right.sense_id:
            return LexicalAssessment(item.comparison_id, LexicalDecision.REJECT, ("RELATION_CONTRADICTS_ANNOTATED_FIELDS",))
    elif relation == LexicalRelation.UNRESOLVED:
        reasons.append("ANNOTATED_AS_UNRESOLVED")

    if reasons:
        return LexicalAssessment(item.comparison_id, LexicalDecision.ABSTAIN, tuple(reasons))
    return LexicalAssessment(item.comparison_id, LexicalDecision.ACCEPT_AS_SCOPED, ())
