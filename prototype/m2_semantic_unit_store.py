"""Persistent, evidence-verified SemanticUnitCandidate stream on ZPCM.

Candidates are immutable append-only records. A revision is a new record_id
whose derivation_refs point to the prior candidate. This adapter does not
adjudicate truth or create a second event ledger.
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
    EpistemicStatus,
    GroundingStatus,
    RecordEnvelope,
    RoleBinding,
    Score,
    SemanticUnitCandidate,
    TruthStatus,
    TypedAttribute,
    UnitKind,
    canonical_json,
    record_digest,
)
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


EVENT_TYPE = "m2_semantic_unit_candidate"
EVENT_SCHEMA = "m2-semantic-unit-candidate-event-v1"


class SemanticUnitStoreError(RuntimeError):
    """A candidate cannot be committed or safely read from ZPCM."""


@dataclass(frozen=True)
class SemanticUnitReceipt:
    event_id: str
    sequence: int
    payload_digest: str
    record_digest: str
    replayed: bool = False


def _evidence_ref(value: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(**value)


def _candidate_from_dict(value: dict[str, Any]) -> SemanticUnitCandidate:
    envelope_value = dict(value["envelope"])
    envelope_value["source_refs"] = tuple(
        _evidence_ref(item) for item in envelope_value["source_refs"]
    )
    envelope_value["derivation_refs"] = tuple(envelope_value.get("derivation_refs", ()))
    envelope = RecordEnvelope(**envelope_value)

    attributes = []
    for item in value.get("typed_attributes", ()):
        row = dict(item)
        row["source_refs"] = tuple(_evidence_ref(ref) for ref in row.get("source_refs", ()))
        attributes.append(TypedAttribute(**row))

    roles = tuple(RoleBinding(**item) for item in value.get("role_bindings", ()))
    score_value = value.get("ranking_score")
    score = Score(**score_value) if score_value is not None else None
    return SemanticUnitCandidate(
        envelope=envelope,
        kind=UnitKind(value["kind"]),
        surface_forms=tuple(value["surface_forms"]),
        typed_attributes=tuple(attributes),
        role_bindings=roles,
        canonical_key=value.get("canonical_key"),
        grounding_status=GroundingStatus(value["grounding_status"]),
        epistemic_status=EpistemicStatus(value["epistemic_status"]),
        extractor_confidence=value.get("extractor_confidence"),
        source_reliability=value.get("source_reliability"),
        truth_status=TruthStatus(value["truth_status"]),
        calibrated_probability=value.get("calibrated_probability"),
        ranking_score=score,
    )


class PersistentSemanticUnitCandidateStore:
    """Append-only candidate stream backed by ZPCM and verified against M1."""

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
        self._last_sequence = memory.latest_domain_sequence(
            event_type=EVENT_TYPE, scope=scope,
        )

    def _verify_evidence(self, candidate: SemanticUnitCandidate) -> None:
        if candidate.envelope.scope != self.scope:
            raise SemanticUnitStoreError("candidate scope does not match the store scope")
        references = list(candidate.envelope.source_refs)
        for attribute in candidate.typed_attributes:
            references.extend(attribute.source_refs)
        for reference in references:
            self._resolver.resolve(reference)

    @staticmethod
    def _event_payload(candidate: SemanticUnitCandidate) -> tuple[dict[str, Any], str]:
        body = json.loads(canonical_json(candidate))
        body_digest = record_digest(candidate)
        return {
            "schema_version": EVENT_SCHEMA,
            "kind": "semantic_unit_candidate_recorded",
            "body": body,
            "body_digest": body_digest,
        }, body_digest

    def record_candidate(self, candidate: SemanticUnitCandidate) -> SemanticUnitReceipt:
        if not isinstance(candidate, SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock:
            self._verify_evidence(candidate)
            record_id = candidate.envelope.record_id
            event_id = f"m2:semantic-unit:{record_id}"
            payload, body_digest = self._event_payload(candidate)
            if body_digest != record_digest(candidate):
                raise SemanticUnitStoreError("canonical candidate digest changed during serialization")
            try:
                receipt = self._memory.append_domain_event(
                    event_type=EVENT_TYPE,
                    event_id=event_id,
                    scope=self.scope,
                    payload=payload,
                    expected_sequence=self._last_sequence,
                )
            except ZPCMError as exc:
                raise SemanticUnitStoreError(
                    "candidate record_id is immutable; use a new revision ID for changed content"
                ) from exc
            if not receipt["replayed"]:
                self._last_sequence = receipt["sequence"]
            return SemanticUnitReceipt(
                event_id=event_id,
                sequence=receipt["sequence"],
                payload_digest=receipt["payload_digest"],
                record_digest=body_digest,
                replayed=receipt["replayed"],
            )

    def iter_candidates(
        self, *, after_sequence: int = 0, page_size: int = 128,
    ) -> Iterator[SemanticUnitCandidate]:
        """Yield verified candidates using ZPCM's bounded keyset-paged reader."""
        try:
            events = self._memory.iter_domain_events(
                event_type=EVENT_TYPE,
                scope=self.scope,
                after_sequence=after_sequence,
                page_size=page_size,
            )
            for event in events:
                payload = event["payload"]
                if (payload.get("schema_version") != EVENT_SCHEMA
                        or payload.get("kind") != "semantic_unit_candidate_recorded"):
                    raise SemanticUnitStoreError("unsupported semantic candidate event schema/kind")
                body = payload.get("body")
                if not isinstance(body, dict):
                    raise SemanticUnitStoreError("semantic candidate event body must be an object")
                candidate = _candidate_from_dict(body)
                self._verify_evidence(candidate)
                body_digest = record_digest(candidate)
                if body_digest != payload.get("body_digest"):
                    raise SemanticUnitStoreError("semantic candidate record digest mismatch")
                expected_id = f"m2:semantic-unit:{candidate.envelope.record_id}"
                if event["event_id"] != expected_id:
                    raise SemanticUnitStoreError("semantic candidate event identity mismatch")
                yield candidate
        except (ZPCMError, ContractError, SemanticUnitStoreError):
            raise
        except Exception as exc:
            raise SemanticUnitStoreError(f"semantic candidate replay failed: {exc}") from exc
