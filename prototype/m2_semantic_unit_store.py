"""Append-only M2 SemanticUnitCandidate lifecycle on the shared ZPCM event log.

Candidates are hypotheses/semantic extraction products, not world facts. Revisions
append a new immutable record linked to the previous record; retractions append a
tombstone event and never erase history.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from threading import RLock
from typing import Any

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.observation_contract import (
    ContractError, EpistemicStatus, EvidenceRef, GroundingStatus,
    RecordEnvelope, RoleBinding, Score, SemanticUnitCandidate,
    TruthStatus, TypedAttribute, UnitKind, canonical_json, record_digest,
)
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


EVENT_TYPE = "m2_semantic_unit"
EVENT_SCHEMA = "m2-semantic-unit-event-v1"


class SemanticUnitStoreError(RuntimeError):
    """A semantic-unit lifecycle event cannot be committed or replayed safely."""


@dataclass(frozen=True)
class SemanticUnitReceipt:
    event_id: str
    sequence: int
    payload_digest: str
    record_digest: str
    replayed: bool = False


def _candidate_from_dict(value: dict[str, Any]) -> SemanticUnitCandidate:
    env = dict(value["envelope"])
    env["source_refs"] = tuple(EvidenceRef(**x) for x in env["source_refs"])
    env["derivation_refs"] = tuple(env.get("derivation_refs", ()))
    envelope = RecordEnvelope(**env)
    attributes = tuple(
        TypedAttribute(
            name=x["name"], value_type=x["value_type"], value=x.get("value"),
            unit=x.get("unit"),
            source_refs=tuple(EvidenceRef(**r) for r in x.get("source_refs", ())),
        )
        for x in value.get("typed_attributes", ())
    )
    roles = tuple(RoleBinding(**x) for x in value.get("role_bindings", ()))
    score_value = value.get("ranking_score")
    return SemanticUnitCandidate(
        envelope=envelope,
        kind=UnitKind(value["kind"]),
        surface_forms=tuple(value["surface_forms"]),
        typed_attributes=attributes,
        role_bindings=roles,
        canonical_key=value.get("canonical_key"),
        grounding_status=GroundingStatus(value.get("grounding_status", "UNRESOLVED")),
        epistemic_status=EpistemicStatus(value.get("epistemic_status", "UNKNOWN")),
        extractor_confidence=value.get("extractor_confidence"),
        source_reliability=value.get("source_reliability"),
        truth_status=TruthStatus(value.get("truth_status", "UNKNOWN")),
        calibrated_probability=value.get("calibrated_probability"),
        ranking_score=Score(**score_value) if score_value is not None else None,
    )


class PersistentM2SemanticUnitStore:
    """Typed candidate history backed only by ZPCM memory_events."""

    def __init__(self, memory: ZPCMMemory, resolver: SQLiteEvidenceRefResolver, *,
                 scope: str, replay_page_size: int = 128):
        if not isinstance(memory, ZPCMMemory):
            raise TypeError("memory must be ZPCMMemory")
        if not isinstance(resolver, SQLiteEvidenceRefResolver):
            raise TypeError("resolver must be SQLiteEvidenceRefResolver")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be non-empty")
        if (isinstance(replay_page_size, bool) or not isinstance(replay_page_size, int)
                or not 1 <= replay_page_size <= 4096):
            raise ValueError("replay_page_size must be an integer in [1, 4096]")
        self._memory, self._resolver, self.scope = memory, resolver, scope
        self._replay_page_size = replay_page_size
        self._lock = RLock()
        self._versions: dict[str, SemanticUnitCandidate] = {}
        self._receipts: dict[str, SemanticUnitReceipt] = {}
        self._digests: dict[str, str] = {}
        self._event_kinds: dict[str, str] = {}
        self._predecessors: dict[str, str | None] = {}
        self._latest: dict[str, str] = {}
        self._retracted: dict[str, str] = {}
        self._last_sequence = 0
        self._restore()

    @property
    def candidates(self) -> dict[str, SemanticUnitCandidate]:
        with self._lock:
            return {root: self._versions[current] for root, current in self._latest.items()
                    if current not in self._retracted}

    @property
    def history(self) -> dict[str, SemanticUnitCandidate]:
        with self._lock:
            return dict(self._versions)

    @property
    def retractions(self) -> dict[str, str]:
        with self._lock:
            return dict(self._retracted)

    def _verify_candidate(self, candidate: SemanticUnitCandidate) -> None:
        if candidate.envelope.scope != self.scope:
            raise SemanticUnitStoreError("candidate scope does not match store scope")
        refs = list(candidate.envelope.source_refs)
        for attribute in candidate.typed_attributes:
            refs.extend(attribute.source_refs)
        # Validate every reference; duplicate refs are harmless but wasteful.
        seen = set()
        for ref in refs:
            key = (ref.document_id, ref.chunk_id, ref.content_sha256,
                   ref.byte_start, ref.byte_end, ref.source_version)
            if key not in seen:
                self._resolver.resolve(ref)
                seen.add(key)

    @staticmethod
    def _payload(kind: str, candidate: SemanticUnitCandidate, previous_id: str | None = None):
        body = json.loads(canonical_json(candidate))
        digest_value = record_digest(candidate)
        payload = {"schema_version": EVENT_SCHEMA, "kind": kind,
                   "body": body, "body_digest": digest_value}
        if previous_id is not None:
            payload["previous_record_id"] = previous_id
        return payload, digest_value

    def _restore(self) -> None:
        try:
            events = self._memory.iter_domain_events(
                event_type=EVENT_TYPE, scope=self.scope,
                page_size=self._replay_page_size,
            )
            versions, receipts, digests = {}, {}, {}
            event_kinds, predecessors = {}, {}
            latest, retracted = {}, {}
            previous_sequence = 0
            for event in events:
                seq = event["sequence"]
                if isinstance(seq, bool) or not isinstance(seq, int) or seq <= previous_sequence:
                    raise SemanticUnitStoreError("semantic-unit event sequence is not strictly increasing")
                previous_sequence = seq
                payload = event["payload"]
                if payload.get("schema_version") != EVENT_SCHEMA:
                    raise SemanticUnitStoreError("unsupported semantic-unit event schema")
                kind = payload.get("kind")
                event_id = event["event_id"]
                if kind in ("candidate_recorded", "candidate_revised"):
                    body = payload.get("body")
                    if not isinstance(body, dict):
                        raise SemanticUnitStoreError("candidate event body must be an object")
                    candidate = _candidate_from_dict(body)
                    self._verify_candidate(candidate)
                    rid = candidate.envelope.record_id
                    digest_value = record_digest(candidate)
                    if digest_value != payload.get("body_digest") or rid in versions:
                        raise SemanticUnitStoreError("candidate digest mismatch or duplicate record ID")
                    if kind == "candidate_recorded":
                        if event_id != f"m2:semantic-unit:{rid}" or rid in latest:
                            raise SemanticUnitStoreError("candidate event identity is inconsistent")
                        latest[rid] = rid
                    else:
                        prior = payload.get("previous_record_id")
                        if event_id != f"m2:semantic-unit:{rid}" or prior not in versions:
                            raise SemanticUnitStoreError("revision identity/predecessor is invalid")
                        root = next((r for r, current in latest.items() if current == prior), None)
                        if root is None or prior in retracted:
                            raise SemanticUnitStoreError("revision does not extend the current active version")
                        if candidate.envelope.derivation_refs.count(prior) != 1:
                            raise SemanticUnitStoreError("revision must cite its predecessor exactly once")
                        if candidate.envelope.scope != versions[prior].envelope.scope:
                            raise SemanticUnitStoreError("revision cannot cross scopes")
                        latest[root] = rid
                    versions[rid] = candidate
                    digests[rid] = digest_value
                    event_kinds[rid] = kind
                    predecessors[rid] = payload.get("previous_record_id") if kind == "candidate_revised" else None
                    receipts[rid] = SemanticUnitReceipt(
                        event_id, seq, event["payload_digest"], digest_value, True)
                elif kind == "candidate_retracted":
                    rid = payload.get("record_id")
                    reason = payload.get("reason")
                    if event_id != f"m2:semantic-unit:{rid}:retracted" or rid not in versions:
                        raise SemanticUnitStoreError("retraction identity/target is invalid")
                    if not isinstance(reason, str) or not reason.strip() or rid in retracted:
                        raise SemanticUnitStoreError("invalid or duplicate candidate retraction")
                    if rid not in latest.values():
                        raise SemanticUnitStoreError("only the current candidate version can be retracted")
                    retracted[rid] = reason
                else:
                    raise SemanticUnitStoreError("unknown semantic-unit event kind")
            self._versions, self._receipts, self._digests = versions, receipts, digests
            self._event_kinds, self._predecessors = event_kinds, predecessors
            self._latest, self._retracted = latest, retracted
            self._last_sequence = previous_sequence
        except (ZPCMError, ContractError, SemanticUnitStoreError):
            raise
        except Exception as exc:
            raise SemanticUnitStoreError(f"semantic-unit replay failed: {exc}") from exc

    def _append_candidate(self, candidate: SemanticUnitCandidate, *, previous_id: str | None):
        self._verify_candidate(candidate)
        rid = candidate.envelope.record_id
        digest_value = record_digest(candidate)
        if rid in self._versions:
            if self._digests[rid] != digest_value:
                raise SemanticUnitStoreError("candidate record_id is immutable")
            prior = self._receipts[rid]
            return SemanticUnitReceipt(prior.event_id, prior.sequence, prior.payload_digest,
                                       prior.record_digest, True)
        event_id = f"m2:semantic-unit:{rid}"
        kind = "candidate_revised" if previous_id is not None else "candidate_recorded"
        payload, body_digest = self._payload(kind, candidate, previous_id)
        if body_digest != digest_value:
            raise SemanticUnitStoreError("candidate digest changed during serialization")
        raw = self._memory.append_domain_event(
            event_type=EVENT_TYPE, event_id=event_id, scope=self.scope,
            payload=payload, expected_sequence=self._last_sequence)
        if raw["replayed"]:
            raise SemanticUnitStoreError("event exists outside restored adapter state; reconstruct before retry")
        receipt = SemanticUnitReceipt(event_id, raw["sequence"], raw["payload_digest"],
                                      digest_value, False)
        self._versions[rid] = candidate
        self._digests[rid] = digest_value
        self._event_kinds[rid] = kind
        self._predecessors[rid] = previous_id
        self._receipts[rid] = receipt
        self._last_sequence = receipt.sequence
        if previous_id is None:
            self._latest[rid] = rid
        else:
            root = next(root for root, current in self._latest.items() if current == previous_id)
            self._latest[root] = rid
        return receipt

    def record_candidate(self, candidate: SemanticUnitCandidate) -> SemanticUnitReceipt:
        if not isinstance(candidate, SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock:
            record_id = candidate.envelope.record_id
            if record_id in self._versions and self._event_kinds[record_id] != "candidate_recorded":
                raise SemanticUnitStoreError("record_candidate cannot replay a revision event")
            return self._append_candidate(candidate, previous_id=None)

    def revise_candidate(self, previous_record_id: str,
                         candidate: SemanticUnitCandidate) -> SemanticUnitReceipt:
        if not isinstance(previous_record_id, str) or not previous_record_id.strip():
            raise ValueError("previous_record_id must be non-empty")
        if not isinstance(candidate, SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock:
            # Retry after a committed revision remains idempotent even though
            # its predecessor is no longer the current version.
            candidate_id = candidate.envelope.record_id
            if candidate_id in self._versions:
                if (self._event_kinds[candidate_id] != "candidate_revised"
                        or self._predecessors[candidate_id] != previous_record_id
                        or self._digests[candidate_id] != record_digest(candidate)
                        or candidate.envelope.derivation_refs.count(previous_record_id) != 1):
                    raise SemanticUnitStoreError("candidate revision identity/predecessor is immutable")
                receipt = self._receipts[candidate_id]
                return SemanticUnitReceipt(receipt.event_id, receipt.sequence,
                    receipt.payload_digest, receipt.record_digest, True)
            if previous_record_id not in self._versions:
                raise SemanticUnitStoreError("revision predecessor does not exist")
            if previous_record_id in self._retracted or previous_record_id not in self._latest.values():
                raise SemanticUnitStoreError("only the current active candidate can be revised")
            if candidate.envelope.derivation_refs.count(previous_record_id) != 1:
                raise SemanticUnitStoreError("revision must cite predecessor exactly once in derivation_refs")
            if candidate.envelope.record_id == previous_record_id:
                raise SemanticUnitStoreError("revision requires a new immutable record_id")
            if candidate.envelope.scope != self.scope:
                raise SemanticUnitStoreError("revision cannot cross scopes")
            return self._append_candidate(candidate, previous_id=previous_record_id)

    def retract_candidate(self, record_id: str, *, reason: str) -> SemanticUnitReceipt:
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("record_id must be non-empty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be non-empty")
        with self._lock:
            if record_id not in self._versions or record_id not in self._latest.values():
                raise SemanticUnitStoreError("only the current candidate version can be retracted")
            if record_id in self._retracted:
                if self._retracted[record_id] != reason:
                    raise SemanticUnitStoreError("retraction reason conflicts with prior tombstone")
                prior = next(
                    (event for event in self._memory.iter_domain_events(
                        event_type=EVENT_TYPE, scope=self.scope,
                        page_size=self._replay_page_size,
                    ) if event["event_id"] == f"m2:semantic-unit:{record_id}:retracted"),
                    None,
                )
                if prior is None:
                    raise SemanticUnitStoreError("retraction receipt is missing from the event log")
                return SemanticUnitReceipt(prior["event_id"], prior["sequence"],
                    prior["payload_digest"], self._digests[record_id], True)
            event_id = f"m2:semantic-unit:{record_id}:retracted"
            payload = {"schema_version": EVENT_SCHEMA, "kind": "candidate_retracted",
                       "record_id": record_id, "reason": reason}
            raw = self._memory.append_domain_event(
                event_type=EVENT_TYPE, event_id=event_id, scope=self.scope,
                payload=payload, expected_sequence=self._last_sequence)
            if raw["replayed"]:
                raise SemanticUnitStoreError("retraction event exists outside restored adapter state")
            self._retracted[record_id] = reason
            self._last_sequence = raw["sequence"]
            return SemanticUnitReceipt(event_id, raw["sequence"], raw["payload_digest"],
                                       self._digests[record_id], False)
