"""SQLite reference implementation of Zhouyi-AI's shared evidence protocol.

This is a single-process reference store, not a distributed event broker or a
security boundary between evaluator and learner processes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROTOCOL_VERSION = "0.1"
EVENT_TYPES = {"observation", "prediction_commit", "evidence_reveal", "structure_version", "revision"}


class ProtocolError(ValueError):
    """Base class for protocol invariant violations."""


class IdempotencyConflict(ProtocolError):
    """An idempotency key was reused with a different event payload."""


class SequenceConflict(ProtocolError):
    """The caller's expected sequence is stale."""


class MissingReference(ProtocolError):
    """An event references an unknown or not-yet-available event/version."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventReceipt:
    episode_id: str
    event_id: str
    sequence_no: int
    payload_digest: str
    replayed: bool = False


class SQLiteEvidenceStore:
    """Durable append-only episode store with transactional protocol checks.

    SQLite serializes writers using BEGIN IMMEDIATE. WAL plus synchronous=FULL
    provides a local durability baseline. The API is thread-safe within this
    process; it does not claim multi-host consensus or source authentication.
    """

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            episode_id TEXT NOT NULL,
            sequence_no INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            protocol_version TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            causation_refs_json TEXT NOT NULL,
            payload_schema TEXT NOT NULL,
            integrity_metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (episode_id, sequence_no),
            UNIQUE (episode_id, event_id)
        );
        CREATE TABLE IF NOT EXISTS idempotency (
            episode_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            event_id TEXT NOT NULL,
            sequence_no INTEGER NOT NULL,
            PRIMARY KEY (episode_id, idempotency_key),
            FOREIGN KEY (episode_id, sequence_no)
              REFERENCES events(episode_id, sequence_no)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_observation_id
          ON events(episode_id, json_extract(payload_json, '$.observation_id'))
          WHERE event_type='observation';
        CREATE UNIQUE INDEX IF NOT EXISTS one_prediction_per_observation
          ON events(episode_id, json_extract(payload_json, '$.observation_id'))
          WHERE event_type='prediction_commit';
        CREATE UNIQUE INDEX IF NOT EXISTS one_prediction_id
          ON events(episode_id, json_extract(payload_json, '$.prediction_id'))
          WHERE event_type='prediction_commit';
        CREATE UNIQUE INDEX IF NOT EXISTS one_reveal_per_prediction
          ON events(episode_id, json_extract(payload_json, '$.prediction_id'))
          WHERE event_type='evidence_reveal';
        CREATE UNIQUE INDEX IF NOT EXISTS one_structure_version_id
          ON events(episode_id, json_extract(payload_json, '$.version_id'))
          WHERE event_type='structure_version';
        """)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _validate_semantics(self, episode_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "observation":
            if not payload.get("observation_id"):
                raise ProtocolError("observation requires observation_id")
        elif event_type == "prediction_commit":
            required = {"prediction_id", "observation_id", "model_version", "decision_status"}
            if not required.issubset(payload):
                raise ProtocolError(f"prediction_commit missing fields: {sorted(required - payload.keys())}")
            if payload["decision_status"] not in {
                "PREDICT", "ABSTAIN_AMBIGUOUS", "ABSTAIN_INCONSISTENT", "ABSTAIN_BUDGET"
            }:
                raise ProtocolError("invalid prediction decision_status")
            observation = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='observation' "
                "AND json_extract(payload_json, '$.observation_id')=?",
                (episode_id, payload["observation_id"]),
            ).fetchone()
            if observation is None:
                raise MissingReference("prediction commit requires a prior observation event")
        elif event_type == "evidence_reveal":
            if not {"prediction_id", "target_or_feedback"}.issubset(payload):
                raise ProtocolError("evidence_reveal requires prediction_id and target_or_feedback")
            commit = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='prediction_commit' "
                "AND json_extract(payload_json, '$.prediction_id')=?",
                (episode_id, payload["prediction_id"]),
            ).fetchone()
            if commit is None:
                raise MissingReference("reveal requires a previously committed prediction")
        elif event_type == "structure_version":
            required = {"structure_id", "version_id", "kind", "definition", "parent_version_ids", "support_evidence_ids"}
            if not required.issubset(payload):
                raise ProtocolError(f"structure_version missing fields: {sorted(required - payload.keys())}")
            for parent_id in payload["parent_version_ids"]:
                parent = self._db.execute(
                    "SELECT 1 FROM events WHERE episode_id=? AND event_type='structure_version' "
                    "AND json_extract(payload_json, '$.version_id')=?",
                    (episode_id, parent_id),
                ).fetchone()
                if parent is None:
                    raise MissingReference(f"unknown parent structure version: {parent_id}")
            for evidence_id in payload["support_evidence_ids"]:
                reveal = self._db.execute(
                    "SELECT 1 FROM events WHERE episode_id=? AND event_type='evidence_reveal' AND event_id=?",
                    (episode_id, evidence_id),
                ).fetchone()
                if reveal is None:
                    raise MissingReference(f"support evidence is not a prior reveal event: {evidence_id}")
        elif event_type == "revision":
            required = {"revision_id", "operation", "trigger_evidence_ids", "before_version_ids", "after_version_ids"}
            if not required.issubset(payload):
                raise ProtocolError("revision missing required fields")
            for evidence_id in payload["trigger_evidence_ids"]:
                reveal = self._db.execute(
                    "SELECT 1 FROM events WHERE episode_id=? AND event_type='evidence_reveal' AND event_id=?",
                    (episode_id, evidence_id),
                ).fetchone()
                if reveal is None:
                    raise MissingReference(f"revision cites unrevealed evidence: {evidence_id}")
            for version_id in list(payload["before_version_ids"]) + list(payload["after_version_ids"]):
                version = self._db.execute(
                    "SELECT 1 FROM events WHERE episode_id=? AND event_type='structure_version' "
                    "AND json_extract(payload_json, '$.version_id')=?",
                    (episode_id, version_id),
                ).fetchone()
                if version is None:
                    raise MissingReference(f"revision cites unknown structure version: {version_id}")

    def append_event(
        self, *, episode_id: str, event_id: str, event_type: str, payload: dict[str, Any],
        idempotency_key: str, expected_sequence: int | None = None, actor_role: str = "runner",
        causation_refs: Iterable[str] = (), payload_schema: str | None = None,
        integrity_metadata: dict[str, Any] | None = None,
    ) -> EventReceipt:
        if not all(isinstance(x, str) and x for x in (episode_id, event_id, event_type, idempotency_key)):
            raise ProtocolError("episode_id, event_id, event_type and idempotency_key must be non-empty strings")
        if event_type not in EVENT_TYPES:
            raise ProtocolError(f"unsupported event_type: {event_type}")
        if not isinstance(payload, dict):
            raise ProtocolError("payload must be an object")
        payload_json = canonical_json(payload)
        payload_schema = payload_schema or f"{event_type}@1"
        causation_refs_json = canonical_json(list(causation_refs))
        integrity_metadata_json = canonical_json(integrity_metadata or {})
        if not actor_role or not payload_schema:
            raise ProtocolError("actor_role and payload_schema must be non-empty")
        # Include event type and schema in the idempotency fingerprint.
        fingerprint = digest_payload({
            "event_type": event_type, "payload_schema": payload_schema, "payload": payload,
            "actor_role": actor_role, "causation_refs": json.loads(causation_refs_json),
            "integrity_metadata": json.loads(integrity_metadata_json),
        })
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                prior = self._db.execute(
                    "SELECT i.payload_digest, e.event_id, e.sequence_no FROM idempotency i "
                    "JOIN events e USING(episode_id, sequence_no) WHERE i.episode_id=? AND i.idempotency_key=?",
                    (episode_id, idempotency_key),
                ).fetchone()
                if prior:
                    if prior["payload_digest"] != fingerprint:
                        raise IdempotencyConflict("idempotency key reused with different event content")
                    self._db.execute("COMMIT")
                    return EventReceipt(episode_id, prior["event_id"], prior["sequence_no"], fingerprint, True)

                current = self._db.execute(
                    "SELECT COALESCE(MAX(sequence_no), 0) FROM events WHERE episode_id=?", (episode_id,)
                ).fetchone()[0]
                if expected_sequence is not None and expected_sequence != current:
                    raise SequenceConflict(f"expected sequence {expected_sequence}, current sequence is {current}")
                self._validate_semantics(episode_id, event_type, payload)
                seq = current + 1
                created_at = datetime.now(timezone.utc).isoformat()
                self._db.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (episode_id, seq, event_id, event_type, PROTOCOL_VERSION, payload_json, fingerprint,
                     actor_role, causation_refs_json, payload_schema, integrity_metadata_json, created_at),
                )
                self._db.execute(
                    "INSERT INTO idempotency VALUES (?, ?, ?, ?, ?)",
                    (episode_id, idempotency_key, fingerprint, event_id, seq),
                )
                self._db.execute("COMMIT")
                return EventReceipt(episode_id, event_id, seq, fingerprint, False)
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def commit_prediction(self, **kwargs: Any) -> EventReceipt:
        return self.append_event(event_type="prediction_commit", **kwargs)

    def reveal_evidence(self, **kwargs: Any) -> EventReceipt:
        return self.append_event(event_type="evidence_reveal", **kwargs)

    def append_revision(self, **kwargs: Any) -> EventReceipt:
        return self.append_event(event_type="revision", **kwargs)

    def replay_episode(self, episode_id: str, from_sequence: int = 1) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT episode_id, sequence_no, event_id, event_type, protocol_version, payload_json, "
                "payload_digest, actor_role, causation_refs_json, payload_schema, integrity_metadata_json, created_at "
                "FROM events WHERE episode_id=? AND sequence_no>=? ORDER BY sequence_no",
                (episode_id, from_sequence),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            item["causation_refs"] = json.loads(item.pop("causation_refs_json"))
            item["integrity_metadata"] = json.loads(item.pop("integrity_metadata_json"))
            result.append(item)
        return result

    def snapshot_structure(self, episode_id: str, version_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM events WHERE episode_id=? AND event_type='structure_version' "
                "AND json_extract(payload_json, '$.version_id')=?",
                (episode_id, version_id),
            ).fetchone()
        if row is None:
            raise MissingReference(f"unknown structure version: {version_id}")
        return {
            "episode_id": episode_id, "sequence_no": row["sequence_no"], "event_id": row["event_id"],
            "payload": json.loads(row["payload_json"]), "payload_digest": row["payload_digest"],
        }
