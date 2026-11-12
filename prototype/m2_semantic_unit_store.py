"""Append-only M2 SemanticUnit lifecycle with SQLite-backed bounded runtime state.

memory_events remains the sole authority. The tables in this module are rebuildable
indexes over that log; candidate bodies are fetched from the event log only when
requested, never copied into an in-memory history cache during startup.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from threading import RLock
from typing import Any, Iterator

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.observation_contract import (
    ContractError, EpistemicStatus, EvidenceRef, GroundingStatus,
    RecordEnvelope, RoleBinding, Score, SemanticUnitCandidate,
    TruthStatus, TypedAttribute, UnitKind, canonical_json, record_digest,
)
from prototype.zpcm_memory import ZPCMError, ZPCMMemory, canonical, digest


EVENT_TYPE = "m2_semantic_unit"
EVENT_SCHEMA = "m2-semantic-unit-event-v1"
PROJECTION_SCHEMA = "m2-semantic-unit-projection-v1"
MAX_EVENT_BYTES = 1024 * 1024
MAX_REPLAY_PAGE_ROWS = 128
MAX_REPLAY_PAGE_BYTES = 4 * 1024 * 1024


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
    """Typed candidate lifecycle using bounded replay and indexed SQLite projections.

    The event log is authoritative. Projection rows contain identity/lineage metadata
    only; candidate bodies remain in memory_events and are loaded on demand.
    Explicit history/candidates properties materialize their requested result sets.
    """

    def __init__(
        self, memory: ZPCMMemory, resolver: SQLiteEvidenceRefResolver, *,
        scope: str, replay_page_size: int = 128,
        max_event_bytes: int = MAX_EVENT_BYTES,
        max_replay_page_bytes: int = MAX_REPLAY_PAGE_BYTES,
    ):
        if not isinstance(memory, ZPCMMemory):
            raise TypeError("memory must be ZPCMMemory")
        if not isinstance(resolver, SQLiteEvidenceRefResolver):
            raise TypeError("resolver must be SQLiteEvidenceRefResolver")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be non-empty")
        if (isinstance(replay_page_size, bool) or not isinstance(replay_page_size, int)
                or not 1 <= replay_page_size <= MAX_REPLAY_PAGE_ROWS):
            raise ValueError(f"replay_page_size must be in [1, {MAX_REPLAY_PAGE_ROWS}]")
        if (isinstance(max_event_bytes, bool) or not isinstance(max_event_bytes, int)
                or not 1 <= max_event_bytes <= MAX_EVENT_BYTES):
            raise ValueError(f"max_event_bytes must be in [1, {MAX_EVENT_BYTES}]")
        if (isinstance(max_replay_page_bytes, bool)
                or not isinstance(max_replay_page_bytes, int)
                or not 1 <= max_replay_page_bytes <= MAX_REPLAY_PAGE_BYTES):
            raise ValueError(f"max_replay_page_bytes must be in [1, {MAX_REPLAY_PAGE_BYTES}]")
        if max_event_bytes > max_replay_page_bytes:
            raise ValueError("max_event_bytes cannot exceed max_replay_page_bytes")
        self._memory, self._resolver, self.scope = memory, resolver, scope
        self._replay_page_size = replay_page_size
        self._max_event_bytes = max_event_bytes
        self._max_replay_page_bytes = max_replay_page_bytes
        self._lock = RLock()
        self._initialize_projection()
        self._restore()

    def _initialize_projection(self) -> None:
        db = self._memory.db
        with self._memory.lock:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS m2_semantic_unit_records(
                scope TEXT NOT NULL,
                record_id TEXT NOT NULL,
                root_id TEXT NOT NULL,
                previous_record_id TEXT,
                event_kind TEXT NOT NULL,
                record_digest TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                payload_digest TEXT NOT NULL,
                PRIMARY KEY(scope,record_id),
                UNIQUE(scope,event_id),
                FOREIGN KEY(event_id) REFERENCES memory_events(event_id)
            );
            CREATE INDEX IF NOT EXISTS m2_su_records_root_seq
                ON m2_semantic_unit_records(scope,root_id,sequence);
            CREATE INDEX IF NOT EXISTS m2_su_records_previous
                ON m2_semantic_unit_records(scope,previous_record_id);
            CREATE TABLE IF NOT EXISTS m2_semantic_unit_heads(
                scope TEXT NOT NULL,
                root_id TEXT NOT NULL,
                current_record_id TEXT NOT NULL,
                retraction_reason TEXT,
                updated_sequence INTEGER NOT NULL,
                PRIMARY KEY(scope,root_id),
                FOREIGN KEY(scope,current_record_id)
                    REFERENCES m2_semantic_unit_records(scope,record_id)
            );
            CREATE INDEX IF NOT EXISTS m2_su_heads_current
                ON m2_semantic_unit_heads(scope,current_record_id);
            CREATE TABLE IF NOT EXISTS m2_semantic_unit_projection_state(
                scope TEXT PRIMARY KEY,
                generation INTEGER NOT NULL CHECK(generation>=0)
            );
            CREATE TABLE IF NOT EXISTS m2_semantic_unit_projection_checkpoint(
                scope TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                high_water_seq INTEGER NOT NULL CHECK(high_water_seq>=0),
                projection_generation INTEGER NOT NULL,
                checkpoint_digest TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS m2_su_records_insert
            AFTER INSERT ON m2_semantic_unit_records BEGIN
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1 WHERE scope=NEW.scope;
            END;
            CREATE TRIGGER IF NOT EXISTS m2_su_records_update
            AFTER UPDATE ON m2_semantic_unit_records BEGIN
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1 WHERE scope=OLD.scope;
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1
                WHERE scope=NEW.scope AND NEW.scope<>OLD.scope;
            END;
            CREATE TRIGGER IF NOT EXISTS m2_su_records_delete
            AFTER DELETE ON m2_semantic_unit_records BEGIN
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1 WHERE scope=OLD.scope;
            END;
            CREATE TRIGGER IF NOT EXISTS m2_su_heads_insert
            AFTER INSERT ON m2_semantic_unit_heads BEGIN
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1 WHERE scope=NEW.scope;
            END;
            CREATE TRIGGER IF NOT EXISTS m2_su_heads_update
            AFTER UPDATE ON m2_semantic_unit_heads BEGIN
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1 WHERE scope=OLD.scope;
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1
                WHERE scope=NEW.scope AND NEW.scope<>OLD.scope;
            END;
            CREATE TRIGGER IF NOT EXISTS m2_su_heads_delete
            AFTER DELETE ON m2_semantic_unit_heads BEGIN
                UPDATE m2_semantic_unit_projection_state
                SET generation=generation+1 WHERE scope=OLD.scope;
            END;
            """)
            db.execute(
                "INSERT OR IGNORE INTO m2_semantic_unit_projection_state(scope,generation) VALUES(?,0)",
                (self.scope,),
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS memory_events_type_scope_seq "
                "ON memory_events(event_type,scope,seq)"
            )

    @staticmethod
    def _checkpoint_digest(scope: str, high_water: int, generation: int) -> str:
        material = {
            "schema_version": PROJECTION_SCHEMA,
            "scope": scope,
            "high_water_seq": high_water,
            "projection_generation": generation,
        }
        return hashlib.sha256(canonical(material).encode("utf-8")).hexdigest()

    def _write_checkpoint(self, high_water: int) -> None:
        db = self._memory.db
        generation = int(db.execute(
            "SELECT generation FROM m2_semantic_unit_projection_state WHERE scope=?",
            (self.scope,),
        ).fetchone()[0])
        db.execute(
            """INSERT INTO m2_semantic_unit_projection_checkpoint
               (scope,schema_version,high_water_seq,projection_generation,checkpoint_digest)
               VALUES(?,?,?,?,?)
               ON CONFLICT(scope) DO UPDATE SET
                 schema_version=excluded.schema_version,
                 high_water_seq=excluded.high_water_seq,
                 projection_generation=excluded.projection_generation,
                 checkpoint_digest=excluded.checkpoint_digest""",
            (self.scope, PROJECTION_SCHEMA, high_water, generation,
             self._checkpoint_digest(self.scope, high_water, generation)),
        )

    def _stream_events(self, after_sequence: int) -> Iterator[dict[str, Any]]:
        """Read one M2 event at a time after bounded metadata selection."""
        db = self._memory.db
        high_water = int(db.execute(
            "SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type=? AND scope=?",
            (EVENT_TYPE, self.scope),
        ).fetchone()[0])
        cursor = after_sequence
        while cursor < high_water:
            metadata = db.execute(
                """SELECT seq,event_id,payload_digest,recorded_at,
                          length(CAST(payload_json AS BLOB))
                   FROM memory_events
                   WHERE event_type=? AND scope=? AND seq>? AND seq<=?
                   ORDER BY seq LIMIT ?""",
                (EVENT_TYPE, self.scope, cursor, high_water, self._replay_page_size),
            ).fetchall()
            if not metadata:
                break
            page_bytes = 0
            for row in metadata:
                seq, event_id, payload_digest, recorded_at, payload_bytes = row
                payload_bytes = int(payload_bytes)
                if payload_bytes > self._max_event_bytes:
                    raise SemanticUnitStoreError(
                        f"M2 event exceeds hard payload byte limit: {event_id}"
                    )
                if payload_bytes > self._max_replay_page_bytes - page_bytes:
                    if page_bytes == 0:
                        raise SemanticUnitStoreError(
                            f"single M2 event exceeds replay page byte budget: {event_id}"
                        )
                    break
                raw = db.execute(
                    "SELECT payload_json FROM memory_events WHERE seq=? AND event_id=?",
                    (seq, event_id),
                ).fetchone()
                if raw is None:
                    raise SemanticUnitStoreError("M2 event disappeared during bounded replay")
                payload = json.loads(raw[0])
                if digest(payload) != payload_digest:
                    raise SemanticUnitStoreError(f"M2 event digest mismatch: {event_id}")
                yield {
                    "sequence": int(seq), "event_id": event_id,
                    "payload_digest": payload_digest, "recorded_at": recorded_at,
                    "payload": payload,
                }
                cursor = int(seq)
                page_bytes += payload_bytes
            if cursor < int(metadata[-1][0]) and page_bytes >= self._max_replay_page_bytes:
                continue
            if cursor < int(metadata[-1][0]):
                # The next event did not fit; re-query from the last committed
                # cursor rather than skipping it or retaining a decoded page.
                continue

    def _verify_candidate(self, candidate: SemanticUnitCandidate) -> None:
        if candidate.envelope.scope != self.scope:
            raise SemanticUnitStoreError("candidate scope does not match store scope")
        refs = list(candidate.envelope.source_refs)
        for attribute in candidate.typed_attributes:
            refs.extend(attribute.source_refs)
        seen = set()
        for ref in refs:
            key = (ref.document_id, ref.chunk_id, ref.content_sha256,
                   ref.byte_start, ref.byte_end, ref.source_version)
            if key not in seen:
                self._resolver.resolve(ref)
                seen.add(key)

    @staticmethod
    def _payload(kind: str, candidate: SemanticUnitCandidate,
                 previous_id: str | None = None):
        body = json.loads(canonical_json(candidate))
        digest_value = record_digest(candidate)
        payload = {"schema_version": EVENT_SCHEMA, "kind": kind,
                   "body": body, "body_digest": digest_value}
        if previous_id is not None:
            payload["previous_record_id"] = previous_id
        return payload, digest_value

    def _apply_event(self, event: dict[str, Any]) -> None:
        db = self._memory.db
        payload = event["payload"]
        if payload.get("schema_version") != EVENT_SCHEMA:
            raise SemanticUnitStoreError("unsupported semantic-unit event schema")
        kind, event_id, seq = payload.get("kind"), event["event_id"], event["sequence"]
        if kind in ("candidate_recorded", "candidate_revised"):
            body = payload.get("body")
            if not isinstance(body, dict):
                raise SemanticUnitStoreError("candidate event body must be an object")
            candidate = _candidate_from_dict(body)
            self._verify_candidate(candidate)
            rid = candidate.envelope.record_id
            record_hash = record_digest(candidate)
            if record_hash != payload.get("body_digest"):
                raise SemanticUnitStoreError("candidate digest mismatch")
            if event_id != f"m2:semantic-unit:{rid}":
                raise SemanticUnitStoreError("candidate event identity is inconsistent")
            previous = payload.get("previous_record_id") if kind == "candidate_revised" else None
            if kind == "candidate_recorded":
                if db.execute(
                    "SELECT 1 FROM m2_semantic_unit_records WHERE scope=? AND record_id=?",
                    (self.scope, rid),
                ).fetchone():
                    raise SemanticUnitStoreError("duplicate candidate record ID")
                root = rid
                db.execute(
                    """INSERT INTO m2_semantic_unit_records
                       (scope,record_id,root_id,previous_record_id,event_kind,record_digest,
                        event_id,sequence,payload_digest)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (self.scope, rid, root, None, kind, record_hash, event_id, seq,
                     event["payload_digest"]),
                )
                db.execute(
                    """INSERT INTO m2_semantic_unit_heads
                       (scope,root_id,current_record_id,retraction_reason,updated_sequence)
                       VALUES(?,?,?,NULL,?)""",
                    (self.scope, root, rid, seq),
                )
            else:
                prior = db.execute(
                    """SELECT root_id FROM m2_semantic_unit_records
                       WHERE scope=? AND record_id=?""",
                    (self.scope, previous),
                ).fetchone()
                if prior is None:
                    raise SemanticUnitStoreError("revision predecessor does not exist")
                root = str(prior[0])
                head = db.execute(
                    """SELECT current_record_id,retraction_reason FROM m2_semantic_unit_heads
                       WHERE scope=? AND root_id=?""",
                    (self.scope, root),
                ).fetchone()
                if (head is None or head[0] != previous or head[1] is not None
                        or candidate.envelope.derivation_refs.count(previous) != 1):
                    raise SemanticUnitStoreError(
                        "revision does not extend the current active version"
                    )
                if candidate.envelope.scope != self.scope:
                    raise SemanticUnitStoreError("revision cannot cross scopes")
                db.execute(
                    """INSERT INTO m2_semantic_unit_records
                       (scope,record_id,root_id,previous_record_id,event_kind,record_digest,
                        event_id,sequence,payload_digest)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (self.scope, rid, root, previous, kind, record_hash, event_id, seq,
                     event["payload_digest"]),
                )
                db.execute(
                    """UPDATE m2_semantic_unit_heads
                       SET current_record_id=?,updated_sequence=?
                       WHERE scope=? AND root_id=?""",
                    (rid, seq, self.scope, root),
                )
        elif kind == "candidate_retracted":
            rid, reason = payload.get("record_id"), payload.get("reason")
            if event_id != f"m2:semantic-unit:{rid}:retracted":
                raise SemanticUnitStoreError("retraction event identity is invalid")
            if not isinstance(reason, str) or not reason.strip():
                raise SemanticUnitStoreError("retraction reason is invalid")
            row = db.execute(
                """SELECT root_id FROM m2_semantic_unit_records
                   WHERE scope=? AND record_id=?""",
                (self.scope, rid),
            ).fetchone()
            if row is None:
                raise SemanticUnitStoreError("retraction target does not exist")
            head = db.execute(
                """SELECT current_record_id,retraction_reason FROM m2_semantic_unit_heads
                   WHERE scope=? AND root_id=?""",
                (self.scope, row[0]),
            ).fetchone()
            if head is None or head[0] != rid or head[1] is not None:
                raise SemanticUnitStoreError("only the current active candidate can be retracted")
            db.execute(
                """UPDATE m2_semantic_unit_heads SET retraction_reason=?,updated_sequence=?
                   WHERE scope=? AND root_id=?""",
                (reason, seq, self.scope, row[0]),
            )
        else:
            raise SemanticUnitStoreError("unknown semantic-unit event kind")

    def _restore(self) -> None:
        db = self._memory.db
        with self._lock, self._memory.lock:
            db.execute("BEGIN IMMEDIATE")
            try:
                current = int(db.execute(
                    "SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type=? AND scope=?",
                    (EVENT_TYPE, self.scope),
                ).fetchone()[0])
                checkpoint = db.execute(
                    """SELECT schema_version,high_water_seq,projection_generation,checkpoint_digest
                       FROM m2_semantic_unit_projection_checkpoint WHERE scope=?""",
                    (self.scope,),
                ).fetchone()
                generation = int(db.execute(
                    "SELECT generation FROM m2_semantic_unit_projection_state WHERE scope=?",
                    (self.scope,),
                ).fetchone()[0])
                valid = False
                start = 0
                if checkpoint is not None:
                    version, saved, saved_generation, saved_digest = checkpoint
                    valid = (
                        version == PROJECTION_SCHEMA
                        and 0 <= int(saved) <= current
                        and int(saved_generation) == generation
                        and saved_digest == self._checkpoint_digest(
                            self.scope, int(saved), int(saved_generation)
                        )
                    )
                    if valid:
                        start = int(saved)
                if not valid:
                    db.execute("DELETE FROM m2_semantic_unit_heads WHERE scope=?", (self.scope,))
                    db.execute("DELETE FROM m2_semantic_unit_records WHERE scope=?", (self.scope,))
                    start = 0
                previous_sequence = start
                for event in self._stream_events(start):
                    seq = event["sequence"]
                    if seq <= previous_sequence:
                        raise SemanticUnitStoreError(
                            "semantic-unit event sequence is not strictly increasing"
                        )
                    previous_sequence = seq
                    self._apply_event(event)
                if previous_sequence != current:
                    raise SemanticUnitStoreError(
                        "semantic-unit replay did not reach the captured event high-water mark"
                    )
                self._write_checkpoint(current)
                db.execute("COMMIT")
            except (ZPCMError, ContractError, SemanticUnitStoreError):
                db.execute("ROLLBACK")
                raise
            except Exception as exc:
                db.execute("ROLLBACK")
                raise SemanticUnitStoreError(f"semantic-unit replay failed: {exc}") from exc

    def _record_metadata(self, record_id: str):
        return self._memory.db.execute(
            """SELECT event_kind,record_digest,event_id,sequence,payload_digest,
                      root_id,previous_record_id
               FROM m2_semantic_unit_records WHERE scope=? AND record_id=?""",
            (self.scope, record_id),
        ).fetchone()

    def _candidate_for_record(self, record_id: str) -> SemanticUnitCandidate:
        metadata = self._record_metadata(record_id)
        if metadata is None:
            raise SemanticUnitStoreError("candidate record is missing from projection")
        event = self._memory.get_domain_event(
            event_type=EVENT_TYPE, scope=self.scope, event_id=metadata["event_id"]
        )
        if event is None:
            raise SemanticUnitStoreError("candidate event is missing from authoritative log")
        candidate = _candidate_from_dict(event["payload"]["body"])
        if (record_digest(candidate) != metadata["record_digest"]
                or event["payload_digest"] != metadata["payload_digest"]):
            raise SemanticUnitStoreError("candidate projection does not match authoritative event")
        return candidate

    @property
    def candidates(self) -> dict[str, SemanticUnitCandidate]:
        with self._lock, self._memory.lock:
            rows = self._memory.db.execute(
                """SELECT root_id,current_record_id FROM m2_semantic_unit_heads
                   WHERE scope=? AND retraction_reason IS NULL ORDER BY root_id""",
                (self.scope,),
            ).fetchall()
            return {str(row[0]): self._candidate_for_record(str(row[1])) for row in rows}

    @property
    def history(self) -> dict[str, SemanticUnitCandidate]:
        """Explicitly materialize full history; not used by startup or write paths."""
        with self._lock, self._memory.lock:
            rows = self._memory.db.execute(
                """SELECT record_id FROM m2_semantic_unit_records
                   WHERE scope=? ORDER BY sequence""",
                (self.scope,),
            ).fetchall()
            return {str(row[0]): self._candidate_for_record(str(row[0])) for row in rows}

    @property
    def retractions(self) -> dict[str, str]:
        with self._lock, self._memory.lock:
            rows = self._memory.db.execute(
                """SELECT current_record_id,retraction_reason FROM m2_semantic_unit_heads
                   WHERE scope=? AND retraction_reason IS NOT NULL ORDER BY root_id""",
                (self.scope,),
            ).fetchall()
            return {str(row[0]): str(row[1]) for row in rows}

    @property
    def _receipts(self) -> dict[str, SemanticUnitReceipt]:
        """Compatibility view; explicit access materializes receipts on demand."""
        with self._lock, self._memory.lock:
            rows = self._memory.db.execute(
                """SELECT record_id,event_id,sequence,payload_digest,record_digest
                   FROM m2_semantic_unit_records WHERE scope=?""",
                (self.scope,),
            ).fetchall()
            return {str(row[0]): SemanticUnitReceipt(
                str(row[1]), int(row[2]), str(row[3]), str(row[4]), True
            ) for row in rows}

    def _append_event_with_projection(
        self, *, event_id: str, payload: dict[str, Any],
        expected_sequence: int, record_id: str | None,
    ) -> dict[str, Any]:
        """Atomically append the authoritative event and update its derived index."""
        db = self._memory.db
        serialized_bytes = len(canonical(payload).encode("utf-8"))
        if serialized_bytes > self._max_event_bytes:
            raise SemanticUnitStoreError(
                f"semantic-unit event exceeds hard payload byte limit ({self._max_event_bytes})"
            )
        payload_digest = digest(payload)
        with self._memory.lock:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute(
                    """SELECT seq,event_type,scope,payload_digest FROM memory_events
                       WHERE event_id=?""",
                    (event_id,),
                ).fetchone()
                if prior is not None:
                    if (prior["event_type"], prior["scope"], prior["payload_digest"]) != (
                        EVENT_TYPE, self.scope, payload_digest
                    ):
                        raise SemanticUnitStoreError("event ID content conflict")
                    exists = db.execute(
                        """SELECT 1 FROM m2_semantic_unit_records
                           WHERE scope=? AND event_id=?""",
                        (self.scope, event_id),
                    ).fetchone()
                    if record_id is None:
                        exists = db.execute(
                            """SELECT 1 FROM m2_semantic_unit_heads
                               WHERE scope=? AND current_record_id=?""",
                            (self.scope, payload.get("record_id")),
                        ).fetchone()
                    if exists is None:
                        raise SemanticUnitStoreError(
                            "authoritative event exists without its projection; reconstruct store before retry"
                        )
                    db.execute("COMMIT")
                    return {"sequence": int(prior["seq"]),
                            "payload_digest": payload_digest, "replayed": True}
                current = int(db.execute(
                    """SELECT COALESCE(MAX(seq),0) FROM memory_events
                       WHERE event_type=? AND scope=?""",
                    (EVENT_TYPE, self.scope),
                ).fetchone()[0])
                if current != expected_sequence:
                    raise SemanticUnitStoreError(
                        f"stale semantic-unit sequence: expected {expected_sequence}, current {current}"
                    )
                seq, replayed = self._memory._append(
                    event_id, EVENT_TYPE, self.scope, payload
                )
                if replayed:
                    raise SemanticUnitStoreError("unexpected event replay state")
                event = {
                    "sequence": int(seq), "event_id": event_id,
                    "payload_digest": payload_digest, "payload": payload,
                }
                self._apply_event(event)
                self._write_checkpoint(int(seq))
                db.execute("COMMIT")
                return {"sequence": int(seq), "payload_digest": payload_digest,
                        "replayed": False}
            except Exception:
                db.execute("ROLLBACK")
                raise

    def _append_candidate(
        self, candidate: SemanticUnitCandidate, *, previous_id: str | None,
    ) -> SemanticUnitReceipt:
        self._verify_candidate(candidate)
        rid = candidate.envelope.record_id
        kind = "candidate_revised" if previous_id is not None else "candidate_recorded"
        payload, digest_value = self._payload(kind, candidate, previous_id)
        if record_digest(candidate) != digest_value:
            raise SemanticUnitStoreError("candidate digest changed during serialization")
        event_id = f"m2:semantic-unit:{rid}"
        raw = self._append_event_with_projection(
            event_id=event_id, payload=payload,
            expected_sequence=self._memory.latest_domain_sequence(
                event_type=EVENT_TYPE, scope=self.scope
            ),
            record_id=rid,
        )
        return SemanticUnitReceipt(
            event_id, raw["sequence"], raw["payload_digest"], digest_value,
            raw["replayed"],
        )

    def record_candidate(self, candidate: SemanticUnitCandidate) -> SemanticUnitReceipt:
        if not isinstance(candidate, SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock, self._memory.lock:
            prior = self._record_metadata(candidate.envelope.record_id)
            if prior is not None:
                if prior["event_kind"] != "candidate_recorded":
                    raise SemanticUnitStoreError("record_candidate cannot replay a revision event")
                if prior["record_digest"] != record_digest(candidate):
                    raise SemanticUnitStoreError("candidate record_id is immutable")
                return SemanticUnitReceipt(
                    prior["event_id"], int(prior["sequence"]),
                    prior["payload_digest"], prior["record_digest"], True,
                )
            return self._append_candidate(candidate, previous_id=None)

    def revise_candidate(
        self, previous_record_id: str, candidate: SemanticUnitCandidate,
    ) -> SemanticUnitReceipt:
        if not isinstance(previous_record_id, str) or not previous_record_id.strip():
            raise ValueError("previous_record_id must be non-empty")
        if not isinstance(candidate, SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock, self._memory.lock:
            candidate_id = candidate.envelope.record_id
            prior = self._record_metadata(candidate_id)
            if prior is not None:
                if (prior["event_kind"] != "candidate_revised"
                        or prior["previous_record_id"] != previous_record_id
                        or prior["record_digest"] != record_digest(candidate)
                        or candidate.envelope.derivation_refs.count(previous_record_id) != 1):
                    raise SemanticUnitStoreError(
                        "candidate revision identity/predecessor is immutable"
                    )
                return SemanticUnitReceipt(
                    prior["event_id"], int(prior["sequence"]),
                    prior["payload_digest"], prior["record_digest"], True,
                )
            predecessor = self._record_metadata(previous_record_id)
            if predecessor is None:
                raise SemanticUnitStoreError("revision predecessor does not exist")
            head = self._memory.db.execute(
                """SELECT current_record_id,retraction_reason FROM m2_semantic_unit_heads
                   WHERE scope=? AND root_id=?""",
                (self.scope, predecessor["root_id"]),
            ).fetchone()
            if (head is None or head[0] != previous_record_id or head[1] is not None):
                raise SemanticUnitStoreError("only the current active candidate can be revised")
            if candidate.envelope.derivation_refs.count(previous_record_id) != 1:
                raise SemanticUnitStoreError(
                    "revision must cite predecessor exactly once in derivation_refs"
                )
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
        with self._lock, self._memory.lock:
            metadata = self._record_metadata(record_id)
            if metadata is None:
                raise SemanticUnitStoreError("candidate record does not exist")
            head = self._memory.db.execute(
                """SELECT current_record_id,retraction_reason FROM m2_semantic_unit_heads
                   WHERE scope=? AND root_id=?""",
                (self.scope, metadata["root_id"]),
            ).fetchone()
            if head is None or head[0] != record_id:
                raise SemanticUnitStoreError("only the current candidate version can be retracted")
            event_id = f"m2:semantic-unit:{record_id}:retracted"
            if head[1] is not None:
                if head[1] != reason:
                    raise SemanticUnitStoreError("retraction reason conflicts with prior tombstone")
                event = self._memory.get_domain_event(
                    event_type=EVENT_TYPE, scope=self.scope, event_id=event_id
                )
                if event is None:
                    raise SemanticUnitStoreError("retraction receipt is missing from the event log")
                return SemanticUnitReceipt(
                    event_id, event["sequence"], event["payload_digest"],
                    metadata["record_digest"], True,
                )
            payload = {
                "schema_version": EVENT_SCHEMA, "kind": "candidate_retracted",
                "record_id": record_id, "reason": reason,
            }
            raw = self._append_event_with_projection(
                event_id=event_id, payload=payload,
                expected_sequence=self._memory.latest_domain_sequence(
                    event_type=EVENT_TYPE, scope=self.scope
                ),
                record_id=None,
            )
            return SemanticUnitReceipt(
                event_id, raw["sequence"], raw["payload_digest"],
                metadata["record_digest"], raw["replayed"],
            )

    def rebuild_projection(self) -> None:
        """Explicitly discard and stream-rebuild this scope's derived projection."""
        db = self._memory.db
        with self._lock, self._memory.lock:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("DELETE FROM m2_semantic_unit_heads WHERE scope=?", (self.scope,))
                db.execute("DELETE FROM m2_semantic_unit_records WHERE scope=?", (self.scope,))
                for event in self._stream_events(0):
                    self._apply_event(event)
                high_water = int(db.execute(
                    "SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type=? AND scope=?",
                    (EVENT_TYPE, self.scope),
                ).fetchone()[0])
                self._write_checkpoint(high_water)
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
