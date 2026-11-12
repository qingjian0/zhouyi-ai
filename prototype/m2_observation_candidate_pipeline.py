"""Bounded Observation → SemanticUnitCandidate extraction boundary.

The extractor is injected. This module validates provenance and epistemic
boundaries; it does not provide general language understanding or grounding.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from prototype.m2_observation_store import (
    ObservationReceipt,
    PersistentM2ObservationStore,
)
from prototype.m2_semantic_unit_store import (
    PersistentSemanticUnitCandidateStore,
    SemanticUnitReceipt,
)
from prototype.observation_contract import (
    GroundingStatus,
    Observation,
    ParseStatus,
    SemanticUnitCandidate,
    TruthStatus,
    record_digest,
)


class SemanticExtractionError(ValueError):
    """An extractor result violates the Observation-derived candidate contract."""


class SemanticUnitExtractor(Protocol):
    """Pluggable parser/model/human-assisted extraction implementation."""

    def extract(self, observation: Observation) -> Iterable[SemanticUnitCandidate]:
        """Return candidates derived only from the supplied observation."""
        ...


@dataclass(frozen=True)
class ExtractionBatchReceipt:
    observation_record_id: str
    observation_event_ref: str
    candidate_count: int
    candidate_receipts: tuple[SemanticUnitReceipt, ...]
    partial_observation: bool


class ObservationCandidatePipeline:
    """Validate and persist one bounded extraction batch.

    Validation completes before the first append, preventing malformed later
    outputs from causing a partially-written batch. ZPCM commits each candidate
    as an individual append-only event; a process/database failure during the
    append loop can leave a durable prefix, which is retryable only with the
    same immutable candidate IDs and contents.
    """

    def __init__(
        self,
        extractor: SemanticUnitExtractor,
        candidate_store: PersistentSemanticUnitCandidateStore,
        observation_store: PersistentM2ObservationStore,
        *,
        max_candidates_per_observation: int = 64,
    ) -> None:
        if not callable(getattr(extractor, "extract", None)):
            raise TypeError("extractor must provide extract(observation)")
        if not callable(getattr(candidate_store, "record_candidate", None)):
            raise TypeError("candidate_store must provide record_candidate(candidate)")
        if not callable(getattr(observation_store, "verify_observation_receipt", None)):
            raise TypeError("observation_store must verify durable observation receipts")
        if not isinstance(getattr(candidate_store, "scope", None), str):
            raise TypeError("candidate_store must expose a scope")
        if (isinstance(max_candidates_per_observation, bool)
                or not isinstance(max_candidates_per_observation, int)
                or max_candidates_per_observation < 1):
            raise ValueError("max_candidates_per_observation must be a positive integer")
        if getattr(observation_store, "scope", None) != getattr(candidate_store, "scope", None):
            raise ValueError("observation and candidate stores must use the same scope")
        self._extractor = extractor
        self._store = candidate_store
        self._observation_store = observation_store
        self._limit = max_candidates_per_observation

    def extract_and_persist(
        self,
        observation: Observation,
        *,
        observation_receipt: ObservationReceipt,
    ) -> ExtractionBatchReceipt:
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        if not isinstance(observation_receipt, ObservationReceipt):
            raise TypeError("observation_receipt must be an ObservationReceipt")
        observation_id = observation.envelope.record_id
        event_ref = f"m2:observation:{observation_id}"
        if observation.envelope.scope != self._store.scope:
            raise SemanticExtractionError("observation scope does not match candidate store")
        try:
            self._observation_store.verify_observation_receipt(observation, observation_receipt)
        except Exception as exc:
            raise SemanticExtractionError(
                f"observation receipt is not verified by the durable store: {exc}"
            ) from exc
        if observation.parse_status in (ParseStatus.UNPARSEABLE, ParseStatus.REJECTED):
            raise SemanticExtractionError(
                f"observation parse status {observation.parse_status.value} is not extractable"
            )

        raw_candidates = self._extractor.extract(observation)
        try:
            iterator = iter(raw_candidates)
        except TypeError as exc:
            raise SemanticExtractionError("extractor must return an iterable of candidates") from exc

        validated: list[SemanticUnitCandidate] = []
        seen_ids: set[str] = set()
        for candidate in iterator:
            if len(validated) >= self._limit:
                raise SemanticExtractionError(
                    f"extractor exceeded per-observation limit ({self._limit})"
                )
            if not isinstance(candidate, SemanticUnitCandidate):
                raise SemanticExtractionError("extractor yielded a non-SemanticUnitCandidate value")
            envelope = candidate.envelope
            if envelope.scope != observation.envelope.scope:
                raise SemanticExtractionError("candidate scope differs from source observation")
            if envelope.source_refs != observation.envelope.source_refs:
                raise SemanticExtractionError(
                    "candidate must preserve the observation's exact M1 source_refs"
                )
            if event_ref not in envelope.derivation_refs:
                raise SemanticExtractionError(
                    "candidate derivation_refs must cite its source M2 observation event"
                )
            if candidate.grounding_status is not GroundingStatus.UNRESOLVED:
                raise SemanticExtractionError(
                    "extraction cannot claim entity grounding; use the separate grounding stage"
                )
            if candidate.truth_status is not TruthStatus.UNKNOWN:
                raise SemanticExtractionError(
                    "extraction cannot adjudicate truth; truth_status must remain UNKNOWN"
                )
            for attribute in candidate.typed_attributes:
                if any(ref not in observation.envelope.source_refs for ref in attribute.source_refs):
                    raise SemanticExtractionError(
                        "typed attribute references evidence outside its source observation"
                    )
            if envelope.record_id in seen_ids:
                raise SemanticExtractionError("extractor emitted duplicate candidate record_id")
            seen_ids.add(envelope.record_id)
            validated.append(candidate)

        receipts = tuple(self._store.record_candidate(item) for item in validated)
        return ExtractionBatchReceipt(
            observation_record_id=observation_id,
            observation_event_ref=event_ref,
            candidate_count=len(validated),
            candidate_receipts=receipts,
            partial_observation=observation.parse_status is ParseStatus.PARTIAL,
        )
