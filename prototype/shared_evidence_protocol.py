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

PROTOCOL_VERSION = "0.2"
STRICT_PROTOCOL_VERSION = "0.3"
DOMAIN_BOUND_PROTOCOL_VERSION = "0.4"
DOMAIN_FIELDS = ("domain_id", "world_family", "domain_registry_id", "domain_registry_version")
EVIDENCE_SPLITS = {"SUPPORT", "GATE_DEV", "GATE_FINAL", "LOCKED_TEST"}
LEGACY_LEARNER_TRACK = "legacy"
EVENT_TYPES = {"observation", "prediction_commit", "evidence_reveal", "structure_version", "revision", "branch_merge_authorization"}


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
        CREATE TABLE IF NOT EXISTS payload_vault (
            payload_ref TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            payload_digest TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
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

    def put_payload(self, payload_ref: str, payload: Any) -> bool:
        """Persist immutable observation input by its canonical content digest."""
        if not isinstance(payload_ref, str) or payload_ref != digest_payload(payload):
            raise ProtocolError("payload_ref must equal the canonical payload digest")
        raw = canonical_json(payload)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT payload_digest FROM payload_vault WHERE payload_ref=?",
                    (payload_ref,),
                ).fetchone()
                if row is not None:
                    if row["payload_digest"] != payload_ref:
                        raise IdempotencyConflict("payload reference content mismatch")
                    self._db.execute("COMMIT")
                    return False
                self._db.execute(
                    "INSERT INTO payload_vault(payload_ref,payload_json,payload_digest,created_at) VALUES(?,?,?,?)",
                    (payload_ref, raw, payload_ref, datetime.now(timezone.utc).isoformat()),
                )
                self._db.execute("COMMIT")
                return True
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def get_payload(self, payload_ref: str) -> Any:
        """Load and re-verify a previously persisted immutable payload."""
        with self._lock:
            row = self._db.execute(
                "SELECT payload_json,payload_digest FROM payload_vault WHERE payload_ref=?",
                (payload_ref,),
            ).fetchone()
        if row is None:
            raise MissingReference(f"unknown payload reference: {payload_ref}")
        payload = json.loads(row["payload_json"])
        if row["payload_digest"] != payload_ref or digest_payload(payload) != payload_ref:
            raise ProtocolError("payload vault digest verification failed")
        return payload


    @staticmethod
    def _validate_v04_envelope(
        event_type: str, payload: dict[str, Any], payload_schema: str,
        actor_role: str, integrity_metadata: dict[str, Any],
    ) -> None:
        schemas = {
            "observation": (
                "observation@4", "observer",
                {"observation_id", "query_id", "scope", "split", *DOMAIN_FIELDS},
            ),
            "prediction_commit": (
                "prediction_commit@4", "learner",
                {"prediction_id", "observation_id", "model_version", "learner_track",
                 "decision_status", "query_id", "scope", "split", "interop_commit_digest",
                 *DOMAIN_FIELDS},
            ),
            "evidence_reveal": (
                "evidence_reveal@4", "evaluator",
                {"prediction_id", "learner_track", "target_or_feedback", "query_id",
                 "scope", "split", "commit_digest", "event_digest", *DOMAIN_FIELDS},
            ),
        }
        contract = schemas.get(event_type)
        if contract is None:
            raise ProtocolError("E09 v0.4 supports only observation, prediction_commit and evidence_reveal")
        expected_schema, expected_role, expected_fields = contract
        if payload_schema != expected_schema:
            raise ProtocolError(f"E09 v0.4 {event_type} requires payload_schema={expected_schema}")
        if set(payload) != expected_fields:
            missing, unknown = expected_fields - set(payload), set(payload) - expected_fields
            raise ProtocolError(
                f"E09 v0.4 {event_type} closed schema mismatch; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        if actor_role != expected_role:
            raise ProtocolError(f"E09 v0.4 {event_type} requires actor_role={expected_role}")
        if not isinstance(integrity_metadata, dict) or set(integrity_metadata) != {"authenticated_workload"}:
            raise ProtocolError("E09 v0.4 requires authenticated workload integrity metadata")
        identity = integrity_metadata.get("authenticated_workload")
        identity_fields = {
            "workload_id", "issuer_id", "identity_provider",
            "authentication_method", "credential_fingerprint",
        }
        if not isinstance(identity, dict) or set(identity) != identity_fields:
            raise ProtocolError("E09 v0.4 authenticated workload metadata is malformed")
        if any(not isinstance(value, str) or not value.strip() for value in identity.values()):
            raise ProtocolError("E09 v0.4 authenticated workload metadata must be non-empty strings")
        for field in DOMAIN_FIELDS:
            if not isinstance(payload[field], str) or not payload[field].strip():
                raise ProtocolError(f"E09 v0.4 {event_type} requires non-empty {field}")

    def _validate_semantics(self, episode_id: str, event_type: str, payload: dict[str, Any], protocol_version: str) -> None:
        strict = protocol_version in (STRICT_PROTOCOL_VERSION, DOMAIN_BOUND_PROTOCOL_VERSION)
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
                if observation["protocol_version"] != protocol_version:
                    raise ProtocolError("prediction commit cannot bind to an observation from another protocol version")
                for field in ("query_id", "scope", "split"):
                    if payload.get(field) != observed.get(field):
                        raise ProtocolError(f"prediction_commit {field} does not match observation")
                if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION:
                    for field in DOMAIN_FIELDS:
                        if payload.get(field) != observed.get(field):
                            raise ProtocolError(f"prediction_commit {field} does not match trusted observation")
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
                if commit["protocol_version"] != protocol_version:
                    raise ProtocolError("evidence reveal cannot bind to a prediction from another protocol version")
                for field in ("query_id", "scope", "split"):
                    if payload.get(field) != committed.get(field):
                        raise ProtocolError(f"evidence_reveal {field} does not match prediction commit")
                if payload["commit_digest"] != committed.get("interop_commit_digest"):
                    raise ProtocolError("evidence_reveal commit_digest does not match CPG-EI semantic commit digest")
                if payload["event_digest"] != commit["payload_digest"]:
                    raise ProtocolError("evidence_reveal event_digest does not match durable event envelope digest")
                if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION:
                    for field in DOMAIN_FIELDS:
                        if payload.get(field) != committed.get(field):
                            raise ProtocolError(f"evidence_reveal {field} does not match trusted prediction commit")
        elif event_type == "branch_merge_authorization":
            required = {
                "authorization_id", "issuer_id", "scope", "parent_state_ref",
                "branch_ids", "evidence_refs", "issued_at", "expires_at",
                "signature_algorithm", "signature_version", "audience",
                "authorization_sequence", "signature",
            }
            if not strict:
                raise ProtocolError("branch merge authorization requires strict E09 v0.3")
            if not required.issubset(payload):
                raise ProtocolError(
                    f"branch_merge_authorization missing fields: {sorted(required - payload.keys())}"
                )
            if payload["signature_algorithm"] != "Ed25519":
                raise ProtocolError("branch_merge_authorization requires Ed25519")
            if payload["signature_version"] != "E09-AUTHZ-SIG-V2":
                raise ProtocolError("branch_merge_authorization requires E09-AUTHZ-SIG-V2")
            if payload["audience"] != "e12a6-lifecycle":
                raise ProtocolError("branch_merge_authorization audience is invalid")
            current_sequence = self._db.execute(
                "SELECT COALESCE(MAX(sequence_no), 0) FROM events WHERE episode_id=?",
                (episode_id,),
            ).fetchone()[0]
            sequence = payload["authorization_sequence"]
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence != current_sequence + 1:
                raise ProtocolError("authorization_sequence must equal the next durable event sequence")
            for field in ("authorization_id", "issuer_id", "scope", "parent_state_ref",
                          "signature_algorithm", "signature"):
                if not isinstance(payload[field], str) or not payload[field].strip():
                    raise ProtocolError(f"branch_merge_authorization {field} must be non-empty")
            for field in ("branch_ids", "evidence_refs"):
                values = payload[field]
                if (not isinstance(values, list) or not values
                        or any(not isinstance(value, str) or not value.strip() for value in values)
                        or len(values) != len(set(values))):
                    raise ProtocolError(f"branch_merge_authorization {field} must be a non-empty unique string list")
            for field in ("issued_at", "expires_at"):
                if not isinstance(payload[field], str) or not payload[field].strip():
                    raise ProtocolError(f"branch_merge_authorization {field} must be an ISO timestamp")
                try:
                    parsed = datetime.fromisoformat(payload[field].replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ProtocolError(f"branch_merge_authorization {field} is invalid") from exc
                if parsed.tzinfo is None:
                    raise ProtocolError(f"branch_merge_authorization {field} must include a timezone")
            issued = datetime.fromisoformat(payload["issued_at"].replace("Z", "+00:00"))
            expires = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
            if expires <= issued:
                raise ProtocolError("branch merge authorization must expire after issue time")
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
        if protocol_version not in {PROTOCOL_VERSION, STRICT_PROTOCOL_VERSION, DOMAIN_BOUND_PROTOCOL_VERSION}:
            raise ProtocolError(f"unsupported protocol_version: {protocol_version}")
        if not isinstance(payload, dict):
            raise ProtocolError("payload must be an object")
        payload_json = canonical_json(payload)
        payload_schema = payload_schema or f"{event_type}@1"
        causation_refs_json = canonical_json(list(causation_refs))
        integrity_metadata_json = canonical_json(integrity_metadata or {})
        if not actor_role or not payload_schema:
            raise ProtocolError("actor_role and payload_schema must be non-empty")
        if event_type == "branch_merge_authorization" and actor_role != "authorizer":
            raise ProtocolError("branch_merge_authorization must be appended by the authorizer role")
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
                if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION:
                    self._validate_v04_envelope(
                        event_type, payload, payload_schema, actor_role,
                        json.loads(integrity_metadata_json),
                    )
                self._validate_semantics(episode_id, event_type, payload, protocol_version)
                if protocol_version == DOMAIN_BOUND_PROTOCOL_VERSION:
                    causations = json.loads(causation_refs_json)
                    if event_type == "prediction_commit":
                        prior = self._db.execute(
                            "SELECT event_id FROM events WHERE episode_id=? AND event_type='observation' "
                            "AND json_extract(payload_json, '$.observation_id')=?",
                            (episode_id, payload["observation_id"]),
                        ).fetchone()
                        if prior is None or prior["event_id"] not in causations:
                            raise ProtocolError("v0.4 prediction_commit must cite its observation event")
                    elif event_type == "evidence_reveal":
                        prior = self._db.execute(
                            "SELECT event_id FROM events WHERE episode_id=? AND event_type='prediction_commit' "
                            "AND json_extract(payload_json, '$.prediction_id')=? "
                            "AND json_extract(payload_json, '$.learner_track')=?",
                            (episode_id, payload["prediction_id"], payload["learner_track"]),
                        ).fetchone()
                        if prior is None or prior["event_id"] not in causations:
                            raise ProtocolError("v0.4 evidence_reveal must cite its prediction commit event")
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
