"""Experimental v0.3 SQLite store layered on the stable v0.2 event format.

This first implementation slice adds atomic multi-event append, already-visible
TRAIN/SUPPORT ingestion, and typed E12 lifecycle-action records. It remains a
single-process reference store; it is not a distributed broker or a security
boundary between evaluator and learner processes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from prototype.shared_evidence_protocol import (
    EVENT_TYPES as V02_EVENT_TYPES,
    PROTOCOL_VERSION as V02_PROTOCOL_VERSION,
    EventReceipt,
    IdempotencyConflict,
    MissingReference,
    ProtocolError,
    SequenceConflict,
    SQLiteEvidenceStore,
    canonical_json,
    digest_payload,
)

PROTOCOL_VERSION = "0.3"
EVENT_TYPES = V02_EVENT_TYPES | {"evidence_ingest", "lifecycle_action"}
SPLIT_ROLES = {"support", "train", "gate_dev", "gate_final", "locked_test", "post_deploy"}
CHALLENGE_ROLES = {"locked_test", "post_deploy"}
SUPPORT_ROLES = {"support", "train", "gate_dev", "gate_final"}
ACTION_TYPES = {
    "propose", "request_discrimination", "train_support", "gate_validate",
    "reuse", "challenge", "revise", "specialize", "retire",
    "request_revalidation", "register_revision", "revalidate",
    "measure", "compose", "predict", "abstain",
}
CANDIDATE_STATES = {
    "observed", "proposed", "discrimination_pending", "train_supported",
    "gate_validated", "reused", "challenged", "revised", "specialized",
    "retired", "revalidation_pending",
}


class BatchConflict(ProtocolError):
    """A batch idempotency key was reused with different ordered content."""


def _fingerprint(spec: dict[str, Any]) -> str:
    return digest_payload({
        "event_type": spec["event_type"],
        "payload_schema": spec["payload_schema"],
        "payload": spec["payload"],
        "actor_role": spec["actor_role"],
        "causation_refs": spec["causation_refs"],
        "integrity_metadata": spec["integrity_metadata"],
    })


class SQLiteEvidenceStoreV03(SQLiteEvidenceStore):
    """v0.3 writer with v0.1/v0.2-compatible read/replay behavior."""

    def __init__(self, path):
        super().__init__(path)
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS batch_idempotency (
            episode_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            receipts_json TEXT NOT NULL,
            PRIMARY KEY (episode_id, idempotency_key)
        );
        """)

    def _event_by_id(self, episode_id: str, event_id: str):
        return self._db.execute(
            "SELECT * FROM events WHERE episode_id=? AND event_id=?",
            (episode_id, event_id),
        ).fetchone()

    def _event_by_payload_id(self, episode_id: str, event_type: str, field: str, value: str):
        return self._db.execute(
            "SELECT * FROM events WHERE episode_id=? AND event_type=? "
            "AND json_extract(payload_json, ?) = ?",
            (episode_id, event_type, "$." + field, value),
        ).fetchone()

    def _resolve_evidence_ref(self, episode_id: str, ref: Any):
        if isinstance(ref, dict):
            kind, value = ref.get("kind"), ref.get("id")
            if kind == "ingested":
                row = self._event_by_payload_id(episode_id, "evidence_ingest", "evidence_id", value)
            elif kind == "revealed":
                row = self._event_by_id(episode_id, value) if isinstance(value, str) else None
                if row is not None and row["event_type"] != "evidence_reveal":
                    row = None
            else:
                raise ProtocolError("typed evidence reference kind must be ingested or revealed")
            return row
        if not isinstance(ref, str) or not ref:
            raise ProtocolError("evidence reference must be a non-empty ID or typed reference")
        ingest = self._event_by_payload_id(episode_id, "evidence_ingest", "evidence_id", ref)
        reveal = self._event_by_id(episode_id, ref)
        if ingest is not None and reveal is not None:
            raise ProtocolError("ambiguous evidence ID; use a typed reference")
        if reveal is not None and reveal["event_type"] != "evidence_reveal":
            reveal = None
        return ingest or reveal

    def _validate_semantics(self, episode_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "evidence_ingest":
            required = {"evidence_id", "split_role", "outcome_ref", "source_provenance", "learner_track"}
            if not required.issubset(payload):
                raise ProtocolError(f"evidence_ingest missing fields: {sorted(required - payload.keys())}")
            if not isinstance(payload["evidence_id"], str) or not payload["evidence_id"].strip():
                raise ProtocolError("evidence_ingest evidence_id must be non-empty")
            if payload["split_role"] not in {"train", "support"}:
                raise ProtocolError("evidence_ingest is restricted to already-visible train/support evidence")
            if not isinstance(payload["learner_track"], str) or not payload["learner_track"].strip():
                raise ProtocolError("evidence_ingest learner_track must be non-empty")
            if not isinstance(payload["source_provenance"], dict) or not payload["source_provenance"]:
                raise ProtocolError("evidence_ingest requires source provenance")
            if not isinstance(payload["outcome_ref"], str) or not payload["outcome_ref"].strip():
                raise ProtocolError("evidence_ingest outcome_ref must be a non-empty immutable reference")
            if self._event_by_payload_id(episode_id, "evidence_ingest", "evidence_id", payload["evidence_id"]):
                raise ProtocolError("duplicate evidence_id in episode")
            observation_ref = payload.get("observation_ref")
            if observation_ref is not None:
                observation = self._event_by_id(episode_id, observation_ref)
                if observation is None or observation["event_type"] != "observation":
                    raise MissingReference("evidence_ingest observation_ref must reference a prior observation")
        elif event_type == "lifecycle_action":
            required = {
                "action_id", "action_type", "candidate_id", "candidate_version",
                "from_state", "to_state", "evidence_refs", "cost", "note",
                "candidate_lineage_refs", "learner_track",
            }
            if not required.issubset(payload):
                raise ProtocolError(f"lifecycle_action missing fields: {sorted(required - payload.keys())}")
            if not isinstance(payload["action_id"], str) or not payload["action_id"].strip():
                raise ProtocolError("lifecycle_action action_id must be non-empty")
            if payload["action_type"] not in ACTION_TYPES:
                raise ProtocolError("unknown E12-A6 ActionType wire value")
            from_state, to_state = payload["from_state"], payload["to_state"]
            if (from_state is None) != (to_state is None):
                raise ProtocolError("from_state and to_state must both be null or both be present")
            if from_state is not None and (from_state not in CANDIDATE_STATES or to_state not in CANDIDATE_STATES):
                raise ProtocolError("unknown E12-A6 CandidateState wire value")
            candidate_id, candidate_version = payload["candidate_id"], payload["candidate_version"]
            if (candidate_id is None) != (candidate_version is None):
                raise ProtocolError("candidate_id and candidate_version must be paired")
            if candidate_id is not None and (not isinstance(candidate_id, str) or not candidate_id.strip()):
                raise ProtocolError("candidate_id must be non-empty")
            if candidate_version is not None and (
                isinstance(candidate_version, bool) or not isinstance(candidate_version, int) or candidate_version < 1
            ):
                raise ProtocolError("candidate_version must be a positive integer")
            if not isinstance(payload["learner_track"], str) or not payload["learner_track"].strip():
                raise ProtocolError("lifecycle_action learner_track must be non-empty")
            if not isinstance(payload["evidence_refs"], list) or not isinstance(payload["candidate_lineage_refs"], list):
                raise ProtocolError("lifecycle_action evidence_refs and candidate_lineage_refs must be arrays")
            if isinstance(payload["cost"], bool) or not isinstance(payload["cost"], (int, float)) or payload["cost"] < 0:
                raise ProtocolError("lifecycle_action cost must be non-negative")
            if not isinstance(payload["note"], str):
                raise ProtocolError("lifecycle_action note must be a string")
            for ref in payload["evidence_refs"]:
                row = self._resolve_evidence_ref(episode_id, ref)
                if row is None:
                    raise MissingReference(f"lifecycle_action references unavailable evidence: {ref}")
                ref_track = json.loads(row["payload_json"]).get("learner_track")
                if ref_track and ref_track != payload["learner_track"]:
                    raise ProtocolError("lifecycle_action cannot cite evidence from another learner_track")
            # Reuse E12-A6's canonical transition table; do not fork its legal
            # transition semantics in the protocol layer.
            from prototype.e12a6_lifecycle_contract import ActionType, CandidateState, _TRANSITIONS
            action = ActionType(payload["action_type"])
            allowed = _TRANSITIONS.get(action, set())
            if allowed:
                if from_state is None:
                    raise ProtocolError("this E12-A6 action requires an explicit state transition")
                transition = (CandidateState(from_state), CandidateState(to_state))
                if transition not in allowed:
                    raise ProtocolError("transition is not permitted by the E12-A6 contract")
            elif from_state is not None:
                raise ProtocolError("non-transition E12-A6 action must not change candidate state")
            if candidate_id is not None and from_state is not None:
                latest = self._db.execute(
                    "SELECT payload_json FROM events WHERE episode_id=? AND event_type='lifecycle_action' "
                    "AND json_extract(payload_json, '$.candidate_id')=? "
                    "AND json_extract(payload_json, '$.candidate_version')=? "
                    "ORDER BY sequence_no DESC LIMIT 1",
                    (episode_id, candidate_id, candidate_version),
                ).fetchone()
                current_state = "observed" if latest is None else json.loads(latest["payload_json"])["to_state"]
                if current_state != from_state:
                    raise ProtocolError(f"stale lifecycle transition: current={current_state}, from={from_state}")
            duplicate = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='lifecycle_action' "
                "AND json_extract(payload_json, '$.action_id')=?",
                (episode_id, payload["action_id"]),
            ).fetchone()
            if duplicate:
                raise ProtocolError("duplicate lifecycle action_id")
            required_role = {
                "train_supported": {"train"},
                "gate_validated": {"gate_final"},
                "challenged": CHALLENGE_ROLES,
            }.get(to_state)
            if required_role:
                roles = set()
                for ref in payload["evidence_refs"]:
                    row = self._resolve_evidence_ref(episode_id, ref)
                    evidence_payload = json.loads(row["payload_json"])
                    if row["event_type"] == "evidence_ingest":
                        roles.add(evidence_payload["split_role"])
                    else:
                        roles.add(evidence_payload.get("split_role", "locked_test"))
                if not roles.intersection(required_role):
                    raise ProtocolError(f"{payload['to_state']} requires evidence role in {sorted(required_role)}")
        elif event_type == "structure_version":
            required = {"structure_id", "version_id", "kind", "definition", "parent_version_ids", "support_evidence_ids"}
            if not required.issubset(payload):
                raise ProtocolError(f"structure_version missing fields: {sorted(required - payload.keys())}")
            for parent_id in payload["parent_version_ids"]:
                if self._event_by_payload_id(episode_id, "structure_version", "version_id", parent_id) is None:
                    raise MissingReference(f"unknown parent structure version: {parent_id}")
            for evidence_ref in payload["support_evidence_ids"]:
                if self._resolve_evidence_ref(episode_id, evidence_ref) is None:
                    raise MissingReference(f"unknown support evidence reference: {evidence_ref}")
        else:
            super()._validate_semantics(episode_id, event_type, payload)

    def append_events(
        self,
        *,
        episode_id: str,
        events: Sequence[dict[str, Any]],
        idempotency_key: str,
        expected_sequence: int | None = None,
    ) -> tuple[EventReceipt, ...]:
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ProtocolError("episode_id must be non-empty")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ProtocolError("batch idempotency_key must be non-empty")
        if not isinstance(events, (list, tuple)) or not events:
            raise ProtocolError("events must be a non-empty ordered sequence")
        normalized = []
        event_ids = set()
        for index, raw in enumerate(events):
            if not isinstance(raw, dict):
                raise ProtocolError("each event spec must be an object")
            required = {"event_id", "event_type", "payload"}
            if not required.issubset(raw):
                raise ProtocolError(f"event spec missing fields: {sorted(required - raw.keys())}")
            event_id, event_type, payload = raw["event_id"], raw["event_type"], raw["payload"]
            if not all(isinstance(v, str) and v.strip() for v in (event_id, event_type)):
                raise ProtocolError("event_id and event_type must be non-empty")
            if event_id in event_ids:
                raise ProtocolError("duplicate event_id inside batch")
            event_ids.add(event_id)
            if event_type not in EVENT_TYPES:
                raise ProtocolError(f"unsupported v0.3 event_type: {event_type}")
            if not isinstance(payload, dict):
                raise ProtocolError("event payload must be an object")
            schema = raw.get("payload_schema") or f"{event_type}@1"
            if schema != f"{event_type}@1":
                raise ProtocolError(f"unsupported payload schema: {schema}")
            actor = raw.get("actor_role", "runner")
            if not isinstance(actor, str) or not actor.strip():
                raise ProtocolError("actor_role must be non-empty")
            causation = list(raw.get("causation_refs", ()))
            integrity = raw.get("integrity_metadata") or {}
            if not isinstance(integrity, dict):
                raise ProtocolError("integrity_metadata must be an object")
            spec = {
                "event_id": event_id, "event_type": event_type, "payload": payload,
                "payload_schema": schema, "actor_role": actor,
                "causation_refs": causation, "integrity_metadata": integrity,
                "idempotency_key": raw.get("idempotency_key", f"{idempotency_key}:{index}"),
            }
            if not isinstance(spec["idempotency_key"], str) or not spec["idempotency_key"].strip():
                raise ProtocolError("event idempotency_key must be non-empty")
            spec["fingerprint"] = _fingerprint(spec)
            normalized.append(spec)
        batch_digest = digest_payload([
            {k: spec[k] for k in ("event_id", "event_type", "payload", "payload_schema",
                                  "actor_role", "causation_refs", "integrity_metadata",
                                  "idempotency_key")}
            for spec in normalized
        ])
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                prior = self._db.execute(
                    "SELECT payload_digest, receipts_json FROM batch_idempotency "
                    "WHERE episode_id=? AND idempotency_key=?",
                    (episode_id, idempotency_key),
                ).fetchone()
                if prior:
                    if prior["payload_digest"] != batch_digest:
                        raise BatchConflict("batch idempotency key reused with different ordered content")
                    old = json.loads(prior["receipts_json"])
                    self._db.execute("COMMIT")
                    return tuple(EventReceipt(
                        episode_id, item["event_id"], item["sequence_no"],
                        item["payload_digest"], True,
                    ) for item in old)
                current = self._db.execute(
                    "SELECT COALESCE(MAX(sequence_no), 0) FROM events WHERE episode_id=?",
                    (episode_id,),
                ).fetchone()[0]
                if expected_sequence is not None and expected_sequence != current:
                    raise SequenceConflict(f"expected sequence {expected_sequence}, current sequence is {current}")
                receipts = []
                for offset, spec in enumerate(normalized, start=1):
                    existing = self._db.execute(
                        "SELECT payload_digest, event_id, sequence_no FROM idempotency "
                        "WHERE episode_id=? AND idempotency_key=?",
                        (episode_id, spec["idempotency_key"]),
                    ).fetchone()
                    if existing:
                        if existing["payload_digest"] != spec["fingerprint"]:
                            raise IdempotencyConflict("event idempotency key reused with different content")
                        raise ProtocolError("partial event-level retry is not accepted; retry the whole batch key")
                    self._validate_semantics(episode_id, spec["event_type"], spec["payload"])
                    sequence = current + offset
                    created_at = datetime.now(timezone.utc).isoformat()
                    payload_json = canonical_json(spec["payload"])
                    causation_json = canonical_json(spec["causation_refs"])
                    integrity_json = canonical_json(spec["integrity_metadata"])
                    self._db.execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (episode_id, sequence, spec["event_id"], spec["event_type"],
                         PROTOCOL_VERSION, payload_json, spec["fingerprint"], spec["actor_role"],
                         causation_json, spec["payload_schema"], integrity_json, created_at),
                    )
                    self._db.execute(
                        "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?)",
                        (episode_id, spec["idempotency_key"], spec["fingerprint"],
                         spec["event_id"], sequence),
                    )
                    receipts.append({
                        "event_id": spec["event_id"], "sequence_no": sequence,
                        "payload_digest": spec["fingerprint"],
                    })
                self._db.execute(
                    "INSERT INTO batch_idempotency VALUES (?, ?, ?, ?)",
                    (episode_id, idempotency_key, batch_digest, canonical_json(receipts)),
                )
                self._db.execute("COMMIT")
                return tuple(EventReceipt(
                    episode_id, item["event_id"], item["sequence_no"],
                    item["payload_digest"], False,
                ) for item in receipts)
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def append_event(
        self, *, episode_id: str, event_id: str, event_type: str, payload: dict[str, Any],
        idempotency_key: str, expected_sequence: int | None = None, actor_role: str = "runner",
        causation_refs: Iterable[str] = (), payload_schema: str | None = None,
        integrity_metadata: dict[str, Any] | None = None,
    ) -> EventReceipt:
        spec = {
            "event_id": event_id, "event_type": event_type, "payload": payload,
            "idempotency_key": idempotency_key, "actor_role": actor_role,
            "causation_refs": list(causation_refs),
            "payload_schema": payload_schema or f"{event_type}@1",
            "integrity_metadata": integrity_metadata or {},
        }
        return self.append_events(
            episode_id=episode_id, events=[spec],
            idempotency_key=f"single:{idempotency_key}",
            expected_sequence=expected_sequence,
        )[0]
