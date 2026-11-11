"""SQLite reference implementation of Zhouyi-AI's shared evidence protocol.

This is a single-process reference store, not a distributed event broker or a
security boundary between evaluator and learner processes.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROTOCOL_VERSION = "0.2"
STRICT_PROTOCOL_VERSION = "0.3"
EVIDENCE_SPLITS = {"SUPPORT", "GATE_DEV", "GATE_FINAL", "LOCKED_TEST"}
LEGACY_LEARNER_TRACK = "legacy"
EVENT_TYPES = {"observation", "prediction_commit", "evidence_reveal", "structure_version", "revision", "memory_claim_asserted", "memory_claim_retracted"}


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
        # SQLite's WAL-reset corruption bug is fixed in 3.51.3. Use rollback
        # journaling on older runtimes instead of silently relying on an
        # affected WAL implementation under multi-connection writes.
        requested_journal = "WAL" if sqlite3.sqlite_version_info >= (3, 51, 3) else "DELETE"
        mode_row = self._db.execute(f"PRAGMA journal_mode={requested_journal}").fetchone()
        self.journal_mode = str(mode_row[0]).upper()
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
        DROP INDEX IF EXISTS one_prediction_per_observation;
        DROP INDEX IF EXISTS one_prediction_per_observation_track;
        CREATE UNIQUE INDEX IF NOT EXISTS one_prediction_per_observation_track_v2
          ON events(episode_id, json_extract(payload_json, '$.observation_id'),
                    COALESCE(json_extract(payload_json, '$.learner_track'), 'legacy'))
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

    @staticmethod
    def _validate_scope_split(payload: dict[str, Any], event_name: str) -> None:
        if not isinstance(payload.get("scope"), str) or not payload["scope"].strip():
            raise ProtocolError(f"v0.3 {event_name} requires a non-empty scope")
        if payload.get("split") not in EVIDENCE_SPLITS:
            raise ProtocolError(f"v0.3 {event_name} has an invalid evidence split")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _validate_semantics(self, episode_id: str, event_type: str, payload: dict[str, Any], protocol_version: str) -> None:
        strict = protocol_version == STRICT_PROTOCOL_VERSION
        if event_type == "observation":
            if not payload.get("observation_id"):
                raise ProtocolError("observation requires observation_id")
            if strict:
                self._validate_scope_split(payload, "observation")
                if not payload.get("query_id"):
                    raise ProtocolError("v0.3 observation requires query_id")
        elif event_type == "prediction_commit":
            required = {"prediction_id", "observation_id", "model_version", "learner_track", "decision_status"}
            if strict:
                required |= {"query_id", "scope", "split", "interop_commit_digest"}
            if not required.issubset(payload):
                raise ProtocolError(f"prediction_commit missing fields: {sorted(required - payload.keys())}")
            if not isinstance(payload["learner_track"], str) or not payload["learner_track"].strip():
                raise ProtocolError("prediction_commit learner_track must be a non-empty string")
            if strict:
                digest = payload.get("interop_commit_digest")
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                    raise ProtocolError("v0.3 prediction_commit requires a lowercase SHA-256 interop_commit_digest")
            if payload["decision_status"] not in {
                "PREDICT", "ABSTAIN_AMBIGUOUS", "ABSTAIN_INCONSISTENT", "ABSTAIN_BUDGET"
            }:
                raise ProtocolError("invalid prediction decision_status")
            observation = self._db.execute(
                "SELECT payload_json, protocol_version FROM events WHERE episode_id=? AND event_type='observation' "
                "AND json_extract(payload_json, '$.observation_id')=?",
                (episode_id, payload["observation_id"]),
            ).fetchone()
            if observation is None:
                raise MissingReference("prediction commit requires a prior observation event")
            if strict:
                observed = json.loads(observation["payload_json"])
                if observation["protocol_version"] != STRICT_PROTOCOL_VERSION:
                    raise ProtocolError("v0.3 prediction cannot bind to a legacy observation")
                for field in ("query_id", "scope", "split"):
                    if payload.get(field) != observed.get(field):
                        raise ProtocolError(f"prediction_commit {field} does not match observation")
        elif event_type == "evidence_reveal":
            required = {"prediction_id", "learner_track", "target_or_feedback"}
            if strict:
                required |= {"query_id", "scope", "split", "commit_digest", "event_digest"}
            if not required.issubset(payload):
                raise ProtocolError(f"evidence_reveal missing fields: {sorted(required - payload.keys())}")
            if not isinstance(payload["learner_track"], str) or not payload["learner_track"].strip():
                raise ProtocolError("evidence_reveal learner_track must be a non-empty string")
            commit = self._db.execute(
                "SELECT payload_json, payload_digest, protocol_version FROM events WHERE episode_id=? AND event_type='prediction_commit' "
                "AND json_extract(payload_json, '$.prediction_id')=? "
                "AND COALESCE(json_extract(payload_json, '$.learner_track'), 'legacy')=?",
                (episode_id, payload["prediction_id"], payload["learner_track"]),
            ).fetchone()
            if commit is None:
                raise MissingReference("reveal requires a previously committed prediction from the same learner_track")
            if strict:
                committed = json.loads(commit["payload_json"])
                if commit["protocol_version"] != STRICT_PROTOCOL_VERSION:
                    raise ProtocolError("v0.3 reveal cannot bind to a legacy prediction")
                for field in ("query_id", "scope", "split"):
                    if payload.get(field) != committed.get(field):
                        raise ProtocolError(f"evidence_reveal {field} does not match prediction commit")
                if payload["commit_digest"] != committed.get("interop_commit_digest"):
                    raise ProtocolError("evidence_reveal commit_digest does not match CPG-EI semantic commit digest")
                if payload["event_digest"] != commit["payload_digest"]:
                    raise ProtocolError("evidence_reveal event_digest does not match durable event envelope digest")
        elif event_type == "memory_claim_asserted":
            required = {"claim_id", "subject", "predicate", "object", "valid_from", "epistemic_status", "evidence_refs"}
            if not required.issubset(payload):
                raise ProtocolError(f"memory_claim_asserted missing fields: {sorted(required - payload.keys())}")
            for field in ("claim_id", "subject", "predicate", "epistemic_status"):
                if not isinstance(payload[field], str) or not payload[field].strip():
                    raise ProtocolError(f"memory_claim_asserted {field} must be non-empty")
            valid_from = payload["valid_from"]
            if isinstance(valid_from, bool) or not isinstance(valid_from, int) or valid_from < 0:
                raise ProtocolError("memory_claim_asserted valid_from must be a non-negative integer")
            valid_until = payload.get("valid_until")
            if valid_until is not None and (isinstance(valid_until, bool) or not isinstance(valid_until, int) or valid_until < valid_from):
                raise ProtocolError("memory_claim_asserted valid_until must be >= valid_from")
            for name, refs, required_nonempty in (
                ("evidence_refs", payload["evidence_refs"], True),
                ("derivation_refs", payload.get("derivation_refs", []), False),
                ("scope_conditions", payload.get("scope_conditions", []), False),
            ):
                if not isinstance(refs, list) or (required_nonempty and not refs) or any(not isinstance(ref, str) or "::" not in ref for ref in refs) or len(refs) != len(set(refs)):
                    raise ProtocolError(f"memory_claim_asserted {name} must be a unique list of qualified event refs")
            for ref in payload["evidence_refs"]:
                source_episode, source_event = ref.split("::", 1)
                row = self._db.execute("SELECT event_type FROM events WHERE episode_id=? AND event_id=?", (source_episode, source_event)).fetchone()
                if row is None or row["event_type"] != "evidence_reveal":
                    raise MissingReference(f"claim evidence must reference a prior evidence_reveal: {ref}")
            for ref in payload.get("derivation_refs", []):
                source_episode, source_event = ref.split("::", 1)
                row = self._db.execute("SELECT event_type FROM events WHERE episode_id=? AND event_id=?", (source_episode, source_event)).fetchone()
                if row is None or row["event_type"] != "memory_claim_asserted":
                    raise MissingReference(f"claim derivation must reference a prior memory claim: {ref}")
            prior_claim = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='memory_claim_asserted' AND json_extract(payload_json, '$.claim_id')=?",
                (episode_id, payload["claim_id"]),
            ).fetchone()
            if prior_claim is not None:
                raise ProtocolError("claim_id is already asserted in this memory episode")
        elif event_type == "memory_claim_retracted":
            if not isinstance(payload.get("claim_id"), str) or not payload["claim_id"].strip() or not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
                raise ProtocolError("memory_claim_retracted requires claim_id and reason")
            prior_claim = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='memory_claim_asserted' AND json_extract(payload_json, '$.claim_id')=?",
                (episode_id, payload["claim_id"]),
            ).fetchone()
            prior_retraction = self._db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND event_type='memory_claim_retracted' AND json_extract(payload_json, '$.claim_id')=?",
                (episode_id, payload["claim_id"]),
            ).fetchone()
            if prior_claim is None or prior_retraction is not None:
                raise MissingReference("claim retraction requires one active prior assertion")
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
        integrity_metadata: dict[str, Any] | None = None, protocol_version: str = PROTOCOL_VERSION,
    ) -> EventReceipt:
        if not all(isinstance(x, str) and x for x in (episode_id, event_id, event_type, idempotency_key)):
            raise ProtocolError("episode_id, event_id, event_type and idempotency_key must be non-empty strings")
        if event_type not in EVENT_TYPES:
            raise ProtocolError(f"unsupported event_type: {event_type}")
        if protocol_version not in {PROTOCOL_VERSION, STRICT_PROTOCOL_VERSION}:
            raise ProtocolError(f"unsupported protocol_version: {protocol_version}")
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
            "event_type": event_type, "protocol_version": protocol_version,
            "payload_schema": payload_schema, "payload": payload,
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
                self._validate_semantics(episode_id, event_type, payload, protocol_version)
                seq = current + 1
                created_at = datetime.now(timezone.utc).isoformat()
                self._db.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (episode_id, seq, event_id, event_type, protocol_version, payload_json, fingerprint,
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

    @contextmanager
    def projection_transaction(self):
        """Run a derived projection transaction on this store's canonical DB."""
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def install_projection_schema(self, sql: str) -> None:
        """Install derived tables in the same database; never creates another event ledger."""
        if not isinstance(sql, str) or not sql.strip():
            raise ProtocolError("projection schema must be non-empty SQL")
        with self._lock:
            self._db.executescript(sql)

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
            payload = json.loads(item.pop("payload_json"))
            # v0.1 had a single implicit learner track. Preserve its immutable
            # bytes/digest while exposing it as the explicit legacy namespace.
            if item["protocol_version"] == "0.1" and item["event_type"] in {"prediction_commit", "evidence_reveal"}:
                payload.setdefault("learner_track", LEGACY_LEARNER_TRACK)
            item["payload"] = payload
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
