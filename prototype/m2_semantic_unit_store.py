"""Append-only M2 semantic-unit lifecycle with SQLite-derived bounded startup projection.

The memory_events table remains the sole source of truth. The projection stores
only version metadata and each root's current body; historical bodies are read
from the event log only through the explicit history API or projection rebuild.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3
from threading import RLock
from typing import Any, Iterator

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.observation_contract import (
    ContractError, EpistemicStatus, EvidenceRef, GroundingStatus,
    RecordEnvelope, RoleBinding, Score, SemanticUnitCandidate,
    TruthStatus, TypedAttribute, UnitKind, canonical_json, record_digest,
)
from prototype.zpcm_memory import ZPCMError, ZPCMMemory


EVENT_TYPE = "m2_semantic_unit"
EVENT_SCHEMA = "m2-semantic-unit-event-v1"
PROJECTION_SCHEMA = "m2-semantic-unit-sqlite-projection-v1"


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
    """SQLite-backed M2 lifecycle; initialization never materializes full history."""

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
        self._ensure_projection_schema()
        self._restore()

    @property
    def _db(self):
        return self._memory.db

    def _ensure_projection_schema(self) -> None:
        with self._memory.lock:
            self._db.executescript("""
            CREATE TABLE IF NOT EXISTS m2_semantic_unit_versions(
                scope TEXT NOT NULL,
                record_id TEXT NOT NULL,
                root_id TEXT NOT NULL,
                predecessor_id TEXT,
                event_kind TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                payload_digest TEXT NOT NULL,
                record_digest TEXT NOT NULL,
                PRIMARY KEY(scope,record_id),
                UNIQUE(scope,event_id)
            );
            CREATE INDEX IF NOT EXISTS m2_semantic_unit_versions_root
                ON m2_semantic_unit_versions(scope,root_id,sequence);
            CREATE TABLE IF NOT EXISTS m2_semantic_unit_roots(
                scope TEXT NOT NULL,
                root_id TEXT NOT NULL,
                current_record_id TEXT NOT NULL,
                current_body_json TEXT NOT NULL,
                current_record_digest TEXT NOT NULL,
                current_event_id TEXT NOT NULL,
                current_sequence INTEGER NOT NULL,
                retracted_reason TEXT,
                PRIMARY KEY(scope,root_id),
                UNIQUE(scope,current_record_id)
            );
            CREATE INDEX IF NOT EXISTS m2_semantic_unit_roots_active
                ON m2_semantic_unit_roots(scope,retracted_reason,current_sequence);
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
            INSERT OR IGNORE INTO m2_semantic_unit_projection_state(scope,generation)
                VALUES("unused",0);
            """.replace(
                "VALUES('unused',0);",
                "VALUES(" + "'" + self.scope.replace("'", "''") + "'" + ",0);"
            ))
            # Triggers make out-of-band projection mutation invalidate the checkpoint.
            trigger_suffix = hashlib.sha256(self.scope.encode("utf-8")).hexdigest()[:16]
            for operation, timing in (("INSERT", "insert"), ("UPDATE", "update"), ("DELETE", "delete")):
                for table in ("m2_semantic_unit_versions", "m2_semantic_unit_roots"):
                    trigger = f"m2_{table.rsplit('_', 1)[-1]}_{timing}_{trigger_suffix}"
                    self._db.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {trigger} AFTER {operation} ON {table} "
                        "BEGIN UPDATE m2_semantic_unit_projection_state "
                        "SET generation=generation+1 WHERE scope=NEW.scope; END"
                        if operation != "DELETE" else
                        f"CREATE TRIGGER IF NOT EXISTS {trigger} AFTER DELETE ON {table} "
                        "BEGIN UPDATE m2_semantic_unit_projection_state "
                        "SET generation=generation+1 WHERE scope=OLD.scope; END"
                    )
            self._db.execute(
                "INSERT OR IGNORE INTO m2_semantic_unit_projection_state(scope,generation) VALUES(?,0)",
                (self.scope,),
            )

    def _latest_sequence(self) -> int:
        return int(self._db.execute(
            "SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type=? AND scope=?",
            (EVENT_TYPE, self.scope),
        ).fetchone()[0])

    @staticmethod
    def _checkpoint_digest(scope: str, high_water: int, generation: int) -> str:
        value = {
            "schema_version": PROJECTION_SCHEMA, "scope": scope,
            "high_water_seq": high_water, "projection_generation": generation,
        }
        return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

    def _checkpoint_valid(self) -> bool:
        checkpoint = self._db.execute(
            "SELECT schema_version,high_water_seq,projection_generation,checkpoint_digest "
            "FROM m2_semantic_unit_projection_checkpoint WHERE scope=?", (self.scope,)
        ).fetchone()
        state = self._db.execute(
            "SELECT generation FROM m2_semantic_unit_projection_state WHERE scope=?",
            (self.scope,),
        ).fetchone()
        if checkpoint is None or state is None:
            return False
        high_water, generation = self._latest_sequence(), int(state["generation"])
        return (
            checkpoint["schema_version"] == PROJECTION_SCHEMA
            and int(checkpoint["high_water_seq"]) == high_water
            and int(checkpoint["projection_generation"]) == generation
            and checkpoint["checkpoint_digest"]
                == self._checkpoint_digest(self.scope, high_water, generation)
        )

    def _write_checkpoint(self, high_water: int) -> None:
        generation = int(self._db.execute(
            "SELECT generation FROM m2_semantic_unit_projection_state WHERE scope=?",
            (self.scope,),
        ).fetchone()[0])
        self._db.execute(
            "INSERT INTO m2_semantic_unit_projection_checkpoint("
            "scope,schema_version,high_water_seq,projection_generation,checkpoint_digest) "
            "VALUES(?,?,?,?,?) ON CONFLICT(scope) DO UPDATE SET "
            "schema_version=excluded.schema_version,high_water_seq=excluded.high_water_seq,"
            "projection_generation=excluded.projection_generation,"
            "checkpoint_digest=excluded.checkpoint_digest",
            (self.scope, PROJECTION_SCHEMA, high_water, generation,
             self._checkpoint_digest(self.scope, high_water, generation)),
        )

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

    def _project_event(self, event: dict[str, Any]) -> None:
        payload, event_id, seq = event["payload"], event["event_id"], event["sequence"]
        if payload.get("schema_version") != EVENT_SCHEMA:
            raise SemanticUnitStoreError("unsupported semantic-unit event schema")
        kind = payload.get("kind")
        if kind in ("candidate_recorded", "candidate_revised"):
            body = payload.get("body")
            if not isinstance(body, dict):
                raise SemanticUnitStoreError("candidate event body must be an object")
            candidate = _candidate_from_dict(body)
            self._verify_candidate(candidate)
            rid = candidate.envelope.record_id
            candidate_digest = record_digest(candidate)
            if candidate_digest != payload.get("body_digest"):
                raise SemanticUnitStoreError("candidate body digest mismatch")
            if kind == "candidate_recorded":
                if event_id != f"m2:semantic-unit:{rid}":
                    raise SemanticUnitStoreError("candidate event identity is inconsistent")
                root = rid
                self._db.execute(
                    "INSERT INTO m2_semantic_unit_versions VALUES(?,?,?,?,?,?,?,?,?)",
                    (self.scope,rid,root,None,kind,event_id,seq,event["payload_digest"],candidate_digest),
                )
                self._db.execute(
                    "INSERT INTO m2_semantic_unit_roots VALUES(?,?,?,?,?,?,?,NULL)",
                    (self.scope,root,rid,canonical_json(candidate),candidate_digest,event_id,seq),
                )
                return
            previous = payload.get("previous_record_id")
            prior = self._db.execute(
                "SELECT root_id FROM m2_semantic_unit_versions WHERE scope=? AND record_id=?",
                (self.scope, previous),
            ).fetchone()
            active = self._db.execute(
                "SELECT root_id,current_record_id FROM m2_semantic_unit_roots "
                "WHERE scope=? AND current_record_id=? AND retracted_reason IS NULL",
                (self.scope, previous),
            ).fetchone()
            if (event_id != f"m2:semantic-unit:{rid}" or prior is None or active is None
                    or candidate.envelope.derivation_refs.count(previous) != 1):
                raise SemanticUnitStoreError("revision identity/predecessor is invalid")
            root = prior["root_id"]
            if active["root_id"] != root:
                raise SemanticUnitStoreError("revision root projection is inconsistent")
            self._db.execute(
                "INSERT INTO m2_semantic_unit_versions VALUES(?,?,?,?,?,?,?,?,?)",
                (self.scope,rid,root,previous,kind,event_id,seq,event["payload_digest"],candidate_digest),
            )
            changed = self._db.execute(
                "UPDATE m2_semantic_unit_roots SET current_record_id=?,current_body_json=?,"
                "current_record_digest=?,current_event_id=?,current_sequence=? "
                "WHERE scope=? AND root_id=? AND current_record_id=? AND retracted_reason IS NULL",
                (rid,canonical_json(candidate),candidate_digest,event_id,seq,
                 self.scope,root,previous),
            ).rowcount
            if changed != 1:
                raise SemanticUnitStoreError("revision projection update lost its current predecessor")
            return
        if kind == "candidate_retracted":
            rid, reason = payload.get("record_id"), payload.get("reason")
            if event_id != f"m2:semantic-unit:{rid}:retracted" or not isinstance(reason,str) or not reason.strip():
                raise SemanticUnitStoreError("retraction identity/reason is invalid")
            changed = self._db.execute(
                "UPDATE m2_semantic_unit_roots SET retracted_reason=? "
                "WHERE scope=? AND current_record_id=? AND retracted_reason IS NULL",
                (reason,self.scope,rid),
            ).rowcount
            if changed != 1:
                raise SemanticUnitStoreError("only the current active candidate can be retracted")
            return
        raise SemanticUnitStoreError("unknown semantic-unit event kind")

    def _restore(self) -> None:
        if self._checkpoint_valid():
            return
        with self._memory.lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("DELETE FROM m2_semantic_unit_projection_checkpoint WHERE scope=?",
                                 (self.scope,))
                self._db.execute("DELETE FROM m2_semantic_unit_versions WHERE scope=?", (self.scope,))
                self._db.execute("DELETE FROM m2_semantic_unit_roots WHERE scope=?", (self.scope,))
                self._db.execute(
                    "INSERT OR IGNORE INTO m2_semantic_unit_projection_state(scope,generation) VALUES(?,0)",
                    (self.scope,),
                )
                previous_sequence = 0
                for event in self._memory.iter_domain_events(
                    event_type=EVENT_TYPE, scope=self.scope, page_size=self._replay_page_size
                ):
                    seq = event["sequence"]
                    if isinstance(seq,bool) or not isinstance(seq,int) or seq <= previous_sequence:
                        raise SemanticUnitStoreError("semantic-unit event sequence is not strictly increasing")
                    previous_sequence = seq
                    self._project_event(event)
                high_water = self._latest_sequence()
                self._write_checkpoint(high_water)
                self._db.execute("COMMIT")
            except (ZPCMError, ContractError, SemanticUnitStoreError):
                self._db.execute("ROLLBACK")
                raise
            except Exception as exc:
                self._db.execute("ROLLBACK")
                raise SemanticUnitStoreError(f"semantic-unit projection rebuild failed: {exc}") from exc

    def _ensure_current(self) -> None:
        if not self._checkpoint_valid():
            self._restore()

    def _version_row(self, record_id: str):
        return self._db.execute(
            "SELECT * FROM m2_semantic_unit_versions WHERE scope=? AND record_id=?",
            (self.scope,record_id),
        ).fetchone()

    @staticmethod
    def _receipt(row, *, replayed: bool) -> SemanticUnitReceipt:
        return SemanticUnitReceipt(
            row["event_id"],int(row["sequence"]),row["payload_digest"],
            row["record_digest"],replayed,
        )

    @property
    def candidates(self) -> dict[str, SemanticUnitCandidate]:
        """Compatibility materialization of all active current candidates; prefer iter_candidates."""
        return {root: candidate for root,candidate in self.iter_candidates()}

    def iter_candidates(self, *, limit: int = 64, after_root_id: str | None = None
                        ) -> Iterator[tuple[str, SemanticUnitCandidate]]:
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1 <= limit <= 4096:
            raise ValueError("limit must be an integer in [1, 4096]")
        self._ensure_current()
        sql = ("SELECT root_id,current_body_json FROM m2_semantic_unit_roots "
               "WHERE scope=? AND retracted_reason IS NULL")
        args: list[Any] = [self.scope]
        if after_root_id is not None:
            sql += " AND root_id>?"
            args.append(after_root_id)
        sql += " ORDER BY root_id LIMIT ?"
        args.append(limit)
        with self._memory.lock:
            rows = self._db.execute(sql,args).fetchall()
        for row in rows:
            yield row["root_id"],_candidate_from_dict(json.loads(row["current_body_json"]))

    @property
    def history(self) -> dict[str, SemanticUnitCandidate]:
        """Explicit full-history materialization for export and compatibility only."""
        result = {}
        for event in self._memory.iter_domain_events(
            event_type=EVENT_TYPE,scope=self.scope,page_size=self._replay_page_size
        ):
            payload = event["payload"]
            if payload.get("kind") in ("candidate_recorded","candidate_revised"):
                candidate = _candidate_from_dict(payload["body"])
                result[candidate.envelope.record_id] = candidate
        return result

    @property
    def retractions(self) -> dict[str, str]:
        self._ensure_current()
        with self._memory.lock:
            rows = self._db.execute(
                "SELECT current_record_id,retracted_reason FROM m2_semantic_unit_roots "
                "WHERE scope=? AND retracted_reason IS NOT NULL",(self.scope,)
            ).fetchall()
        return {row["current_record_id"]:row["retracted_reason"] for row in rows}

    @property
    def _root_by_current(self) -> dict[str,str]:
        self._ensure_current()
        with self._memory.lock:
            rows = self._db.execute(
                "SELECT root_id,current_record_id FROM m2_semantic_unit_roots WHERE scope=?",
                (self.scope,),
            ).fetchall()
        return {row["current_record_id"]:row["root_id"] for row in rows
                if row["retracted_reason"] is None}

    @property
    def _receipts(self) -> dict[str,SemanticUnitReceipt]:
        self._ensure_current()
        with self._memory.lock:
            rows = self._db.execute(
                "SELECT record_id,event_id,sequence,payload_digest,record_digest "
                "FROM m2_semantic_unit_versions WHERE scope=?",(self.scope,)
            ).fetchall()
        return {row["record_id"]:self._receipt(row,replayed=True) for row in rows}

    def _append_projected(self, *, event_id: str, payload: dict[str,Any],
                          action: str, candidate: SemanticUnitCandidate | None = None,
                          previous_id: str | None = None, record_id: str | None = None,
                          reason: str | None = None) -> SemanticUnitReceipt:
        self._ensure_current()
        with self._memory.lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                current = self._latest_sequence()
                seq,replayed = self._memory._append(event_id,EVENT_TYPE,self.scope,payload)
                if replayed:
                    row = self._version_row(candidate.envelope.record_id) if candidate else None
                    if action == "retract":
                        row = self._db.execute(
                            "SELECT v.* FROM m2_semantic_unit_versions v "
                            "WHERE v.scope=? AND v.record_id=? AND v.event_kind='candidate_recorded' "
                            "ORDER BY v.sequence LIMIT 1",(self.scope,record_id)
                        ).fetchone()
                    if row is None:
                        raise SemanticUnitStoreError("event exists without its matching M2 projection")
                    self.db_unused = None
                    self._db.execute("COMMIT")
                    return self._receipt(row,replayed=True)
                if action == "record":
                    assert candidate is not None
                    rid = candidate.envelope.record_id
                    body_digest = record_digest(candidate)
                    self._db.execute(
                        "INSERT INTO m2_semantic_unit_versions VALUES(?,?,?,?,?,?,?,?,?)",
                        (self.scope,rid,rid,None,"candidate_recorded",event_id,seq,
                         self._memory._append_digest(payload),body_digest),
                    )
                    self._db.execute(
                        "INSERT INTO m2_semantic_unit_roots VALUES(?,?,?,?,?,?,?,NULL)",
                        (self.scope,rid,rid,canonical_json(candidate),body_digest,event_id,seq),
                    )
                elif action == "revise":
                    assert candidate is not None and previous_id is not None
                    prior = self._version_row(previous_id)
                    active = self._db.execute(
                        "SELECT root_id FROM m2_semantic_unit_roots WHERE scope=? "
                        "AND current_record_id=? AND retracted_reason IS NULL",
                        (self.scope,previous_id),
                    ).fetchone()
                    if prior is None or active is None or prior["root_id"] != active["root_id"]:
                        raise SemanticUnitStoreError("revision predecessor is no longer current")
                    rid = candidate.envelope.record_id
                    body_digest = record_digest(candidate)
                    self._db.execute(
                        "INSERT INTO m2_semantic_unit_versions VALUES(?,?,?,?,?,?,?,?,?)",
                        (self.scope,rid,active["root_id"],previous_id,"candidate_revised",
                         event_id,seq,self._memory._append_digest(payload),body_digest),
                    )
                    changed = self._db.execute(
                        "UPDATE m2_semantic_unit_roots SET current_record_id=?,current_body_json=?,"
                        "current_record_digest=?,current_event_id=?,current_sequence=? "
                        "WHERE scope=? AND root_id=? AND current_record_id=? AND retracted_reason IS NULL",
                        (rid,canonical_json(candidate),body_digest,event_id,seq,
                         self.scope,active["root_id"],previous_id),
                    ).rowcount
                    if changed != 1:
                        raise SemanticUnitStoreError("revision lost a concurrent predecessor race")
                elif action == "retract":
                    assert record_id is not None and reason is not None
                    changed = self._db.execute(
                        "UPDATE m2_semantic_unit_roots SET retracted_reason=? "
                        "WHERE scope=? AND current_record_id=? AND retracted_reason IS NULL",
                        (reason,self.scope,record_id),
                    ).rowcount
                    if changed != 1:
                        raise SemanticUnitStoreError("retraction target is no longer current")
                else:
                    raise SemanticUnitStoreError("unknown projection action")
                self._write_checkpoint(seq)
                row = self._version_row(candidate.envelope.record_id) if candidate else self._version_row(record_id)
                self._db.execute("COMMIT")
                if row is None:
                    raise SemanticUnitStoreError("projection receipt row is missing after append")
                return self._receipt(row,replayed=False)
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def record_candidate(self, candidate: SemanticUnitCandidate) -> SemanticUnitReceipt:
        if not isinstance(candidate,SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock:
            self._verify_candidate(candidate)
            rid = candidate.envelope.record_id
            existing = self._version_row(rid)
            if existing is not None:
                if existing["event_kind"] != "candidate_recorded" or existing["record_digest"] != record_digest(candidate):
                    raise SemanticUnitStoreError("candidate record_id is immutable")
                return self._receipt(existing,replayed=True)
            payload,body_digest = self._payload("candidate_recorded",candidate)
            return self._append_projected(
                event_id=f"m2:semantic-unit:{rid}",payload=payload,action="record",candidate=candidate
            )

    def revise_candidate(self, previous_record_id: str,
                         candidate: SemanticUnitCandidate) -> SemanticUnitReceipt:
        if not isinstance(previous_record_id,str) or not previous_record_id.strip():
            raise ValueError("previous_record_id must be non-empty")
        if not isinstance(candidate,SemanticUnitCandidate):
            raise TypeError("candidate must be SemanticUnitCandidate")
        with self._lock:
            self._verify_candidate(candidate)
            rid = candidate.envelope.record_id
            existing = self._version_row(rid)
            if existing is not None:
                if (existing["event_kind"] != "candidate_revised"
                        or existing["predecessor_id"] != previous_record_id
                        or existing["record_digest"] != record_digest(candidate)
                        or candidate.envelope.derivation_refs.count(previous_record_id) != 1):
                    raise SemanticUnitStoreError("candidate revision identity/predecessor is immutable")
                return self._receipt(existing,replayed=True)
            prior = self._version_row(previous_record_id)
            if prior is None:
                raise SemanticUnitStoreError("revision predecessor does not exist")
            active = self._db.execute(
                "SELECT root_id FROM m2_semantic_unit_roots WHERE scope=? "
                "AND current_record_id=? AND retracted_reason IS NULL",
                (self.scope,previous_record_id),
            ).fetchone()
            if active is None or prior["root_id"] != active["root_id"]:
                raise SemanticUnitStoreError("only the current active candidate can be revised")
            if candidate.envelope.derivation_refs.count(previous_record_id) != 1:
                raise SemanticUnitStoreError("revision must cite predecessor exactly once in derivation_refs")
            if rid == previous_record_id or candidate.envelope.scope != self.scope:
                raise SemanticUnitStoreError("revision requires a new ID and matching scope")
            payload,_ = self._payload("candidate_revised",candidate,previous_record_id)
            return self._append_projected(
                event_id=f"m2:semantic-unit:{rid}",payload=payload,action="revise",
                candidate=candidate,previous_id=previous_record_id,
            )

    def retract_candidate(self, record_id: str, *, reason: str) -> SemanticUnitReceipt:
        if not isinstance(record_id,str) or not record_id.strip():
            raise ValueError("record_id must be non-empty")
        if not isinstance(reason,str) or not reason.strip():
            raise ValueError("reason must be non-empty")
        with self._lock:
            self._ensure_current()
            existing = self._db.execute(
                "SELECT * FROM m2_semantic_unit_roots WHERE scope=? AND current_record_id=?",
                (self.scope,record_id),
            ).fetchone()
            if existing is None:
                raise SemanticUnitStoreError("only the current candidate version can be retracted")
            if existing["retracted_reason"] is not None:
                if existing["retracted_reason"] != reason:
                    raise SemanticUnitStoreError("retraction reason conflicts with prior tombstone")
                event = self._memory.get_domain_event(
                    event_type=EVENT_TYPE,scope=self.scope,
                    event_id=f"m2:semantic-unit:{record_id}:retracted",
                )
                if event is None:
                    raise SemanticUnitStoreError("retraction receipt is missing from the event log")
                return SemanticUnitReceipt(event["event_id"],event["sequence"],
                    event["payload_digest"],existing["current_record_digest"],True)
            payload = {"schema_version":EVENT_SCHEMA,"kind":"candidate_retracted",
                       "record_id":record_id,"reason":reason}
            return self._append_projected(
                event_id=f"m2:semantic-unit:{record_id}:retracted",payload=payload,
                action="retract",record_id=record_id,reason=reason,
            )
