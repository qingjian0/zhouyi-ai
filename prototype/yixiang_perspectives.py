"""XSL-4 multi-perspective Yi-Xiang hypothesis records.

This module stores competing lenses without selecting a single interpretation.
Evidence labels describe recorded provenance; they do not establish truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class EvidencePolarity(str, Enum):
    SUPPORTS = "SUPPORTS"
    COUNTERS = "COUNTERS"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    UNKNOWN = "UNKNOWN"


class PerspectiveStatus(str, Enum):
    UNTESTED = "UNTESTED"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class PerspectiveEvidence:
    evidence_id: str
    source_ref: str
    polarity: EvidencePolarity
    scope_note: str
    claim_note: str


@dataclass(frozen=True)
class AnalogyPerspective:
    perspective_id: str
    source_concept: str
    target_concept: str
    lens: str
    tradition_or_source: str
    applicability_conditions: tuple[str, ...]
    evidence: tuple[PerspectiveEvidence, ...]
    counterexample_notes: tuple[str, ...]
    limitations: tuple[str, ...]
    provenance: str


@dataclass(frozen=True)
class PerspectiveAssessment:
    status: PerspectiveStatus
    support_count: int
    counter_count: int
    context_count: int
    unknown_count: int


@dataclass(frozen=True)
class PerspectiveSet:
    set_id: str
    perspectives: tuple[AnalogyPerspective, ...]


class PerspectiveError(ValueError):
    """Raised when a perspective record violates the explicit data contract."""


def assess_perspective(perspective: AnalogyPerspective) -> PerspectiveAssessment:
    """Summarize attached evidence labels without scoring or deciding truth."""
    polarities = [item.polarity for item in perspective.evidence]
    support = polarities.count(EvidencePolarity.SUPPORTS)
    counter = polarities.count(EvidencePolarity.COUNTERS)
    context = polarities.count(EvidencePolarity.CONTEXT_ONLY)
    unknown = polarities.count(EvidencePolarity.UNKNOWN)
    if support and counter:
        status = PerspectiveStatus.CONTESTED
    elif polarities:
        status = PerspectiveStatus.EVIDENCE_ATTACHED
    else:
        status = PerspectiveStatus.UNTESTED
    return PerspectiveAssessment(status, support, counter, context, unknown)


def validate_perspective(perspective: AnalogyPerspective) -> None:
    """Validate record completeness; never infer semantic validity."""
    required = {
        "perspective_id": perspective.perspective_id,
        "source_concept": perspective.source_concept,
        "target_concept": perspective.target_concept,
        "lens": perspective.lens,
        "tradition_or_source": perspective.tradition_or_source,
        "provenance": perspective.provenance,
    }
    missing = [name for name, value in required.items()
               if not isinstance(value, str) or not value.strip()]
    if missing:
        raise PerspectiveError("missing required fields: " + ", ".join(missing))
    if not perspective.applicability_conditions:
        raise PerspectiveError("at least one applicability condition is required")
    if not perspective.limitations:
        raise PerspectiveError("at least one limitation is required")
    evidence_ids = [item.evidence_id for item in perspective.evidence]
    if any(not value.strip() for value in evidence_ids):
        raise PerspectiveError("evidence_id must be non-empty")
    if len(set(evidence_ids)) != len(evidence_ids):
        raise PerspectiveError("evidence_id values must be unique within a perspective")
    for item in perspective.evidence:
        if not item.source_ref.strip():
            raise PerspectiveError("every evidence item requires a source_ref")
        if not item.scope_note.strip() or not item.claim_note.strip():
            raise PerspectiveError("evidence scope_note and claim_note are required")
        if not isinstance(item.polarity, EvidencePolarity):
            raise PerspectiveError("evidence polarity must be explicit")


def validate_perspective_set(perspective_set: PerspectiveSet) -> None:
    """Keep all perspectives distinct; no implicit winner or deduplication."""
    if not perspective_set.set_id.strip():
        raise PerspectiveError("set_id is required")
    ids = [item.perspective_id for item in perspective_set.perspectives]
    if len(set(ids)) != len(ids):
        raise PerspectiveError("perspective_id values must be unique within a set")
    for item in perspective_set.perspectives:
        validate_perspective(item)


def build_perspective_set(
    set_id: str, perspectives: Iterable[AnalogyPerspective]
) -> PerspectiveSet:
    result = PerspectiveSet(set_id, tuple(perspectives))
    validate_perspective_set(result)
    return result
