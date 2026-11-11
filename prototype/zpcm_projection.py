"""ZPCM claim projection over the canonical E09 shared event store.

This module owns memory claim projections, not a second append-only event
ledger. Claim events are appended to SQLiteEvidenceStore under one memory
episode; event identity, idempotency and durability remain there.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from prototype.shared_evidence_protocol import SQLiteEvidenceStore


MEMORY_EPISODE = "zpcm-global"
PROJECTION_NAME = "zpcm-claims-v1"


class ZPCMProjectionError(ValueError):
    """Invalid memory claim projection operation."""


@dataclass(frozen=True)
class ZPCMAppendReceipt:
    event_id: str
    sequence_no: int
    payload_digest: str
    replayed: bool


@dataclass(frozen=True)
class ZPCMClaimRecord:
    claim_id: str
    subject: str
    predicate: str
    object_value: Any
    valid_from: int
    valid_until: int | None
    epistemic_status: str
    evidence_refs: tuple[str, ...]
    derivation_refs: tuple[str, ...]
    scope_conditions: tuple[str, ...]
    assertion_event_id: str
    assertion_sequence: int
    recorded_at: str
    retracted_event_id: str | None
    retraction_reason: str | None


@dataclass(frozen=True)
class ZPCMProjectionReport:
    start_sequence: int
    end_sequence: int
    applied_events: int
    remaining: bool


def _qualified_refs(values, name, *, required=False):
    if not isinstance(values, (tuple, list)):
        raise ZPCMProjectionError(f"{name} must be a sequence")
    result = tuple(values)
    if required and not result:
        raise ZPCMProjectionError(f"{name} must not be empty")
    if any(not isinstance(value, str) or "::" not in value or not all(value.split("::", 1)) for value in result):
        raise ZPCMProjectionError(f"{name} must contain qualified episode::event refs")
    if len(result) != len(set(result)):
        raise ZPCMProjectionError(f"{name} must be unique")
    return result


def append_claim(
    store: SQLiteEvidenceStore,
    *,
    event_id: str,
    claim_id: str,
    subject: str,
    predicate: str,
    object_value: Any,
    valid_from: int,
    evidence_refs,
    epistemic_status: str = "INFERRED",
    valid_until: int | None = None,
    derivation_refs=(),
    scope_conditions=(),
    episode_id: str = MEMORY_EPISODE,
) -> ZPCMAppendReceipt:
    refs = _qualified_refs(evidence_refs, "evidence_refs", required=True)
    derivations = _qualified_refs(derivation_refs, "derivation_refs")
    scopes = tuple(scope_conditions)
    if any(not isinstance(value, str) or not value.strip() for value in scopes) or len(scopes) != len(set(scopes)):
        raise ZPCMProjectionError("scope_conditions must be unique non-empty strings")
    receipt = store.append_event(
        episode_id=episode_id,
        event_id=event_id,
        event_type="memory_claim_asserted",
        payload={
            "claim_id": claim_id,
            "subject": subject,
            "predicate": predicate,
            "object": object_value,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "epistemic_status": epistemic_status,
            "evidence_refs": list(refs),
            "derivation_refs": list(derivations),
            "scope_conditions": list(scopes),
        },
        idempotency_key=event_id,
        actor_role="memory_writer",
        payload_schema="zpcm-memory-claim-asserted@1",
    )
    return ZPCMAppendReceipt(receipt.event_id, receipt.sequence_no, receipt.payload_digest, receipt.replayed)


def retract_claim(
    store: SQLiteEvidenceStore,
    *,
    event_id: str,
    claim_id: str,
    reason: str,
    episode_id: str = MEMORY_EPISODE,
) -> ZPCMAppendReceipt:
    receipt = store.append_event(
        episode_id=episode_id,
        event_id=event_id,
        event_type="memory_claim_retracted",
        payload={"claim_id": claim_id, "reason": reason},
        idempotency_key=event_id,
        actor_role="memory_writer",
        payload_schema="zpcm-memory-claim-retracted@1",
    )
    return ZPCMAppendReceipt(receipt.event_id, receipt.sequence_no, receipt.payload_digest, receipt.replayed)


class ZPCMClaimProjection:
    """Rebuildable claim index attached to the same SQLiteEvidenceStore database."""

    def __init__(self, store: SQLiteEvidenceStore, *, episode_id: str = MEMORY_EPISODE):
        if not isinstance(store, SQLiteEvidenceStore):
            raise TypeError("store must be the canonical SQLiteEvidenceStore")
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ValueError("episode_id must be non-empty")
        self.store = store
        self.episode_id = episode_id
        self.store.install_projection_schema("""
        CREATE TABLE IF NOT EXISTS zpcm_projection_cursors (
            episode_id TEXT NOT NULL,
            projection TEXT NOT NULL,
            last_sequence INTEGER NOT NULL,
            PRIMARY KEY (episode_id, projection)
        );
        CREATE TABLE IF NOT EXISTS zpcm_claims (
            episode_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            assertion_sequence INTEGER NOT NULL,
            assertion_event_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object_json TEXT NOT NULL,
            valid_from INTEGER NOT NULL,
            valid_until INTEGER,
            epistemic_status TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            derivation_refs_json TEXT NOT NULL,
            scope_conditions_json TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            retracted_sequence INTEGER,
            retracted_event_id TEXT,
            retraction_reason TEXT,
            PRIMARY KEY (episode_id, claim_id),
            FOREIGN KEY (episode_id, assertion_sequence)
              REFERENCES events(episode_id, sequence_no)
        );
        CREATE INDEX IF NOT EXISTS idx_zpcm_claim_subject_predicate
          ON zpcm_claims(episode_id, subject, predicate, assertion_sequence);
        CREATE INDEX IF NOT EXISTS idx_zpcm_claim_validity
          ON zpcm_claims(episode_id, valid_from, valid_until);
        """)
        with self.store.projection_transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO zpcm_projection_cursors(episode_id, projection, last_sequence) VALUES (?, ?, 0)",
                (self.episode_id, PROJECTION_NAME),
            )

    def _apply(self, db, row) -> None:
        event_type = row["event_type"]
        payload = json.loads(row["payload_json"])
        if event_type == "memory_claim_asserted":
            db.execute("""
                INSERT INTO zpcm_claims(
                    episode_id, claim_id, assertion_sequence, assertion_event_id,
                    subject, predicate, object_json, valid_from, valid_until,
                    epistemic_status, evidence_refs_json, derivation_refs_json,
                    scope_conditions_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.episode_id, payload["claim_id"], row["sequence_no"], row["event_id"],
                payload["subject"], payload["predicate"],
                json.dumps(payload["object"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False),
                payload["valid_from"], payload.get("valid_until"), payload["epistemic_status"],
                json.dumps(payload["evidence_refs"], ensure_ascii=False, separators=(",", ":")),
                json.dumps(payload.get("derivation_refs", []), ensure_ascii=False, separators=(",", ":")),
                json.dumps(payload.get("scope_conditions", []), ensure_ascii=False, separators=(",", ":")),
                row["created_at"],
            ))
        elif event_type == "memory_claim_retracted":
            cursor = db.execute("""
                UPDATE zpcm_claims SET retracted_sequence=?, retracted_event_id=?, retraction_reason=?
                WHERE episode_id=? AND claim_id=? AND retracted_sequence IS NULL
            """, (
                row["sequence_no"], row["event_id"], payload["reason"],
                self.episode_id, payload["claim_id"],
            ))
            if cursor.rowcount != 1:
                raise ZPCMProjectionError("retraction projection requires one active claim")

    def materialize(self, *, limit: int = 1000) -> ZPCMProjectionReport:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ZPCMProjectionError("limit must be a positive integer")
        with self.store.projection_transaction() as db:
            cursor_row = db.execute(
                "SELECT last_sequence FROM zpcm_projection_cursors WHERE episode_id=? AND projection=?",
                (self.episode_id, PROJECTION_NAME),
            ).fetchone()
            start = int(cursor_row["last_sequence"])
            rows = db.execute(
                "SELECT sequence_no,event_id,event_type,payload_json,created_at FROM events WHERE episode_id=? AND sequence_no>? ORDER BY sequence_no LIMIT ?",
                (self.episode_id, start, limit),
            ).fetchall()
            cursor = start
            for event in rows:
                self._apply(db, event)
                cursor = int(event["sequence_no"])
            db.execute(
                "UPDATE zpcm_projection_cursors SET last_sequence=? WHERE episode_id=? AND projection=?",
                (cursor, self.episode_id, PROJECTION_NAME),
            )
            remaining = db.execute(
                "SELECT 1 FROM events WHERE episode_id=? AND sequence_no>? LIMIT 1",
                (self.episode_id, cursor),
            ).fetchone() is not None
        return ZPCMProjectionReport(start, cursor, len(rows), remaining)

    def query_claims(
        self, *, subject: str | None = None, predicate: str | None = None,
        at_time: int | None = None, include_retracted: bool = False,
    ) -> tuple[ZPCMClaimRecord, ...]:
        clauses = ["episode_id=?"]
        args: list[Any] = [self.episode_id]
        if subject is not None:
            clauses.append("subject=?")
            args.append(subject)
        if predicate is not None:
            clauses.append("predicate=?")
            args.append(predicate)
        if not include_retracted:
            clauses.append("retracted_sequence IS NULL")
        if at_time is not None:
            if isinstance(at_time, bool) or not isinstance(at_time, int) or at_time < 0:
                raise ZPCMProjectionError("at_time must be a non-negative integer")
            clauses.append("valid_from<=? AND (valid_until IS NULL OR valid_until>=?)")
            args.extend((at_time, at_time))
        with self.store.projection_transaction() as db:
            rows = db.execute(
                "SELECT * FROM zpcm_claims WHERE " + " AND ".join(clauses) + " ORDER BY assertion_sequence, claim_id",
                args,
            ).fetchall()
        return tuple(ZPCMClaimRecord(
            claim_id=row["claim_id"], subject=row["subject"], predicate=row["predicate"],
            object_value=json.loads(row["object_json"]), valid_from=row["valid_from"],
            valid_until=row["valid_until"], epistemic_status=row["epistemic_status"],
            evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
            derivation_refs=tuple(json.loads(row["derivation_refs_json"])),
            scope_conditions=tuple(json.loads(row["scope_conditions_json"])),
            assertion_event_id=row["assertion_event_id"], assertion_sequence=row["assertion_sequence"],
            recorded_at=row["recorded_at"], retracted_event_id=row["retracted_event_id"],
            retraction_reason=row["retraction_reason"],
        ) for row in rows)

    @property
    def projection_sequence(self) -> int:
        with self.store.projection_transaction() as db:
            row = db.execute(
                "SELECT last_sequence FROM zpcm_projection_cursors WHERE episode_id=? AND projection=?",
                (self.episode_id, PROJECTION_NAME),
            ).fetchone()
            return int(row["last_sequence"])

    def rebuild_projection(self) -> ZPCMProjectionReport:
        with self.store.projection_transaction() as db:
            cursor_row = db.execute(
                "SELECT last_sequence FROM zpcm_projection_cursors WHERE episode_id=? AND projection=?",
                (self.episode_id, PROJECTION_NAME),
            ).fetchone()
            start = int(cursor_row["last_sequence"])
            db.execute("DELETE FROM zpcm_claims WHERE episode_id=?", (self.episode_id,))
            db.execute(
                "UPDATE zpcm_projection_cursors SET last_sequence=0 WHERE episode_id=? AND projection=?",
                (self.episode_id, PROJECTION_NAME),
            )
            rows = db.execute(
                "SELECT sequence_no,event_id,event_type,payload_json,created_at FROM events WHERE episode_id=? ORDER BY sequence_no",
                (self.episode_id,),
            ).fetchall()
            cursor = 0
            for event in rows:
                self._apply(db, event)
                cursor = int(event["sequence_no"])
            db.execute(
                "UPDATE zpcm_projection_cursors SET last_sequence=? WHERE episode_id=? AND projection=?",
                (cursor, self.episode_id, PROJECTION_NAME),
            )
        return ZPCMProjectionReport(start, cursor, len(rows), False)
