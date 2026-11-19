"""Evidence-verified Observation -> SemanticUnitCandidate handoff.

The extractor is injected. This module enforces persistence provenance,
bounded output, and epistemic separation; it is not a semantic model.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Protocol

from prototype.m2_observation_store import ObservationReceipt
from prototype.m2_semantic_unit_store import SemanticUnitReceipt
from prototype.observation_contract import (
    GroundingStatus,
    Observation,
    ParseStatus,
    SemanticUnitCandidate,
    TruthStatus,
    record_digest,
)


class SemanticExtractionError(ValueError):
    """An extraction result violates the persisted-observation contract."""


class SemanticUnitExtractor(Protocol):
    def extract(self, observation: Observation) -> Iterable[SemanticUnitCandidate]:
        """Return candidates derived only from the supplied observation."""


class ObservationReader(Protocol):
    scope: str

    def get_observation(self, record_id: str) -> Observation | None: ...

    def get_receipt(self, record_id: str) -> ObservationReceipt | None: ...


class CandidateWriter(Protocol):
    scope: str

    def record_candidate(self, candidate: SemanticUnitCandidate) -> SemanticUnitReceipt: ...


@dataclass(frozen=True)
class ExtractionBatchReceipt:
    observation_record_id: str
    observation_event_ref: str
    candidate_count: int
    candidate_receipts: tuple[SemanticUnitReceipt, ...]
    partial_observation: bool


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _same_receipt(left: ObservationReceipt, right: ObservationReceipt) -> bool:
    # replayed is an operation outcome, not part of the immutable event identity.
    return (
        left.event_id == right.event_id
        and left.sequence == right.sequence
        and left.payload_digest == right.payload_digest
        and left.record_digest == right.record_digest
    )


class ObservationCandidatePipeline:
    """Validate a bounded extraction batch before writing any candidate.

    The observation and receipt are re-read from the authoritative M2 store.
    A caller-created receipt with a matching record digest is not sufficient.
    Candidate appends are individually durable; a storage failure can leave a
    prefix, so extractor IDs and payloads must be stable across retries.
    """

    def __init__(
        self,
        extractor: SemanticUnitExtractor,
        observation_store: ObservationReader,
        candidate_store: CandidateWriter,
        *,
        max_candidates_per_observation: int = 64,
    ) -> None:
        if not callable(getattr(extractor, "extract", None)):
            raise TypeError("extractor must provide extract(observation)")
        for name, store, methods in (
            ("observation_store", observation_store, ("get_observation", "get_receipt")),
            ("candidate_store", candidate_store, ("record_candidate",)),
        ):
            if not isinstance(getattr(store, "scope", None), str) or not store.scope.strip():
                raise TypeError(f"{name} must expose a non-empty scope")
            if any(not callable(getattr(store, method, None)) for method in methods):
                raise TypeError(f"{name} is missing a required read/write method")
        if observation_store.scope != candidate_store.scope:
            raise ValueError("observation_store and candidate_store scopes must match")
        if (
            isinstance(max_candidates_per_observation, bool)
            or not isinstance(max_candidates_per_observation, int)
            or max_candidates_per_observation < 1
        ):
            raise ValueError("max_candidates_per_observation must be a positive integer")
        self._extractor = extractor
        self._observations = observation_store
        self._candidates = candidate_store
        self._limit = max_candidates_per_observation

    def _verify_persisted_observation(
        self, observation: Observation, supplied: ObservationReceipt
    ) -> tuple[str, str]:
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        if not isinstance(supplied, ObservationReceipt):
            raise TypeError("observation_receipt must be an ObservationReceipt")
        observation_id = observation.envelope.record_id
        event_ref = f"m2:observation:{observation_id}"
        if observation.envelope.scope != self._observations.scope:
            raise SemanticExtractionError("observation scope does not match the observation store")
        if supplied.event_id != event_ref:
            raise SemanticExtractionError("observation receipt does not identify this observation")
        if (
            isinstance(supplied.sequence, bool)
            or not isinstance(supplied.sequence, int)
            or supplied.sequence < 1
        ):
            raise SemanticExtractionError("observation receipt sequence must be a positive integer")
        if not _valid_digest(supplied.payload_digest) or not _valid_digest(supplied.record_digest):
            raise SemanticExtractionError("observation receipt digests must be lowercase SHA-256 hex")
        digest = record_digest(observation)
        if supplied.record_digest != digest:
            raise SemanticExtractionError("observation receipt digest does not match the supplied record")

        persisted = self._observations.get_observation(observation_id)
        if persisted is None:
            raise SemanticExtractionError("observation is not present in the authoritative M2 store")
        if persisted != observation:
            raise SemanticExtractionError("supplied observation differs from the persisted M2 record")
        persisted_receipt = self._observations.get_receipt(observation_id)
        if not isinstance(persisted_receipt, ObservationReceipt):
            raise SemanticExtractionError("authoritative M2 observation receipt is missing or malformed")
        if not _same_receipt(supplied, persisted_receipt):
            raise SemanticExtractionError("supplied observation receipt differs from the persisted receipt")
        return observation_id, event_ref

    def extract_and_persist(
        self,
        observation: Observation,
        *,
        observation_receipt: ObservationReceipt,
    ) -> ExtractionBatchReceipt:
        observation_id, event_ref = self._verify_persisted_observation(
            observation, observation_receipt
        )
        if observation.parse_status in (ParseStatus.UNPARSEABLE, ParseStatus.REJECTED):
            raise SemanticExtractionError(
                f"observation parse status {observation.parse_status.value} is not extractable"
            )

        try:
            iterator = iter(self._extractor.extract(observation))
        except TypeError as exc:
            raise SemanticExtractionError(
                "extractor must return an iterable of candidates"
            ) from exc

        validated: list[SemanticUnitCandidate] = []
        seen_ids: set[str] = set()
        for candidate in iterator:
            if len(validated) >= self._limit:
                raise SemanticExtractionError(
                    f"extractor exceeded per-observation limit ({self._limit})"
                )
            if not isinstance(candidate, SemanticUnitCandidate):
                raise SemanticExtractionError(
                    "extractor yielded a non-SemanticUnitCandidate value"
                )
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

        receipts = tuple(self._candidates.record_candidate(item) for item in validated)
        return ExtractionBatchReceipt(
            observation_record_id=observation_id,
            observation_event_ref=event_ref,
            candidate_count=len(validated),
            candidate_receipts=receipts,
            partial_observation=observation.parse_status is ParseStatus.PARTIAL,
        )
