"""M2 observation persistence as events in the existing ZPCM event log.

Raw source bytes remain in M1. This adapter stores only typed observations and
verified EvidenceRefs; it does not create a second evidence or event ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from threading import RLock
from typing import Any

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.observation_contract import (
    ContractError,
    EvidenceRef,
    ExtractionMethod,
    Modality,
    Observation,
    ParseStatus,
    RecordEnvelope,
    Score,
    SourceLocator,
    canonical_json,
    record_digest,
)
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


EVENT_TYPE = "m2_observation"
EVENT_SCHEMA = "m2-observation-event-v1"


class ObservationStoreError(RuntimeError):
    """An M2 observation event cannot be committed or safely replayed."""


@dataclass(frozen=True)
class ObservationReceipt:
    event_id: str
    sequence: int
    payload_digest: str
    record_digest: str
    replayed: bool = False


def _evidence_ref_from_dict(value: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(**value)


def _observation_from_dict(value: dict[str, Any]) -> Observation:
    envelope_value = dict(value["envelope"])
    envelope_value["source_refs"] = tuple(
        _evidence_ref_from_dict(item) for item in envelope_value["source_refs"]
    )
    envelope_value["derivation_refs"] = tuple(envelope_value.get("derivation_refs", ()))
    envelope = RecordEnvelope(**envelope_value)

    locator_value = dict(value["source_locator"])
    locator_value["modality"] = Modality(locator_value["modality"])
    if locator_value.get("region_xywh") is not None:
        locator_value["region_xywh"] = tuple(locator_value["region_xywh"])
    locator = SourceLocator(**locator_value)

    score_value = value.get("extraction_score")
    score = Score(**score_value) if score_value is not None else None
    return Observation(
        envelope=envelope,
        modality=Modality(value["modality"]),
        source_locator=locator,
        extractor_id=value["extractor_id"],
        extractor_version=value["extractor_version"],
        extraction_method=ExtractionMethod(value["extraction_method"]),
        parse_status=ParseStatus(value["parse_status"]),
        extraction_score=score,
        language=value.get("language"),
        speaker=value.get("speaker"),
    )


class PersistentM2ObservationStore:
    """Append-only observation adapter backed by ZPCM's shared memory_events."""

    def __init__(
        self,
        memory: ZPCMMemory,
        resolver: SQLiteEvidenceRefResolver,
        *,
        scope: str,
    ) -> None:
        if not isinstance(memory, ZPCMMemory):
            raise TypeError("memory must be ZPCMMemory")
        if not isinstance(resolver, SQLiteEvidenceRefResolver):
            raise TypeError("resolver must be SQLiteEvidenceRefResolver")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be non-empty")
        self._memory = memory
        self._resolver = resolver
        self.scope = scope
        self._lock = RLock()
        self._observations: dict[str, Observation] = {}
        self._receipts: dict[str, ObservationReceipt] = {}
        self._record_digests: dict[str, str] = {}
        self._last_sequence = 0
        self._restore()

    @property
    def observations(self) -> dict[str, Observation]:
        with self._lock:
            return dict(self._observations)

    def _verify_evidence(self, observation: Observation) -> None:
        if observation.envelope.scope != self.scope:
            raise ObservationStoreError("observation scope does not match the store scope")
        refs = observation.envelope.source_refs
        for reference in refs:
            self._resolver.resolve(reference)
        if len(refs) == 1 and observation.source_locator.payload_version != refs[0].source_version:
            raise ObservationStoreError(
                "single-source locator payload_version must match its EvidenceRef source_version"
            )

    @staticmethod
    def _event_payload(observation: Observation) -> tuple[dict[str, Any], str]:
        body = json.loads(canonical_json(observation))
        body_digest = record_digest(observation)
        return {
            "schema_version": EVENT_SCHEMA,
            "kind": "observation_recorded",
            "body": body,
            "body_digest": body_digest,
        }, body_digest

    def _restore(self) -> None:
        try:
            events = self._memory.replay_domain_events(event_type=EVENT_TYPE, scope=self.scope)
            previous = 0
            staged: dict[str, Observation] = {}
            receipts: dict[str, ObservationReceipt] = {}
            record_digests: dict[str, str] = {}
            for event in events:
                sequence = event["sequence"]
                if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous:
                    raise ObservationStoreError("M2 observation event sequence is not strictly increasing")
                previous = sequence
                payload = event["payload"]
                if payload.get("schema_version") != EVENT_SCHEMA or payload.get("kind") != "observation_recorded":
                    raise ObservationStoreError("unsupported M2 observation event schema/kind")
                body = payload.get("body")
                if not isinstance(body, dict):
                    raise ObservationStoreError("observation event body must be an object")
                observation = _observation_from_dict(body)
                self._verify_evidence(observation)
                digest_value = record_digest(observation)
                if digest_value != payload.get("body_digest"):
                    raise ObservationStoreError("observation record digest mismatch")
                record_id = observation.envelope.record_id
                expected_event_id = f"m2:observation:{record_id}"
                if event["event_id"] != expected_event_id or record_id in staged:
                    raise ObservationStoreError("observation event identity is inconsistent or duplicated")
                staged[record_id] = observation
                record_digests[record_id] = digest_value
                receipts[record_id] = ObservationReceipt(
                    event_id=event["event_id"],
                    sequence=sequence,
                    payload_digest=event["payload_digest"],
                    record_digest=digest_value,
                    replayed=True,
                )
            self._observations = staged
            self._receipts = receipts
            self._record_digests = record_digests
            self._last_sequence = previous
        except (ZPCMError, ContractError, ObservationStoreError):
            raise
        except Exception as exc:
            raise ObservationStoreError(f"M2 observation replay failed: {exc}") from exc

    def record_observation(self, observation: Observation) -> ObservationReceipt:
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        with self._lock:
            self._verify_evidence(observation)
            record_id = observation.envelope.record_id
            digest_value = record_digest(observation)
            old = self._observations.get(record_id)
            if old is not None:
                if self._record_digests[record_id] != digest_value:
                    raise ObservationStoreError("observation record_id is immutable; create a new revision ID")
                prior = self._receipts[record_id]
                return ObservationReceipt(
                    prior.event_id, prior.sequence, prior.payload_digest, prior.record_digest, True
                )

            event_id = f"m2:observation:{record_id}"
            payload, body_digest = self._event_payload(observation)
            if body_digest != digest_value:
                raise ObservationStoreError("canonical observation digest changed during serialization")
            try:
                raw = self._memory.append_domain_event(
                    event_type=EVENT_TYPE,
                    event_id=event_id,
                    scope=self.scope,
                    payload=payload,
                    expected_sequence=self._last_sequence,
                )
            except ZPCMError:
                raise
            receipt = ObservationReceipt(
                event_id=event_id,
                sequence=raw["sequence"],
                payload_digest=raw["payload_digest"],
                record_digest=digest_value,
                replayed=raw["replayed"],
            )
            if receipt.replayed:
                raise ObservationStoreError(
                    "event exists in ZPCM outside this adapter's restored state; reconstruct before retry"
                )
            self._observations[record_id] = observation
            self._receipts[record_id] = receipt
            self._record_digests[record_id] = digest_value
            self._last_sequence = receipt.sequence
            return receipt
