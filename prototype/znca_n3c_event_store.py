"""ZNCA N3-C: durable, hash-chained event store with optimistic concurrency."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class EventStoreError(RuntimeError):
    pass


class VersionConflict(EventStoreError):
    pass


class IdempotencyConflict(EventStoreError):
    pass


class IntegrityError(EventStoreError):
    pass


@dataclass(frozen=True)
class StoredEvent:
    stream_id: str
    sequence: int
    transaction_id: str
    event_type: str
    payload_json: str
    previous_hash: str
    event_hash: str

    @property
    def payload(self) -> dict:
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class RecoveryResult:
    stream_id: str
    version: int
    state: tuple[tuple[str, str], ...]
    last_hash: str

    def as_dict(self) -> dict[str, str]:
        return dict(self.state)


GENESIS = "0" * 64


def canonical_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EventStoreError("payload must be finite JSON data") from exc


def require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EventStoreError(f"{field} must be a non-empty string")


def calculate_hash(stream_id: str, sequence: int, transaction_id: str,
                   event_type: str, payload_json: str, previous_hash: str) -> str:
    envelope = {
        "stream_id": stream_id, "sequence": sequence,
        "transaction_id": transaction_id, "event_type": event_type,
        "payload": json.loads(payload_json), "previous_hash": previous_hash,
    }
    return hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()


class SQLiteEventStore:
    """Single-database append-only stream with CAS, idempotency and replay."""

    def __init__(self, path: str | Path, stream_id: str = "cognitive-state") -> None:
        require_text(stream_id, "stream_id")
        self.path = str(path)
        self.stream_id = stream_id
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path, timeout=10.0, isolation_level=None, check_same_thread=False
        )
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS znca_streams (
                stream_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL CHECK(version >= 0),
                last_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS znca_events (
                stream_id TEXT NOT NULL,
                sequence INTEGER NOT NULL CHECK(sequence > 0),
                transaction_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                request_fingerprint TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                PRIMARY KEY(stream_id, sequence),
                UNIQUE(stream_id, transaction_id),
                FOREIGN KEY(stream_id) REFERENCES znca_streams(stream_id)
            );
        """)
        self._connection.execute(
            "INSERT OR IGNORE INTO znca_streams VALUES (?, 0, ?)",
            (self.stream_id, GENESIS),
        )

    @property
    def version(self) -> int:
        row = self._connection.execute(
            "SELECT version FROM znca_streams WHERE stream_id = ?",
            (self.stream_id,),
        ).fetchone()
        return int(row[0])

    @property
    def last_hash(self) -> str:
        row = self._connection.execute(
            "SELECT last_hash FROM znca_streams WHERE stream_id = ?",
            (self.stream_id,),
        ).fetchone()
        return str(row[0])

    def append(self, *, expected_version: int, transaction_id: str,
               event_type: str, payload: Mapping[str, object]) -> StoredEvent:
        require_text(transaction_id, "transaction_id")
        require_text(event_type, "event_type")
        if not isinstance(expected_version, int) or expected_version < 0:
            raise EventStoreError("expected_version must be non-negative")
        if not isinstance(payload, Mapping):
            raise EventStoreError("payload must be a mapping")
        payload_json = canonical_json(dict(payload))
        fingerprint = canonical_json({
            "expected_version": expected_version,
            "event_type": event_type, "payload": json.loads(payload_json),
        })
        with self._lock:
            conn = self._connection
            try:
                conn.execute("BEGIN IMMEDIATE")
                duplicate = conn.execute(
                    """SELECT sequence, event_type, payload_json, request_fingerprint,
                              previous_hash, event_hash
                       FROM znca_events WHERE stream_id = ? AND transaction_id = ?""",
                    (self.stream_id, transaction_id),
                ).fetchone()
                if duplicate:
                    if duplicate[3] != fingerprint:
                        raise IdempotencyConflict("transaction_id reused for another command")
                    conn.execute("COMMIT")
                    return StoredEvent(self.stream_id, int(duplicate[0]), transaction_id,
                                       str(duplicate[1]), str(duplicate[2]),
                                       str(duplicate[4]), str(duplicate[5]))
                row = conn.execute(
                    "SELECT version, last_hash FROM znca_streams WHERE stream_id = ?",
                    (self.stream_id,),
                ).fetchone()
                current, previous_hash = int(row[0]), str(row[1])
                if current != expected_version:
                    raise VersionConflict(
                        f"expected version {expected_version}, current version {current}"
                    )
                sequence = current + 1
                digest = calculate_hash(self.stream_id, sequence, transaction_id,
                                        event_type, payload_json, previous_hash)
                conn.execute(
                    """INSERT INTO znca_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (self.stream_id, sequence, transaction_id, event_type,
                     payload_json, fingerprint, previous_hash, digest),
                )
                changed = conn.execute(
                    """UPDATE znca_streams SET version = ?, last_hash = ?
                       WHERE stream_id = ? AND version = ?""",
                    (sequence, digest, self.stream_id, expected_version),
                )
                if changed.rowcount != 1:
                    raise VersionConflict("compare-and-swap rejected append")
                conn.execute("COMMIT")
                return StoredEvent(self.stream_id, sequence, transaction_id,
                                   event_type, payload_json, previous_hash, digest)
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise

    def commit_hypothesis(self, *, expected_version: int, transaction_id: str,
                          hypothesis_id: str, base_version: int, status: str,
                          evidence_refs: Sequence[str],
                          state_delta: Mapping[str, str]) -> StoredEvent:
        require_text(hypothesis_id, "hypothesis_id")
        if status != "SUPPORTED":
            raise EventStoreError("only SUPPORTED hypotheses may commit")
        if base_version != expected_version:
            raise VersionConflict("base_version must equal expected_version")
        refs = tuple(evidence_refs)
        if not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
            raise EventStoreError("at least one non-empty evidence reference is required")
        if len(refs) != len(set(refs)):
            raise EventStoreError("evidence references must be unique")
        if not state_delta:
            raise EventStoreError("state_delta must not be empty")
        if any(not isinstance(k, str) or not k.strip()
               or not isinstance(v, str) or not v.strip()
               for k, v in state_delta.items()):
            raise EventStoreError("state_delta keys and values must be non-empty strings")
        return self.append(
            expected_version=expected_version, transaction_id=transaction_id,
            event_type="HypothesisCommitted",
            payload={
                "hypothesis_id": hypothesis_id, "base_version": base_version,
                "evidence_refs": sorted(refs),
                "state_delta": dict(sorted(state_delta.items())),
            },
        )

    def events(self, after_sequence: int = 0) -> tuple[StoredEvent, ...]:
        if not isinstance(after_sequence, int) or after_sequence < 0:
            raise EventStoreError("after_sequence must be non-negative")
        rows = self._connection.execute(
            """SELECT sequence, transaction_id, event_type, payload_json,
                      previous_hash, event_hash FROM znca_events
               WHERE stream_id = ? AND sequence > ? ORDER BY sequence""",
            (self.stream_id, after_sequence),
        ).fetchall()
        return tuple(StoredEvent(self.stream_id, int(r[0]), str(r[1]), str(r[2]),
                                 str(r[3]), str(r[4]), str(r[5])) for r in rows)

    def verify(self) -> tuple[StoredEvent, ...]:
        events = self.events()
        previous_hash = GENESIS
        for expected, event in enumerate(events, start=1):
            if event.sequence != expected:
                raise IntegrityError("event sequence contains a gap or duplicate")
            if event.previous_hash != previous_hash:
                raise IntegrityError(f"previous hash mismatch at sequence {expected}")
            digest = calculate_hash(event.stream_id, event.sequence,
                                    event.transaction_id, event.event_type,
                                    event.payload_json, event.previous_hash)
            if digest != event.event_hash:
                raise IntegrityError(f"event hash mismatch at sequence {expected}")
            previous_hash = event.event_hash
        if self.version != len(events):
            raise IntegrityError("stream version does not match event count")
        if self.last_hash != previous_hash:
            raise IntegrityError("stream head does not match event tail")
        return events

    def recover(self, initial_state: Mapping[str, str] | None = None) -> RecoveryResult:
        events = self.verify()
        state = dict(initial_state or {})
        for event in events:
            if event.event_type != "HypothesisCommitted":
                raise IntegrityError(f"unsupported event type: {event.event_type}")
            delta = event.payload.get("state_delta")
            if not isinstance(delta, dict) or any(
                not isinstance(k, str) or not k.strip()
                or not isinstance(v, str) or not v.strip()
                for k, v in delta.items()
            ):
                raise IntegrityError(f"invalid state_delta at sequence {event.sequence}")
            state.update(delta)
        return RecoveryResult(self.stream_id, len(events), tuple(sorted(state.items())),
                              self.last_hash)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
