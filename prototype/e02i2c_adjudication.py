"""E02-I2-C: evidence contracts and conservative temporal event adjudication.

The adjudicator consumes only observable evidence and identity snapshots. Hidden
identity labels, generator transition plans and evaluator event labels are not
part of these contracts. Decisions are proposals; applying them to the lineage
ledger is a separate transactional step.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class MissingReason(str, Enum):
    SENSOR_GAP = "SENSOR_GAP"
    NO_EXPOSURE = "NO_EXPOSURE"
    FILTERED = "FILTERED"
    UNKNOWN = "UNKNOWN"


class EvidencePolarity(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    ABSENCE = "ABSENCE"


class EventType(str, Enum):
    CREATE = "CREATE"
    KEEP = "KEEP"
    MODIFY = "MODIFY"
    ABSTAIN = "ABSTAIN"
    SUSPEND = "SUSPEND"
    REACTIVATE = "REACTIVATE"
    REACTIVATE_MODIFY = "REACTIVATE_MODIFY"
    RETIRE = "RETIRE"
    REPLACE = "REPLACE"
    SPLIT = "SPLIT"
    MERGE = "MERGE"


@dataclass(frozen=True)
class ObservationOpportunity:
    """How well a window was observed; low coverage is not negative evidence."""

    window: int
    environment: str
    expected_samples: int
    observed_samples: int
    coverage: float
    missing_reason: MissingReason | None = None

    def __post_init__(self) -> None:
        if self.window < 0 or not self.environment.strip():
            raise ValueError("window and environment must be valid")
        if self.expected_samples < 1 or not 0 <= self.observed_samples <= self.expected_samples:
            raise ValueError("sample counts are invalid")
        if not 0.0 <= self.coverage <= 1.0:
            raise ValueError("coverage must be between 0 and 1")
        if self.observed_samples == self.expected_samples and self.missing_reason is not None:
            raise ValueError("a complete observation cannot have a missing reason")

    def sufficient(self, *, min_coverage: float = 0.8,
                   min_samples: int = 1) -> bool:
        if not 0.0 <= min_coverage <= 1.0 or min_samples < 1:
            raise ValueError("invalid sufficiency threshold")
        return (self.observed_samples >= min_samples
                and self.coverage >= min_coverage)


@dataclass(frozen=True)
class EvidencePacket:
    """Auditable observation; deliberately contains no hidden truth labels."""

    evidence_id: str
    sample_id: str
    window: int
    environment: str
    split: str
    polarity: EvidencePolarity
    source_version_id: str | None
    candidate_signature: str | None
    raw_observation_ref: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (
            self.evidence_id, self.sample_id, self.environment,
            self.raw_observation_ref,
        )):
            raise ValueError("evidence identifiers and provenance must be non-empty")
        if self.window < 0:
            raise ValueError("evidence window must be non-negative")
        if self.split not in {"train", "gate", "test"}:
            raise ValueError("split must be train, gate or test")
        if self.polarity == EvidencePolarity.SUPPORTS and not self.candidate_signature:
            raise ValueError("supporting evidence requires a candidate signature")
        if self.candidate_signature is not None and not self.candidate_signature.strip():
            raise ValueError("candidate signature cannot be blank")


@dataclass(frozen=True)
class IdentitySnapshot:
    identity_id: str
    status: str
    version_id: str
    signature: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (
            self.identity_id, self.status, self.version_id, self.signature,
        )):
            raise ValueError("identity snapshot fields must be non-empty")
        if self.status not in {"ACTIVE", "SUSPENDED", "SPLIT", "MERGED", "REPLACED", "RETIRED"}:
            raise ValueError("unknown identity status")


@dataclass(frozen=True)
class EventDecision:
    event: EventType
    identity_id: str | None
    from_version_id: str | None
    candidate_signature: str | None
    evidence_refs: tuple[str, ...]
    reason: str
    abstained: bool = False


def _abstain(identity: IdentitySnapshot | None, reason: str,
             candidate_signature: str | None = None) -> EventDecision:
    return EventDecision(
        EventType.ABSTAIN,
        identity.identity_id if identity else None,
        identity.version_id if identity else None,
        candidate_signature,
        (),
        reason,
        True,
    )


def adjudicate_event(
    identity: IdentitySnapshot | None,
    opportunities: Iterable[ObservationOpportunity],
    evidence: Iterable[EvidencePacket],
    *,
    candidate_signature: str | None = None,
    min_coverage: float = 0.8,
    min_samples: int = 1,
    required_windows: int = 2,
) -> EventDecision:
    """Propose one conservative event from temporal observations.

    CREATE/MODIFY require support in multiple independent windows. SUSPEND
    requires consecutive sufficiently observed ABSENCE windows. RETIRE requires
    a suspended identity plus repeated explicit contradiction. Insufficient
    opportunity and ambiguous transitions always ABSTAIN.
    """
    opportunities = tuple(opportunities)
    evidence = tuple(evidence)
    if required_windows < 2:
        raise ValueError("required_windows must be at least two")
    if not 0.0 <= min_coverage <= 1.0 or min_samples < 1:
        raise ValueError("invalid observation threshold")

    opportunity_by_window: dict[int, ObservationOpportunity] = {}
    for item in opportunities:
        if item.window in opportunity_by_window:
            raise ValueError("at most one opportunity record is allowed per window")
        opportunity_by_window[item.window] = item
    evidence_ids = [item.evidence_id for item in evidence]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("evidence IDs must be unique")
    if any(item.window not in opportunity_by_window for item in evidence):
        raise ValueError("every evidence packet needs a matching opportunity record")

    sufficient_windows = {
        window for window, item in opportunity_by_window.items()
        if item.sufficient(min_coverage=min_coverage, min_samples=min_samples)
    }
    eligible = tuple(item for item in evidence if item.window in sufficient_windows)
    if not sufficient_windows:
        return _abstain(identity, "no sufficiently observed window", candidate_signature)

    def distinct_windows(items: Iterable[EvidencePacket]) -> set[int]:
        return {item.window for item in items}

    def refs(items: Iterable[EvidencePacket]) -> tuple[str, ...]:
        return tuple(sorted({item.evidence_id for item in items}))

    supporting = tuple(
        item for item in eligible
        if item.polarity == EvidencePolarity.SUPPORTS
        and (candidate_signature is None or item.candidate_signature == candidate_signature)
    )
    contradictions = tuple(
        item for item in eligible if item.polarity == EvidencePolarity.CONTRADICTS
    )
    absences = tuple(
        item for item in eligible if item.polarity == EvidencePolarity.ABSENCE
    )

    if identity is None:
        windows = distinct_windows(supporting)
        samples = {item.sample_id for item in supporting}
        if len(windows) >= required_windows and len(samples) >= required_windows:
            signatures = {item.candidate_signature for item in supporting}
            if len(signatures) == 1:
                signature = next(iter(signatures))
                return EventDecision(
                    EventType.CREATE, None, None, signature, refs(supporting),
                    "repeated independent support across sufficiently observed windows",
                )
        return _abstain(None, "new identity lacks repeated independent support", candidate_signature)

    if identity.status in {"SPLIT", "MERGED", "REPLACED", "RETIRED"}:
        return _abstain(identity, "terminal identities cannot transition", candidate_signature)

    if identity.status == "SUSPENDED":
        changed_support = tuple(
            item for item in supporting
            if item.candidate_signature != identity.signature
            and item.source_version_id == identity.version_id
        )
        if (len(distinct_windows(changed_support)) >= required_windows
                and len({item.sample_id for item in changed_support}) >= required_windows):
            return EventDecision(
                EventType.REACTIVATE_MODIFY, identity.identity_id, identity.version_id,
                candidate_signature, refs(changed_support),
                "fresh support and version-linked continuity across multiple windows",
            )
        same_support = tuple(
            item for item in supporting if item.candidate_signature == identity.signature
        )
        if same_support and len({item.sample_id for item in same_support}) >= 1:
            return EventDecision(
                EventType.REACTIVATE, identity.identity_id, identity.version_id,
                identity.signature, refs(same_support),
                "fresh confirming evidence for the suspended version",
            )
        if len(distinct_windows(contradictions)) >= required_windows:
            return EventDecision(
                EventType.RETIRE, identity.identity_id, identity.version_id,
                candidate_signature, refs(contradictions),
                "repeated independent contradiction after suspension",
            )
        return _abstain(identity, "suspended identity lacks sufficient reactivation or retirement evidence",
                        candidate_signature)

    # Active identity: same-signature support is a KEEP, not a new identity.
    same_support = tuple(
        item for item in supporting if item.candidate_signature == identity.signature
    )
    if same_support:
        return EventDecision(
            EventType.KEEP, identity.identity_id, identity.version_id,
            identity.signature, refs(same_support),
            "support confirms the current version",
        )

    changed_support = tuple(
        item for item in supporting
        if item.candidate_signature != identity.signature
        and item.source_version_id == identity.version_id
    )
    if (len(distinct_windows(changed_support)) >= required_windows
            and len({item.sample_id for item in changed_support}) >= required_windows):
        signatures = {item.candidate_signature for item in changed_support}
        if len(signatures) == 1:
            signature = next(iter(signatures))
            return EventDecision(
                EventType.MODIFY, identity.identity_id, identity.version_id,
                signature, refs(changed_support),
                "version-linked continuity supports the same structural change across windows",
            )

    # Absence is only meaningful when the corresponding observation opportunity
    # was sufficient. Require a consecutive tail; a gap breaks the sequence.
    absence_windows = {
        item.window for item in absences
        if item.window in sufficient_windows
    }
    consecutive = 0
    for window in sorted(sufficient_windows, reverse=True):
        if window in absence_windows:
            consecutive += 1
        else:
            break
    if consecutive >= required_windows:
        return EventDecision(
            EventType.SUSPEND, identity.identity_id, identity.version_id,
            identity.signature, refs(absences),
            "consecutive sufficiently observed absence windows",
        )

    if contradictions:
        return _abstain(identity, "contradiction is not absence and does not establish a replacement event",
                        candidate_signature)
    return _abstain(identity, "evidence is insufficient to distinguish KEEP, MODIFY or CREATE",
                    candidate_signature)
