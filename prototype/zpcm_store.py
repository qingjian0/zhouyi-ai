"""ZPCM N0.1: deterministic SQLite event ledger and claim materializer.

This is a storage/reference prototype, not a neural memory model or a
mobile-performance result. Events are immutable; projections are rebuildable.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping


class ZPCMError(ValueError):
    """Base error for invalid ZPCM operations."""


class EventConflictError(ZPCMError):
    """An event ID was reused with a different canonical payload."""


class MaterializationError(ZPCMError):
    """A ledger event could not be applied to the selected projection."""


@dataclass(frozen=True)
class AppendReceipt:
    seq: int
    event_id: str
    duplicate: bool
    event_hash: str


@dataclass(frozen=True)
class MaterializeReport:
    start_seq: int
    end_seq: int
    applied: int
    remaining: bool


@dataclass(frozen=True)
class ClaimRecord:
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
    assertion_seq: int
    retracted_seq: int | None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ZPCMError(f"{field} must be a non-empty string")
    return value


def _require_timestamp(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ZPCMError(f"{field} must be a non-negative integer timestamp")
    return value


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ZPCMError(f"{field} must be a list")
    result = [_require_text(item, f"{field}[]") for item in value]
    if len(result) != len(set(result)):
        raise ZPCMError(f"{field} must not contain duplicates")
    if not allow_empty and not result:
        raise ZPCMError(f"{field} must not be empty")
    return result


class ZPCMStore:
    """Append-only event ledger with deterministic, transactional projections.

    Event append and projection materialization are deliberately separate.
    A process may stop after append; materialize() resumes from the committed
    projection cursor. A failed batch rolls back as a whole and never advances
    the cursor beyond the last successfully committed event.
    """

    PROJECTION = "claims-v1"

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, isolation_level=None,
                                   check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 5000")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._create_schema()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "ZPCMStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _create_schema(self) -> None:
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            observed_at INTEGER NOT NULL,
            recorded_at INTEGER NOT NULL,
            source_refs_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            canonical_json TEXT NOT NULL,
            event_hash TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_type_seq
            ON events(event_type, seq);
        CREATE INDEX IF NOT EXISTS idx_events_observed
            ON events(observed_at, seq);

        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            assertion_seq INTEGER NOT NULL REFERENCES events(seq),
            event_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object_json TEXT NOT NULL,
            valid_from INTEGER NOT NULL,
            valid_until INTEGER,
            epistemic_status TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            derivation_refs_json TEXT NOT NULL,
            scope_conditions_json TEXT NOT NULL,
            retracted_seq INTEGER REFERENCES events(seq),
            retraction_reason TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_claim_subject_predicate
            ON claims(subject, predicate, assertion_seq);
        CREATE INDEX IF NOT EXISTS idx_claim_validity
            ON claims(valid_from, valid_until);
        CREATE INDEX IF NOT EXISTS idx_claim_active
            ON claims(retracted_seq, subject, predicate);

        CREATE TABLE IF NOT EXISTS projection_cursors (
            projection TEXT PRIMARY KEY,
            last_seq INTEGER NOT NULL
        );
        INSERT OR IGNORE INTO projection_cursors(projection, last_seq)
            VALUES ('claims-v1', 0);
        CREATE TRIGGER IF NOT EXISTS events_no_update
            BEFORE UPDATE ON events BEGIN
            SELECT RAISE(ABORT, 'event ledger is append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS events_no_delete
            BEFORE DELETE ON events BEGIN
            SELECT RAISE(ABORT, 'event ledger is append-only');
        END;
        """)

    @staticmethod
    def _normalize_event(event: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(event, Mapping):
            raise ZPCMError("event must be a mapping")
        required = ("event_id", "event_type", "schema_version",
                    "observed_at", "recorded_at", "payload")
        missing = [key for key in required if key not in event]
        if missing:
            raise ZPCMError(f"missing event fields: {', '.join(missing)}")
        event_id = _require_text(event["event_id"], "event_id")
        event_type = _require_text(event["event_type"], "event_type")
        schema_version = event["schema_version"]
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
            raise ZPCMError("schema_version must be a positive integer")
        observed_at = _require_timestamp(event["observed_at"], "observed_at")
        recorded_at = _require_timestamp(event["recorded_at"], "recorded_at")
        payload = event["payload"]
        if not isinstance(payload, Mapping):
            raise ZPCMError("payload must be a mapping")
        source_refs = _string_list(event.get("source_refs", []), "source_refs")
        return {
            "event_id": event_id,
            "event_type": event_type,
            "schema_version": schema_version,
            "observed_at": observed_at,
            "recorded_at": recorded_at,
            "source_refs": source_refs,
            "payload": dict(payload),
        }

    def append_event(self, event: Mapping[str, Any]) -> AppendReceipt:
        normalized = self._normalize_event(event)
        encoded = _canonical_json(normalized)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            existing = self._db.execute("SELECT seq, event_hash FROM events WHERE event_id = ?", (normalized["event_id"],)).fetchone()
            if existing:
                if existing["event_hash"] != digest:
                    raise EventConflictError("event_id already exists with a different payload")
                receipt = AppendReceipt(existing["seq"], normalized["event_id"], True, digest)
                self._db.execute("COMMIT")
                return receipt
            cursor = self._db.execute("""
                INSERT INTO events(event_id, event_type, schema_version, observed_at, recorded_at, source_refs_json, payload_json, canonical_json, event_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (normalized["event_id"], normalized["event_type"], normalized["schema_version"], normalized["observed_at"], normalized["recorded_at"], _canonical_json(normalized["source_refs"]), _canonical_json(normalized["payload"]), encoded, digest))
            receipt = AppendReceipt(cursor.lastrowid, normalized["event_id"], False, digest)
            self._db.execute("COMMIT")
            return receipt
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    @property
    def last_event_seq(self) -> int:
        row = self._db.execute("SELECT COALESCE(MAX(seq), 0) AS n FROM events").fetchone()
        return int(row["n"])

    @property
    def projection_seq(self) -> int:
        row = self._db.execute(
            "SELECT last_seq FROM projection_cursors WHERE projection = ?",
            (self.PROJECTION,),
        ).fetchone()
        return int(row["last_seq"])

    def _apply_projection_event(self, row: sqlite3.Row) -> None:
        event_type = row["event_type"]
        payload = json.loads(row["payload_json"])
        seq = int(row["seq"])
        event_id = row["event_id"]

        if event_type == "CLAIM_ASSERTED":
            claim_id = _require_text(payload.get("claim_id"), "claim_id")
            subject = _require_text(payload.get("subject"), "subject")
            predicate = _require_text(payload.get("predicate"), "predicate")
            if "object" not in payload:
                raise ZPCMError("CLAIM_ASSERTED requires object")
            valid_from = _require_timestamp(payload.get("valid_from"), "valid_from")
            valid_until = payload.get("valid_until")
            if valid_until is not None:
                valid_until = _require_timestamp(valid_until, "valid_until")
                if valid_until < valid_from:
                    raise ZPCMError("valid_until must not precede valid_from")
            status = _require_text(payload.get("epistemic_status", "INFERRED"),
                                   "epistemic_status")
            evidence = _string_list(payload.get("evidence_refs", []),
                                    "evidence_refs", allow_empty=False)
            derivations = _string_list(payload.get("derivation_refs", []),
                                       "derivation_refs")
            scopes = _string_list(payload.get("scope_conditions", []),
                                  "scope_conditions")
            self._db.execute("""
                INSERT INTO claims(
                    claim_id, assertion_seq, event_id, subject, predicate,
                    object_json, valid_from, valid_until, epistemic_status,
                    evidence_refs_json, derivation_refs_json, scope_conditions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id, seq, event_id, subject, predicate,
                _canonical_json(payload["object"]), valid_from, valid_until,
                status, _canonical_json(evidence), _canonical_json(derivations),
                _canonical_json(scopes),
            ))
        elif event_type == "CLAIM_RETRACTED":
            claim_id = _require_text(payload.get("claim_id"), "claim_id")
            reason = _require_text(payload.get("reason"), "reason")
            cursor = self._db.execute("""
                UPDATE claims SET retracted_seq = ?, retraction_reason = ?
                WHERE claim_id = ? AND retracted_seq IS NULL
            """, (seq, reason, claim_id))
            if cursor.rowcount != 1:
                raise ZPCMError("cannot retract an unknown or already retracted claim")
        # Other event types remain in the immutable ledger. A projection may
        # intentionally ignore them without losing their provenance.

    def materialize(self, *, limit: int = 1000) -> MaterializeReport:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ZPCMError("limit must be a positive integer")
        self._db.execute("BEGIN IMMEDIATE")
        try:
            start = self.projection_seq
            rows = self._db.execute(
                "SELECT * FROM events WHERE seq > ? ORDER BY seq LIMIT ?",
                (start, limit),
            ).fetchall()
            cursor = start
            for row in rows:
                try:
                    self._apply_projection_event(row)
                except Exception as exc:
                    raise MaterializationError(
                        f"event seq={row['seq']} id={row['event_id']} failed: {exc}"
                    ) from exc
                cursor = int(row["seq"])
            if rows:
                self._db.execute(
                    "UPDATE projection_cursors SET last_seq = ? WHERE projection = ?",
                    (cursor, self.PROJECTION),
                )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        remaining = self._db.execute(
            "SELECT 1 FROM events WHERE seq > ? LIMIT 1", (cursor,)
        ).fetchone() is not None
        return MaterializeReport(start, cursor, len(rows), remaining)

    def query_claims(self, *, subject: str | None = None,
                     predicate: str | None = None, at_time: int | None = None,
                     include_retracted: bool = False) -> tuple[ClaimRecord, ...]:
        clauses: list[str] = []
        args: list[Any] = []
        if subject is not None:
            clauses.append("subject = ?")
            args.append(_require_text(subject, "subject"))
        if predicate is not None:
            clauses.append("predicate = ?")
            args.append(_require_text(predicate, "predicate"))
        if not include_retracted:
            clauses.append("retracted_seq IS NULL")
        if at_time is not None:
            at_time = _require_timestamp(at_time, "at_time")
            clauses.append("valid_from <= ? AND (valid_until IS NULL OR valid_until >= ?)")
            args.extend((at_time, at_time))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._db.execute(
            "SELECT * FROM claims" + where + " ORDER BY assertion_seq, claim_id",
            args,
        ).fetchall()
        return tuple(ClaimRecord(
            claim_id=row["claim_id"], subject=row["subject"],
            predicate=row["predicate"], object_value=json.loads(row["object_json"]),
            valid_from=row["valid_from"], valid_until=row["valid_until"],
            epistemic_status=row["epistemic_status"],
            evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
            derivation_refs=tuple(json.loads(row["derivation_refs_json"])),
            scope_conditions=tuple(json.loads(row["scope_conditions_json"])),
            assertion_seq=row["assertion_seq"], retracted_seq=row["retracted_seq"],
        ) for row in rows)

    def rebuild_projection(self) -> MaterializeReport:
        """Atomically rebuild the claims projection from the complete event log."""
        self._db.execute("BEGIN IMMEDIATE")
        try:
            start = self.projection_seq
            self._db.execute("DELETE FROM claims")
            self._db.execute(
                "UPDATE projection_cursors SET last_seq = 0 WHERE projection = ?",
                (self.PROJECTION,),
            )
            rows = self._db.execute("SELECT * FROM events ORDER BY seq").fetchall()
            cursor = 0
            for row in rows:
                try:
                    self._apply_projection_event(row)
                except Exception as exc:
                    raise MaterializationError(
                        f"replay event seq={row['seq']} id={row['event_id']} failed: {exc}"
                    ) from exc
                cursor = int(row["seq"])
            self._db.execute(
                "UPDATE projection_cursors SET last_seq = ? WHERE projection = ?",
                (cursor, self.PROJECTION),
            )
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise
        return MaterializeReport(start, cursor, len(rows), False)

    def verify_integrity(self) -> dict[str, Any]:
        sqlite_result = self._db.execute("PRAGMA integrity_check").fetchone()[0]
        rows = self._db.execute(
            "SELECT event_id, canonical_json, event_hash FROM events ORDER BY seq"
        ).fetchall()
        bad_hashes = []
        for row in rows:
            actual = hashlib.sha256(row["canonical_json"].encode("utf-8")).hexdigest()
            if actual != row["event_hash"]:
                bad_hashes.append(row["event_id"])
        return {
            "sqlite_integrity": sqlite_result,
            "event_count": len(rows),
            "bad_event_hashes": tuple(bad_hashes),
            "projection_seq": self.projection_seq,
            "last_event_seq": self.last_event_seq,
            "projection_lag": self.last_event_seq - self.projection_seq,
        }
