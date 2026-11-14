"""Human-review workflow for auditable classical-text benchmark adjudication."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class ReviewStatus(str, Enum):
    SOURCE_UNVERIFIED = "source_unverified"
    INSUFFICIENT_REVIEWS = "insufficient_reviews"
    REVIEWER_CONFLICT = "reviewer_conflict"
    READY_FOR_ADJUDICATION = "ready_for_adjudication"
    ADJUDICATED = "adjudicated"

DECISIONS = {"accept", "reject", "conditional", "abstain"}
CAUSAL = {"symbolic", "normative", "co_occurrence", "correlational", "mechanistic_hypothesis", "intervention_supported", "unknown"}
SOURCE_STATUSES = {"verified_primary", "critical_edition", "unverified_transcription", "secondary_quotation", "research_hypothesis"}
SPLITS = {"train", "dev", "test", "holdout"}

@dataclass(frozen=True)
class SourceVerification:
    source_status: str
    work_id: str
    edition_id: str
    witness_id: str
    locator: str
    transcription: str
    verification_refs: Tuple[str, ...]
    verified_by: Tuple[str, ...]
    verification_note: str

@dataclass(frozen=True)
class IndependentAnnotation:
    reviewer_id: str
    decision: str
    claim: str
    text_layer: str
    shared_basis: Tuple[str, ...]
    non_shared_basis: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    required_invariants: Tuple[str, ...]
    known_counterexamples: Tuple[str, ...]
    causal_status: str
    evidence_refs: Tuple[str, ...]
    rationale: str

@dataclass(frozen=True)
class FinalAdjudication:
    decision: str
    adjudicator_id: str
    rationale: str
    evidence_refs: Tuple[str, ...]

@dataclass(frozen=True)
class ReviewPacket:
    case_id: str
    claim_kind: str
    independence_group: str
    source: SourceVerification
    annotations: Tuple[IndependentAnnotation, ...]
    adjudication: FinalAdjudication | None = None

@dataclass(frozen=True)
class ReviewAssessment:
    case_id: str
    status: ReviewStatus
    reviewer_ids: Tuple[str, ...]
    disagreement_fields: Tuple[str, ...]
    blockers: Tuple[str, ...]
    gold_eligible: bool = False

def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")

def _tuple(values, field, *, allow_empty=True):
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be a tuple")
    for value in values:
        _text(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    if not allow_empty and not values:
        raise ValueError(f"{field} must not be empty")

def _validate_source(source):
    if source.source_status not in SOURCE_STATUSES:
        raise ValueError("unknown source_status")
    for field in ("work_id", "edition_id", "witness_id", "locator", "transcription", "verification_note"):
        _text(getattr(source, field), field)
    _tuple(source.verification_refs, "verification_refs")
    _tuple(source.verified_by, "verified_by")
    if source.source_status in {"verified_primary", "critical_edition"}:
        if not source.verification_refs or not source.verified_by:
            raise ValueError("verified source requires verification_refs and verified_by")

def _validate_annotation(annotation):
    _text(annotation.reviewer_id, "reviewer_id")
    if annotation.decision not in DECISIONS:
        raise ValueError("unknown annotation decision")
    for field in ("claim", "text_layer", "rationale"):
        _text(getattr(annotation, field), field)
    for field in ("shared_basis", "non_shared_basis", "scope_conditions", "required_invariants", "known_counterexamples", "evidence_refs"):
        _tuple(getattr(annotation, field), field)
    if annotation.causal_status not in CAUSAL:
        raise ValueError("unknown causal_status")
    if annotation.decision == "accept" and not annotation.shared_basis:
        raise ValueError("accept requires explicit shared_basis")
    if annotation.decision == "conditional" and not annotation.scope_conditions:
        raise ValueError("conditional requires explicit scope_conditions")

def _validate_adjudication(adjudication, reviewers):
    if adjudication is None:
        return
    if adjudication.decision not in DECISIONS:
        raise ValueError("unknown final adjudication decision")
    _text(adjudication.adjudicator_id, "adjudicator_id")
    _text(adjudication.rationale, "adjudication rationale")
    _tuple(adjudication.evidence_refs, "adjudication evidence_refs", allow_empty=False)
    if adjudication.adjudicator_id in reviewers:
        raise ValueError("adjudicator must be distinct from independent reviewers")

def _disagreements(annotations):
    fields = ("decision", "claim", "text_layer", "shared_basis", "non_shared_basis", "scope_conditions", "required_invariants", "known_counterexamples", "causal_status")
    return tuple(field for field in fields if len({getattr(a, field) for a in annotations}) > 1)

def assess_review_packet(packet: ReviewPacket) -> ReviewAssessment:
    if not isinstance(packet, ReviewPacket):
        raise ValueError("packet must be ReviewPacket")
    for field in ("case_id", "claim_kind", "independence_group"):
        _text(getattr(packet, field), field)
    _validate_source(packet.source)
    if not isinstance(packet.annotations, tuple):
        raise ValueError("annotations must be tuple")
    for annotation in packet.annotations:
        _validate_annotation(annotation)
    reviewer_ids = tuple(a.reviewer_id for a in packet.annotations)
    if len(reviewer_ids) != len(set(reviewer_ids)):
        raise ValueError("reviewer IDs must be unique")
    _validate_adjudication(packet.adjudication, set(reviewer_ids))
    blockers = []
    if packet.source.source_status not in {"verified_primary", "critical_edition"}:
        blockers.append("source_not_verified")
    if len(reviewer_ids) < 2:
        blockers.append("fewer_than_two_independent_reviewers")
    if packet.source.verified_by and set(packet.source.verified_by) & set(reviewer_ids):
        blockers.append("source_verifier_overlaps_reviewer")
    if packet.source.source_status not in {"verified_primary", "critical_edition"}:
        status = ReviewStatus.SOURCE_UNVERIFIED
    elif len(reviewer_ids) < 2:
        status = ReviewStatus.INSUFFICIENT_REVIEWS
    elif packet.adjudication is None:
        status = ReviewStatus.REVIEWER_CONFLICT if _disagreements(packet.annotations) else ReviewStatus.READY_FOR_ADJUDICATION
    else:
        status = ReviewStatus.ADJUDICATED
    disagreements = _disagreements(packet.annotations)
    if packet.adjudication is not None and status == ReviewStatus.ADJUDICATED:
        if not packet.adjudication.rationale.strip():
            blockers.append("missing_adjudication_rationale")
    return ReviewAssessment(packet.case_id, status, reviewer_ids, disagreements, tuple(blockers),
                            status == ReviewStatus.ADJUDICATED and not blockers)

def to_benchmark_case(packet: ReviewPacket, *, split_group: str) -> dict:
    """Export only explicitly adjudicated, source-verified packets to M8."""
    assessment = assess_review_packet(packet)
    if not assessment.gold_eligible:
        raise ValueError(f"packet is not gold eligible: {assessment.status.value}; blockers={assessment.blockers}")
    if split_group not in SPLITS:
        raise ValueError("split_group must be train/dev/test/holdout; exploratory is not gold")
    final = packet.adjudication
    representative = packet.annotations[0]
    return {
        "claim_kind": packet.claim_kind, "case_id": packet.case_id,
        "source_lineage": [packet.source.work_id, packet.source.edition_id, packet.source.witness_id],
        "source_status": packet.source.source_status, "target_claim": representative.claim,
        "relation_families": ["structural"], "shared_basis": list(representative.shared_basis),
        "non_shared_basis": list(representative.non_shared_basis), "scope_conditions": list(representative.scope_conditions),
        "required_invariants": list(representative.required_invariants),
        "known_counterexamples": list(representative.known_counterexamples),
        "causal_status": representative.causal_status,
        "evidence_refs": sorted(set(packet.source.verification_refs) | set(final.evidence_refs) | {r for a in packet.annotations for r in a.evidence_refs}),
        "independence_group": packet.independence_group, "gold_decision": final.decision,
        "gold_rationale": final.rationale, "label_status": "adjudicated",
        "reviewers": sorted(assessment.reviewer_ids), "split_group": split_group,
    }