"""M2 observation persistence as lazily-read events in the shared ZPCM log.

Raw source bytes remain in M1. This adapter stores only typed observations and
verified EvidenceRefs; it does not create a second evidence or event ledger.
The default store instance retains no corpus-sized Python cache. Reads are
indexed by event ID or keyset-paged through ZPCM; full materialization is an
explicit compatibility operation via the observations property.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from threading import RLock
from typing import Any, Iterator

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
        # Read only the indexed high-water mark. No event replay or corpus cache.
        self._last_sequence = self._memory.latest_domain_sequence(
            event_type=EVENT_TYPE, scope=self.scope,
        )

    @staticmethod
    def _event_id(record_id: str) -> str:
        return f"m2:observation:{record_id}"

    def _verify_evidence(self, observation: Observation) -> None:
        if observation.envelope.scope != self.scope:
            raise ObservationStoreError("observation scope does not match the store scope")
        refs = observation.envelope.source_refs
        for reference in refs:
            self._resolver.resolve(reference)
        if len(refs) == 1:
            reference = refs[0]
            if observation.source_locator.payload_version != reference.source_version:
                raise ObservationStoreError(
                    "single-source locator payload_version must match its EvidenceRef source_version"
                )
            if observation.modality is Modality.TEXT and (
                observation.source_locator.byte_start != reference.byte_start
                or observation.source_locator.byte_end != reference.byte_end
            ):
                raise ObservationStoreError(
                    "TEXT source locator byte span must match its single EvidenceRef"
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

    def _decode_event(
        self, event: dict[str, Any], *, replayed: bool = True,
    ) -> tuple[Observation, ObservationReceipt]:
        try:
            if event.get("event_type") != EVENT_TYPE or event.get("scope") != self.scope:
                raise ObservationStoreError("M2 observation event type/scope mismatch")
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
            if event.get("event_id") != self._event_id(record_id):
                raise ObservationStoreError("observation event identity is inconsistent")
            sequence = event.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
                raise ObservationStoreError("observation event sequence is invalid")
            return observation, ObservationReceipt(
                event_id=event["event_id"],
                sequence=sequence,
                payload_digest=event["payload_digest"],
                record_digest=digest_value,
                replayed=replayed,
            )
        except (ZPCMError, ContractError, ObservationStoreError):
            raise
        except Exception as exc:
            raise ObservationStoreError(f"M2 observation event is malformed: {exc}") from exc

    def get_observation(self, record_id: str) -> Observation | None:
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record_id must be non-empty")
        event = self._memory.get_domain_event(
            event_type=EVENT_TYPE, scope=self.scope, event_id=self._event_id(record_id),
        )
        if event is None:
            return None
        observation, _ = self._decode_event(event)
        if observation.envelope.record_id != record_id:
            raise ObservationStoreError("indexed observation record ID mismatch")
        return observation

    def get_receipt(self, record_id: str) -> ObservationReceipt | None:
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record_id must be non-empty")
        event = self._memory.get_domain_event(
            event_type=EVENT_TYPE, scope=self.scope, event_id=self._event_id(record_id),
        )
        if event is None:
            return None
        _, receipt = self._decode_event(event)
        return receipt

    def iter_observations(
        self, *, after_sequence: int = 0, page_size: int = 128,
    ) -> Iterator[tuple[Observation, ObservationReceipt]]:
        """Yield validated observations one bounded ZPCM page at a time."""
        previous = after_sequence
        for event in self._memory.iter_domain_events(
            event_type=EVENT_TYPE, scope=self.scope,
            after_sequence=after_sequence, page_size=page_size,
        ):
            sequence = event["sequence"]
            if sequence <= previous:
                raise ObservationStoreError("M2 observation event sequence is not strictly increasing")
            previous = sequence
            yield self._decode_event(event)

    @property
    def observations(self) -> dict[str, Observation]:
        """Compatibility view; explicitly materializes the full stream on demand."""
        result: dict[str, Observation] = {}
        for observation, _ in self.iter_observations():
            record_id = observation.envelope.record_id
            if record_id in result:
                raise ObservationStoreError("duplicate observation record ID in event stream")
            result[record_id] = observation
        return result

    def record_observation(self, observation: Observation) -> ObservationReceipt:
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        with self._lock:
            self._verify_evidence(observation)
            record_id = observation.envelope.record_id
            event_id = self._event_id(record_id)
            payload, body_digest = self._event_payload(observation)
            if body_digest != record_digest(observation):
                raise ObservationStoreError("canonical observation digest changed during serialization")

            # The SQLite event_id uniqueness constraint is the idempotency arbiter.
            # Refresh the stream cursor after unrelated concurrent appends.
            for _ in range(4):
                expected = self._memory.latest_domain_sequence(
                    event_type=EVENT_TYPE, scope=self.scope,
                )
                try:
                    raw = self._memory.append_domain_event(
                        event_type=EVENT_TYPE,
                        event_id=event_id,
                        scope=self.scope,
                        payload=payload,
                        expected_sequence=expected,
                    )
                except ZPCMError:
                    existing = self._memory.get_domain_event(
                        event_type=EVENT_TYPE, scope=self.scope, event_id=event_id,
                    )
                    if existing is not None:
                        prior, receipt = self._decode_event(existing)
                        if record_digest(prior) != body_digest:
                            raise ObservationStoreError(
                                "observation record_id is immutable; create a new revision ID"
                            )
                        return ObservationReceipt(
                            receipt.event_id, receipt.sequence, receipt.payload_digest,
                            receipt.record_digest, True,
                        )
                    latest = self._memory.latest_domain_sequence(
                        event_type=EVENT_TYPE, scope=self.scope,
                    )
                    if latest == expected:
                        raise
                    continue

                event = self._memory.get_domain_event(
                    event_type=EVENT_TYPE, scope=self.scope, event_id=event_id,
                )
                if event is None:
                    raise ObservationStoreError("committed observation event cannot be read back")
                committed, receipt = self._decode_event(event, replayed=raw["replayed"])
                if record_digest(committed) != body_digest:
                    raise ObservationStoreError(
                        "observation record_id is immutable; create a new revision ID"
                    )
                self._last_sequence = max(self._last_sequence, receipt.sequence)
                return receipt

            raise ObservationStoreError("concurrent observation appends did not stabilize; retry")
