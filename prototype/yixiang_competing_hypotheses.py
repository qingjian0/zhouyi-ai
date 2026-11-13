"""M3 competing yixiang profiles with evidence-aware abstention.

This is an auditable rule-based baseline. It deliberately avoids collapsing
heterogeneous evidence into one probability or forcing a single winner.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceStance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class EvidenceLayer(str, Enum):
    PRIMARY_TEXT = "primary_text"
    OBSERVATION = "observation"
    COMMENTARY = "commentary"
    MODERN_RESEARCH = "modern_research"
    MODEL_INFERENCE = "model_inference"


class CandidateStatus(str, Enum):
    VIABLE = "viable"
    CONTESTED = "contested"
    REJECTED = "rejected"
    UNDERDETERMINED = "underdetermined"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    dimension: str
    stance: EvidenceStance
    strength: float
    layer: EvidenceLayer
    source_ref: str
    note: str = ""

    def validate(self) -> None:
        if not self.evidence_id.strip() or not self.dimension.strip():
            raise ValueError("evidence id and dimension are required")
        if not 0.0 < self.strength <= 1.0:
            raise ValueError("evidence strength must be in (0, 1]")
        if not self.source_ref.strip():
            raise ValueError("evidence source_ref is required")


@dataclass(frozen=True)
class XiangCandidate:
    candidate_id: str
    mapping_claim: str
    applicable_conditions: tuple[str, ...]
    required_conditions: tuple[str, ...]
    satisfied_conditions: tuple[str, ...]
    violated_conditions: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]

    def validate(self) -> None:
        if not self.candidate_id.strip() or not self.mapping_claim.strip():
            raise ValueError("candidate id and mapping claim are required")
        if len(set(self.required_conditions)) != len(self.required_conditions):
            raise ValueError("required conditions must be unique")
        if not set(self.satisfied_conditions).issubset(self.required_conditions):
            raise ValueError("satisfied conditions must be declared required conditions")
        if not set(self.violated_conditions).issubset(self.required_conditions):
            raise ValueError("violated conditions must be declared required conditions")
        if set(self.satisfied_conditions) & set(self.violated_conditions):
            raise ValueError("a condition cannot be both satisfied and violated")
        ids: set[str] = set()
        for item in self.evidence:
            item.validate()
            if item.evidence_id in ids:
                raise ValueError("evidence ids must be unique within a candidate")
            ids.add(item.evidence_id)


@dataclass(frozen=True)
class EvidenceProfile:
    by_dimension: tuple[tuple[str, float, float, float], ...]
    primary_support_count: int
    observation_support_count: int
    commentary_support_count: int
    modern_research_support_count: int
    model_inference_support_count: int
    supporting_records: tuple[EvidenceRecord, ...]
    contradicting_records: tuple[EvidenceRecord, ...]
    neutral_records: tuple[EvidenceRecord, ...]


@dataclass(frozen=True)
class CandidateAssessment:
    candidate_id: str
    status: CandidateStatus
    profile: EvidenceProfile
    missing_conditions: tuple[str, ...]
    violated_conditions: tuple[str, ...]


@dataclass(frozen=True)
class ArbitrationResult:
    assessments: tuple[CandidateAssessment, ...]
    viable_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    unresolved: bool


def assess_candidate(candidate: XiangCandidate) -> CandidateAssessment:
    candidate.validate()
    supports = tuple(e for e in candidate.evidence if e.stance == EvidenceStance.SUPPORTS)
    contradicts = tuple(e for e in candidate.evidence if e.stance == EvidenceStance.CONTRADICTS)
    neutral = tuple(e for e in candidate.evidence if e.stance == EvidenceStance.NEUTRAL)
    dimensions = sorted({e.dimension for e in candidate.evidence})
    profile_rows = []
    for dimension in dimensions:
        group = [e for e in candidate.evidence if e.dimension == dimension]
        profile_rows.append((
            dimension,
            sum(e.strength for e in group if e.stance == EvidenceStance.SUPPORTS),
            sum(e.strength for e in group if e.stance == EvidenceStance.CONTRADICTS),
            sum(e.strength for e in group if e.stance == EvidenceStance.NEUTRAL),
        ))

    counts = {
        layer: sum(1 for e in supports if e.layer == layer)
        for layer in EvidenceLayer
    }
    profile = EvidenceProfile(
        tuple(profile_rows),
        counts[EvidenceLayer.PRIMARY_TEXT],
        counts[EvidenceLayer.OBSERVATION],
        counts[EvidenceLayer.COMMENTARY],
        counts[EvidenceLayer.MODERN_RESEARCH],
        counts[EvidenceLayer.MODEL_INFERENCE],
        supports, contradicts, neutral,
    )
    missing = tuple(sorted(
        set(candidate.required_conditions)
        - set(candidate.satisfied_conditions)
        - set(candidate.violated_conditions)
    ))
    if candidate.violated_conditions:
        status = CandidateStatus.REJECTED
    elif not candidate.evidence or not supports:
        status = CandidateStatus.UNDERDETERMINED
    elif contradicts:
        status = CandidateStatus.CONTESTED
    elif missing:
        status = CandidateStatus.UNDERDETERMINED
    else:
        status = CandidateStatus.VIABLE

    return CandidateAssessment(
        candidate.candidate_id, status, profile, missing,
        tuple(sorted(candidate.violated_conditions)),
    )


def arbitrate(candidates: tuple[XiangCandidate, ...]) -> ArbitrationResult:
    ids = [candidate.candidate_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate ids must be unique")
    assessments = tuple(
        sorted((assess_candidate(c) for c in candidates), key=lambda a: a.candidate_id)
    )
    viable = tuple(a.candidate_id for a in assessments if a.status == CandidateStatus.VIABLE)
    rejected = tuple(a.candidate_id for a in assessments if a.status == CandidateStatus.REJECTED)
    # Even one viable candidate is not declared the truth: it is only the sole
    # currently viable candidate under the declared conditions and evidence.
    unresolved = len(viable) != 1 or any(
        a.status in (CandidateStatus.CONTESTED, CandidateStatus.UNDERDETERMINED)
        for a in assessments
    )
    return ArbitrationResult(assessments, viable, rejected, unresolved)
