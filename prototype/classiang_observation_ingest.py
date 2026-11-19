"""Evidence-bound ingestion of structured feature claims into classiang.

This adapter validates source spans and provenance. It deliberately does not
extract semantics from free text, invent feature dimensions, or assign
relevance scores. Those remain explicit upstream responsibilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from prototype.classiang_engine import (
    FeatureAtom,
    FeatureCandidate,
    Observation,
)


@dataclass(frozen=True)
class RawFeatureClaim:
    """One explicitly supplied feature claim anchored to an exact source span."""

    dimension: str
    value: str
    evidence_refs: tuple[str, ...]
    source_start: int
    source_end: int
    source_quote: str
    purpose_scores: tuple[tuple[str, float], ...] = ()

    def validate(self, *, source_text: str, source_evidence_refs: set[str]) -> None:
        atom = FeatureAtom(self.dimension, self.value)
        atom.validate()
        if not isinstance(self.evidence_refs, tuple) or not self.evidence_refs:
            raise ValueError("claim evidence_refs must be a non-empty tuple")
        if any(not isinstance(ref, str) or not ref.strip() for ref in self.evidence_refs):
            raise ValueError("claim evidence_refs must contain non-empty strings")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("claim evidence_refs must be unique")
        if not set(self.evidence_refs) <= source_evidence_refs:
            raise ValueError("claim references unknown source evidence")
        for name, offset in (("source_start", self.source_start), ("source_end", self.source_end)):
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise ValueError(f"{name} must be an integer")
        if not 0 <= self.source_start < self.source_end <= len(source_text):
            raise ValueError("claim source span is outside source_text")
        if not isinstance(self.source_quote, str) or not self.source_quote:
            raise ValueError("source_quote must be non-empty")
        if source_text[self.source_start:self.source_end] != self.source_quote:
            raise ValueError("source_quote does not match the referenced source span")
        if not isinstance(self.purpose_scores, tuple):
            raise ValueError("purpose_scores must be a tuple")


@dataclass(frozen=True)
class RawObservationRecord:
    observation_id: str
    subject_id: str
    domain: str
    source_text: str
    evidence_refs: tuple[str, ...]
    claims: tuple[RawFeatureClaim, ...]
    context: tuple[str, ...] = ()

    def validate(self) -> None:
        for name in ("observation_id", "subject_id", "domain", "source_text"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name, values in (("evidence_refs", self.evidence_refs), ("context", self.context)):
            if not isinstance(values, tuple):
                raise ValueError(f"{name} must be a tuple")
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"{name} must contain non-empty strings")
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        if not self.evidence_refs:
            raise ValueError("evidence_refs must not be empty")
        if not isinstance(self.claims, tuple):
            raise ValueError("claims must be a tuple")
        for claim in self.claims:
            if not isinstance(claim, RawFeatureClaim):
                raise ValueError("claims must contain RawFeatureClaim")
            claim.validate(
                source_text=self.source_text,
                source_evidence_refs=set(self.evidence_refs),
            )


@dataclass(frozen=True)
class IngestionResult:
    observation: Observation
    claim_count: int
    unscored_feature_count: int
    evidence_span_refs: tuple[str, ...]


def ingest_observation(record: RawObservationRecord) -> IngestionResult:
    """Convert validated, span-anchored claims without manufacturing semantics.

    A feature is selectable for a task only when its caller-supplied
    purpose_scores include that task. Empty scores remain explicitly unscored.
    Generated span references use Python string offsets (Unicode code points),
    not UTF-8 byte offsets.
    """
    if not isinstance(record, RawObservationRecord):
        raise ValueError("record must be RawObservationRecord")
    record.validate()

    span_refs: set[str] = set()
    features = []
    for index, claim in enumerate(record.claims):
        refs = tuple(sorted(
            f"{source_ref}#chars:{claim.source_start}:{claim.source_end}"
            for source_ref in claim.evidence_refs
        ))
        span_refs.update(refs)
        features.append(FeatureCandidate(
            feature_id=f"{record.observation_id}:claim:{index:06d}",
            atom=FeatureAtom(claim.dimension, claim.value),
            evidence_refs=refs,
            purpose_scores=claim.purpose_scores,
        ))

    observation = Observation(
        observation_id=record.observation_id,
        subject_id=record.subject_id,
        domain=record.domain,
        evidence_refs=tuple(sorted(set(record.evidence_refs) | span_refs)),
        features=tuple(features),
        context=record.context,
    )
    observation.validate()
    return IngestionResult(
        observation=observation,
        claim_count=len(features),
        unscored_feature_count=sum(not item.purpose_scores for item in features),
        evidence_span_refs=tuple(sorted(span_refs)),
    )
