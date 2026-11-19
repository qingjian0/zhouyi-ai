"""ZPCM v0.1 bounded persistent memory projection; E09 remains protocol authority."""
from __future__ import annotations
import hashlib,json,sqlite3,threading
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterable,Iterator,Sequence

class ZPCMError(ValueError): pass
def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def digest(v): return hashlib.sha256(canonical(v).encode()).hexdigest()

class ZPCMMemory:
    SCHEMA_VERSION="zpcm-memory-v0.1"
    def __init__(self,path:str|Path, *, max_event_payload_bytes:int=1048576, max_page_bytes:int=4194304):
        if isinstance(max_event_payload_bytes,bool) or not isinstance(max_event_payload_bytes,int) or max_event_payload_bytes < 1:
            raise ZPCMError("max_event_payload_bytes must be a positive integer")
        if isinstance(max_page_bytes,bool) or not isinstance(max_page_bytes,int) or max_page_bytes < max_event_payload_bytes:
            raise ZPCMError("max_page_bytes must be >= max_event_payload_bytes")
        self.max_event_payload_bytes=max_event_payload_bytes; self.max_page_bytes=max_page_bytes
        self.path=str(path); self.lock=threading.RLock()
        self.db=sqlite3.connect(self.path,isolation_level=None,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        mode="WAL" if sqlite3.sqlite_version_info >= (3,51,3) else "DELETE"
        self.journal_mode=str(self.db.execute(f"PRAGMA journal_mode={mode}").fetchone()[0]).upper()
        self.db.execute("PRAGMA synchronous=FULL"); self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS memory_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,scope TEXT NOT NULL,payload_json TEXT NOT NULL,payload_digest TEXT NOT NULL,recorded_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS memory_events_type_scope_seq ON memory_events(event_type,scope,seq);
        CREATE TABLE IF NOT EXISTS memory_items(item_id TEXT PRIMARY KEY,item_type TEXT NOT NULL,scope TEXT NOT NULL,content_json TEXT NOT NULL,source_event_id TEXT NOT NULL,created_seq INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,FOREIGN KEY(source_event_id) REFERENCES memory_events(event_id));
        CREATE INDEX IF NOT EXISTS memory_items_scope_type_seq ON memory_items(scope,item_type,created_seq DESC);
        CREATE TABLE IF NOT EXISTS assertions(assertion_id TEXT PRIMARY KEY,subject_id TEXT NOT NULL,predicate TEXT NOT NULL,object_json TEXT NOT NULL,scope TEXT NOT NULL,valid_from TEXT,valid_to TEXT,status TEXT NOT NULL,source_event_id TEXT NOT NULL,created_seq INTEGER NOT NULL,FOREIGN KEY(source_event_id) REFERENCES memory_events(event_id));
        CREATE INDEX IF NOT EXISTS assertions_lookup ON assertions(scope,subject_id,predicate,status);
        CREATE TABLE IF NOT EXISTS e12a6_authorization_consumptions(
            receipt_id TEXT PRIMARY KEY,
            nonce TEXT UNIQUE NOT NULL,
            event_id TEXT UNIQUE NOT NULL,
            scope TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES memory_events(event_id)
        );
        CREATE TABLE IF NOT EXISTS e12a6_lifecycle_candidate_history (
            scope TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            candidate_version INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            event_id TEXT NOT NULL UNIQUE,
            event_kind TEXT NOT NULL,
            action_id TEXT,
            evidence_ids_json TEXT NOT NULL,
            PRIMARY KEY(scope,event_id),
            FOREIGN KEY(event_id) REFERENCES memory_events(event_id)
        );
        CREATE INDEX IF NOT EXISTS e12a6_candidate_history_lookup
            ON e12a6_lifecycle_candidate_history(scope,candidate_id,candidate_version,sequence);
        CREATE INDEX IF NOT EXISTS e12a6_candidate_history_action
            ON e12a6_lifecycle_candidate_history(scope,action_id);
        CREATE TABLE IF NOT EXISTS e12a6_lifecycle_candidate_history_meta (
            scope TEXT PRIMARY KEY,
            high_water_seq INTEGER NOT NULL,
            event_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS e12a6_lifecycle_checkpoints (
            scope TEXT PRIMARY KEY,
            checkpoint_schema TEXT NOT NULL,
            checkpoint_sequence INTEGER NOT NULL,
            event_count INTEGER NOT NULL,
            prefix_digest TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            snapshot_digest TEXT NOT NULL,
            created_at TEXT NOT NULL,
            pages_digest TEXT
        );
        CREATE TABLE IF NOT EXISTS e12a6_lifecycle_checkpoint_pages (
            scope TEXT NOT NULL,
            checkpoint_sequence INTEGER NOT NULL,
            page_kind TEXT NOT NULL,
            page_index INTEGER NOT NULL,
            page_json TEXT NOT NULL,
            page_digest TEXT NOT NULL,
            PRIMARY KEY(scope,checkpoint_sequence,page_kind,page_index)
        );
        """)
        checkpoint_columns = {
            row["name"] for row in self.db.execute("PRAGMA table_info(e12a6_lifecycle_checkpoints)")
        }
        if "pages_digest" not in checkpoint_columns:
            self.db.execute("ALTER TABLE e12a6_lifecycle_checkpoints ADD COLUMN pages_digest TEXT")
        # The event log is authoritative for every rebuildable projection.
        # Reject accidental mutation through the shared SQLite connection.
        self.db.executescript("""
        CREATE TRIGGER IF NOT EXISTS memory_events_reject_update
        BEFORE UPDATE ON memory_events
        BEGIN
            SELECT RAISE(ABORT, 'memory_events is append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS memory_events_reject_delete
        BEFORE DELETE ON memory_events
        BEGIN
            SELECT RAISE(ABORT, 'memory_events is append-only');
        END;
        """)
        self._rebuild_authorization_consumption_index()
        self._ensure_e12a6_candidate_history_projection()
        self._ensure_e12a6_current_state_projection()

    def _index_e12a6_candidate_event(self, scope: str, sequence: int,
                                     event_id: str, payload: dict[str, Any]) -> None:
        kind = payload.get("kind")
        body = payload.get("body")
        if not isinstance(body, dict):
            raise ZPCMError("lifecycle event body must be an object")
        candidate = None
        action_id = None
        evidence_ids = []
        if kind in {"candidate_registered", "revision_created"}:
            candidate = body.get("candidate")
            if isinstance(candidate, dict):
                evidence_ids = candidate.get("evidence_ids", [])
        elif kind == "action_applied":
            candidate = body.get("action")
            if isinstance(candidate, dict):
                action_id = candidate.get("action_id")
                evidence_ids = candidate.get("evidence_ids", [])
        elif kind == "authorization_consumed":
            candidate = body
            evidence_ids = body.get("evidence_refs", [])
        if not isinstance(candidate, dict):
            return
        candidate_id = candidate.get("candidate_id")
        candidate_version = candidate.get("version", candidate.get("candidate_version"))
        if (not isinstance(candidate_id, str) or not candidate_id.strip()
                or isinstance(candidate_version, bool) or not isinstance(candidate_version, int)
                or candidate_version < 1):
            return
        if not isinstance(evidence_ids, list) or any(not isinstance(item, str) for item in evidence_ids):
            raise ZPCMError("lifecycle candidate evidence references are malformed")
        self.db.execute(
            "INSERT INTO e12a6_lifecycle_candidate_history "
            "(scope,candidate_id,candidate_version,sequence,event_id,event_kind,action_id,evidence_ids_json) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (scope, candidate_id, candidate_version, sequence, event_id, kind,
             action_id, canonical(evidence_ids)),
        )

    def _rebuild_e12a6_candidate_history_scope(self, scope: str) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows = self.db.execute(
                "SELECT seq,event_id,payload_json,payload_digest FROM memory_events "
                "WHERE event_type='e12a6_lifecycle' AND scope=? ORDER BY seq",
                (scope,),
            )
            self.db.execute("DELETE FROM e12a6_lifecycle_candidate_history WHERE scope=?", (scope,))
            high_water = 0
            count = 0
            for row in rows:
                payload = json.loads(row["payload_json"])
                if digest(payload) != row["payload_digest"]:
                    raise ZPCMError(f"lifecycle event digest mismatch: {row['event_id']}")
                high_water = row["seq"]
                count += 1
                self._index_e12a6_candidate_event(scope, row["seq"], row["event_id"], payload)
            self.db.execute(
                "INSERT INTO e12a6_lifecycle_candidate_history_meta(scope,high_water_seq,event_count) "
                "VALUES(?,?,?) ON CONFLICT(scope) DO UPDATE SET "
                "high_water_seq=excluded.high_water_seq,event_count=excluded.event_count",
                (scope, high_water, count),
            )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def _ensure_e12a6_candidate_history_projection(self) -> None:
        scopes = [row["scope"] for row in self.db.execute(
            "SELECT DISTINCT scope FROM memory_events WHERE event_type='e12a6_lifecycle'"
        )]
        for scope in scopes:
            current = self.db.execute(
                "SELECT COUNT(*) AS n,COALESCE(MAX(seq),0) AS high_water FROM memory_events "
                "WHERE event_type='e12a6_lifecycle' AND scope=?",
                (scope,),
            ).fetchone()
            meta = self.db.execute(
                "SELECT high_water_seq,event_count FROM e12a6_lifecycle_candidate_history_meta WHERE scope=?",
                (scope,),
            ).fetchone()
            if (meta is None or meta["event_count"] != current["n"]
                    or meta["high_water_seq"] != current["high_water"]):
                self._rebuild_e12a6_candidate_history_scope(scope)

    def iter_lifecycle_candidate_history(
        self, *, scope: str, candidate_id: str, candidate_version: int | None = None,
        after_sequence: int = 0, limit: int = 100, max_page_bytes: int = 4 * 1024 * 1024,
    ) -> list[dict[str, Any]]:
        """Read one deterministic candidate-history page within count and byte bounds."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ZPCMError("candidate_id must be non-empty")
        if candidate_version is not None and (
            isinstance(candidate_version, bool) or not isinstance(candidate_version, int)
            or candidate_version < 1
        ):
            raise ZPCMError("candidate_version must be a positive integer")
        if isinstance(after_sequence, bool) or not isinstance(after_sequence, int) or after_sequence < 0:
            raise ZPCMError("after_sequence must be a non-negative integer")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ZPCMError("limit must be between 1 and 1000")
        if isinstance(max_page_bytes, bool) or not isinstance(max_page_bytes, int) or max_page_bytes < 1:
            raise ZPCMError("max_page_bytes must be positive")
        query = (
            "SELECT e.seq,e.event_id,e.event_type,e.scope,"
            "length(CAST(e.payload_json AS BLOB)) AS payload_bytes,"
            "e.payload_digest,e.recorded_at "
            "FROM e12a6_lifecycle_candidate_history h "
            "JOIN memory_events e ON e.event_id=h.event_id "
            "WHERE h.scope=? AND h.candidate_id=? AND h.sequence>? "
        )
        args: list[Any] = [scope, candidate_id, after_sequence]
        if candidate_version is not None:
            query += "AND h.candidate_version=? "
            args.append(candidate_version)
        query += "ORDER BY h.sequence LIMIT ?"
        args.append(limit)
        with self.lock:
            rows = self.db.execute(query, tuple(args)).fetchall()
        selected = []
        used_bytes = 0
        for row in rows:
            size = int(row["payload_bytes"])
            if size > self.max_event_payload_bytes:
                raise ZPCMError(f"persisted event payload exceeds max_event_payload_bytes: {row['event_id']}")
            if used_bytes + size > max_page_bytes:
                if not selected:
                    raise ZPCMError("candidate history page cannot make progress within max_page_bytes")
                break
            selected.append(row)
            used_bytes += size
        results = []
        for row in selected:
            with self.lock:
                raw = self.db.execute(
                    "SELECT payload_json FROM memory_events WHERE seq=? AND event_id=?",
                    (row["seq"], row["event_id"]),
                ).fetchone()
            if raw is None:
                raise ZPCMError("candidate history event disappeared during page read")
            payload = json.loads(raw["payload_json"])
            if digest(payload) != row["payload_digest"]:
                raise ZPCMError(f"lifecycle event digest mismatch: {row['event_id']}")
            results.append({
                "sequence": row["seq"], "event_id": row["event_id"],
                "event_type": row["event_type"], "scope": row["scope"],
                "payload": payload, "payload_digest": row["payload_digest"],
                "recorded_at": row["recorded_at"],
            })
        return results

    def get_authorization_consumption(
        self, *, receipt_id: str | None = None, nonce: str | None = None,
    ) -> dict[str, Any] | None:
        """Look up one receipt/nonce binding through the SQLite uniqueness index."""
        if (receipt_id is None) == (nonce is None):
            raise ZPCMError("provide exactly one of receipt_id or nonce")
        value = receipt_id if receipt_id is not None else nonce
        if not isinstance(value, str) or not value.strip():
            raise ZPCMError("receipt_id or nonce must be non-empty")
        column = "receipt_id" if receipt_id is not None else "nonce"
        with self.lock:
            row = self.db.execute(
                f"SELECT event_id,scope FROM e12a6_authorization_consumptions WHERE {column}=?",
                (value,),
            ).fetchone()
        if row is None:
            return None
        event = self.get_domain_event(
            event_type="e12a6_lifecycle", scope=row["scope"], event_id=row["event_id"],
        )
        if event is None or event["payload"].get("kind") != "authorization_consumed":
            raise ZPCMError("authorization consumption index points to a missing or invalid event")
        body = event["payload"].get("body")
        if not isinstance(body, dict):
            raise ZPCMError("authorization consumption body must be an object")
        return {"event_id": event["event_id"], "sequence": event["sequence"], "body": body}

    def iter_authorization_consumptions(
        self, *, scope: str, page_size: int = 128,
    ) -> Iterator[dict[str, Any]]:
        """Keyset-page scoped authorization bindings with a stable high-water mark."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 4096:
            raise ZPCMError("page_size must be an integer in [1, 4096]")
        with self.lock:
            high_water = self.db.execute(
                "SELECT COALESCE(MAX(e.seq),0) FROM e12a6_authorization_consumptions a "
                "JOIN memory_events e ON e.event_id=a.event_id "
                "WHERE a.scope=? AND e.event_type='e12a6_lifecycle'",
                (scope,),
            ).fetchone()[0]
        cursor = 0
        while cursor < high_water:
            with self.lock:
                rows = self.db.execute(
                    "SELECT e.seq,e.event_id,e.payload_json,e.payload_digest "
                    "FROM e12a6_authorization_consumptions a "
                    "JOIN memory_events e ON e.event_id=a.event_id "
                    "WHERE a.scope=? AND e.event_type='e12a6_lifecycle' "
                    "AND e.seq>? AND e.seq<=? ORDER BY e.seq LIMIT ?",
                    (scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                payload = json.loads(row["payload_json"])
                if digest(payload) != row["payload_digest"]:
                    raise ZPCMError(f"authorization event digest mismatch: {row['event_id']}")
                if payload.get("kind") != "authorization_consumed" or not isinstance(payload.get("body"), dict):
                    raise ZPCMError("authorization consumption index is inconsistent")
                cursor = row["seq"]
                yield payload["body"]

    def iter_candidate_authorization_consumptions(
        self, *, scope: str, candidate_id: str, candidate_version: int,
        page_size: int = 128,
    ) -> Iterator[dict[str, Any]]:
        """Keyset-page authorization events for one candidate version."""
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 1000:
            raise ZPCMError("page_size must be an integer in [1, 1000]")
        cursor = 0
        while True:
            page = self.iter_lifecycle_candidate_history(
                scope=scope, candidate_id=candidate_id,
                candidate_version=candidate_version, after_sequence=cursor,
                limit=page_size,
            )
            if not page:
                return
            for event in page:
                if event["payload"].get("kind") == "authorization_consumed":
                    yield event["payload"]["body"]
            cursor = page[-1]["sequence"]

    def _ensure_e12a6_current_state_projection(self) -> None:
        """Maintain rebuildable, queryable E12-A6 current-state rows from the event log.

        The append-only memory_events table remains authoritative. These tables
        are derived projections and are updated by SQLite triggers in the same
        transaction as each lifecycle event append.
        """
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS e12a6_current_state_projection_meta(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                schema_version TEXT NOT NULL,
                initialized_through_seq INTEGER NOT NULL,
                initialized_event_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS e12a6_candidate_state_projection(
                scope TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                candidate_version INTEGER NOT NULL,
                candidate_json TEXT NOT NULL,
                source_seq INTEGER NOT NULL,
                PRIMARY KEY(scope,candidate_id,candidate_version)
            );
            CREATE INDEX IF NOT EXISTS e12a6_candidate_state_by_scope_seq
                ON e12a6_candidate_state_projection(scope,source_seq);
            CREATE TABLE IF NOT EXISTS e12a6_evidence_state_projection(
                scope TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                source_seq INTEGER NOT NULL,
                PRIMARY KEY(scope,evidence_id)
            );
            CREATE INDEX IF NOT EXISTS e12a6_evidence_state_by_scope_seq
                ON e12a6_evidence_state_projection(scope,source_seq);
            CREATE TABLE IF NOT EXISTS e12a6_action_state_projection(
                scope TEXT NOT NULL,
                action_id TEXT NOT NULL,
                candidate_id TEXT,
                candidate_version INTEGER,
                action_json TEXT NOT NULL,
                source_seq INTEGER NOT NULL,
                PRIMARY KEY(scope,action_id)
            );
            CREATE INDEX IF NOT EXISTS e12a6_action_state_by_candidate
                ON e12a6_action_state_projection(scope,candidate_id,candidate_version,source_seq);
            CREATE INDEX IF NOT EXISTS e12a6_action_state_by_scope_seq
                ON e12a6_action_state_projection(scope,source_seq);
            CREATE TRIGGER IF NOT EXISTS e12a6_candidate_state_insert
            AFTER INSERT ON memory_events
            WHEN NEW.event_type='e12a6_lifecycle'
             AND json_extract(NEW.payload_json,'$.kind') IN ('candidate_registered','revision_created')
            BEGIN
                INSERT INTO e12a6_candidate_state_projection(
                    scope,candidate_id,candidate_version,candidate_json,source_seq
                )
                SELECT NEW.scope,
                    json_extract(NEW.payload_json,'$.body.candidate.candidate_id'),
                    json_extract(NEW.payload_json,'$.body.candidate.version'),
                    json_extract(NEW.payload_json,'$.body.candidate'),NEW.seq
                WHERE json_extract(NEW.payload_json,'$.body.candidate.candidate_id') IS NOT NULL
                ON CONFLICT(scope,candidate_id,candidate_version) DO UPDATE SET
                    candidate_json=excluded.candidate_json,source_seq=excluded.source_seq;
            END;
            CREATE TRIGGER IF NOT EXISTS e12a6_evidence_state_insert
            AFTER INSERT ON memory_events
            WHEN NEW.event_type='e12a6_lifecycle'
             AND json_extract(NEW.payload_json,'$.kind')='evidence_registered'
            BEGIN
                INSERT INTO e12a6_evidence_state_projection(
                    scope,evidence_id,evidence_json,source_seq
                )
                SELECT NEW.scope,
                    json_extract(NEW.payload_json,'$.body.evidence.evidence_id'),
                    json_extract(NEW.payload_json,'$.body.evidence'),NEW.seq
                WHERE json_extract(NEW.payload_json,'$.body.evidence.evidence_id') IS NOT NULL
                ON CONFLICT(scope,evidence_id) DO UPDATE SET
                    evidence_json=excluded.evidence_json,source_seq=excluded.source_seq;
            END;
            CREATE TRIGGER IF NOT EXISTS e12a6_action_state_insert
            AFTER INSERT ON memory_events
            WHEN NEW.event_type='e12a6_lifecycle'
             AND json_extract(NEW.payload_json,'$.kind')='action_applied'
            BEGIN
                INSERT INTO e12a6_action_state_projection(
                    scope,action_id,candidate_id,candidate_version,action_json,source_seq
                )
                SELECT NEW.scope,
                    json_extract(NEW.payload_json,'$.body.action.action_id'),
                    json_extract(NEW.payload_json,'$.body.action.candidate_id'),
                    json_extract(NEW.payload_json,'$.body.action.candidate_version'),
                    json_extract(NEW.payload_json,'$.body.action'),NEW.seq
                WHERE json_extract(NEW.payload_json,'$.body.action.action_id') IS NOT NULL
                ON CONFLICT(scope,action_id) DO UPDATE SET
                    candidate_id=excluded.candidate_id,
                    candidate_version=excluded.candidate_version,
                    action_json=excluded.action_json,source_seq=excluded.source_seq;
                UPDATE e12a6_candidate_state_projection
                SET candidate_json=json_set(
                        candidate_json,'$.state',
                        json_extract(NEW.payload_json,'$.body.action.to_state')
                    ),
                    source_seq=NEW.seq
                WHERE scope=NEW.scope
                  AND candidate_id=json_extract(NEW.payload_json,'$.body.action.candidate_id')
                  AND candidate_version=json_extract(NEW.payload_json,'$.body.action.candidate_version')
                  AND json_extract(NEW.payload_json,'$.body.action.to_state') IS NOT NULL;
            END;
            CREATE TRIGGER IF NOT EXISTS e12a6_current_state_meta_insert
            AFTER INSERT ON memory_events
            WHEN NEW.event_type='e12a6_lifecycle'
            BEGIN
                INSERT INTO e12a6_current_state_projection_meta(
                    singleton,schema_version,initialized_through_seq,initialized_event_count
                ) VALUES(1,'e12a6-current-state-v1',NEW.seq,1)
                ON CONFLICT(singleton) DO UPDATE SET
                    initialized_through_seq=MAX(initialized_through_seq,NEW.seq),
                    initialized_event_count=initialized_event_count+1;
            END;
            """)
            action_projection_migrated = False
            action_columns = {
                row["name"]: row for row in self.db.execute(
                    "PRAGMA table_info(e12a6_action_state_projection)"
                )
            }
            if (action_columns.get("candidate_id") is not None
                    and action_columns["candidate_id"]["notnull"]
                    or action_columns.get("candidate_version") is not None
                    and action_columns["candidate_version"]["notnull"]):
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    self.db.execute("DROP TRIGGER IF EXISTS e12a6_action_state_insert")
                    self.db.execute(
                        "ALTER TABLE e12a6_action_state_projection "
                        "RENAME TO e12a6_action_state_projection_legacy"
                    )
                    self.db.execute("""
                        CREATE TABLE e12a6_action_state_projection(
                            scope TEXT NOT NULL,
                            action_id TEXT NOT NULL,
                            candidate_id TEXT,
                            candidate_version INTEGER,
                            action_json TEXT NOT NULL,
                            source_seq INTEGER NOT NULL,
                            PRIMARY KEY(scope,action_id)
                        )
                    """)
                    self.db.execute("""
                        INSERT INTO e12a6_action_state_projection(
                            scope,action_id,candidate_id,candidate_version,action_json,source_seq
                        )
                        SELECT scope,action_id,candidate_id,candidate_version,action_json,source_seq
                        FROM e12a6_action_state_projection_legacy
                    """)
                    self.db.execute("DROP TABLE e12a6_action_state_projection_legacy")
                    self.db.execute(
                        "CREATE INDEX e12a6_action_state_by_candidate "
                        "ON e12a6_action_state_projection(scope,candidate_id,candidate_version,source_seq)"
                    )
                    self.db.execute(
                        "CREATE INDEX e12a6_action_state_by_scope_seq "
                        "ON e12a6_action_state_projection(scope,source_seq)"
                    )
                    self.db.execute("""
                        CREATE TRIGGER e12a6_action_state_insert
                        AFTER INSERT ON memory_events
                        WHEN NEW.event_type='e12a6_lifecycle'
                         AND json_extract(NEW.payload_json,'$.kind')='action_applied'
                        BEGIN
                            INSERT INTO e12a6_action_state_projection(
                                scope,action_id,candidate_id,candidate_version,action_json,source_seq
                            )
                            SELECT NEW.scope,
                                json_extract(NEW.payload_json,'$.body.action.action_id'),
                                json_extract(NEW.payload_json,'$.body.action.candidate_id'),
                                json_extract(NEW.payload_json,'$.body.action.candidate_version'),
                                json_extract(NEW.payload_json,'$.body.action'),NEW.seq
                            WHERE json_extract(NEW.payload_json,'$.body.action.action_id') IS NOT NULL
                            ON CONFLICT(scope,action_id) DO UPDATE SET
                                candidate_id=excluded.candidate_id,
                                candidate_version=excluded.candidate_version,
                                action_json=excluded.action_json,source_seq=excluded.source_seq;
                            UPDATE e12a6_candidate_state_projection
                            SET candidate_json=json_set(
                                    candidate_json,'$.state',
                                    json_extract(NEW.payload_json,'$.body.action.to_state')
                                ),
                                source_seq=NEW.seq
                            WHERE scope=NEW.scope
                              AND candidate_id=json_extract(NEW.payload_json,'$.body.action.candidate_id')
                              AND candidate_version=json_extract(NEW.payload_json,'$.body.action.candidate_version')
                              AND json_extract(NEW.payload_json,'$.body.action.to_state') IS NOT NULL;
                        END
                    """)
                    self.db.execute("COMMIT")
                    action_projection_migrated = True
                except Exception:
                    self.db.execute("ROLLBACK")
                    raise
            meta = self.db.execute(
                "SELECT schema_version,initialized_through_seq,initialized_event_count "
                "FROM e12a6_current_state_projection_meta WHERE singleton=1"
            ).fetchone()
            current = self.db.execute(
                "SELECT COUNT(*) AS event_count,COALESCE(MAX(seq),0) AS high_water "
                "FROM memory_events WHERE event_type='e12a6_lifecycle'"
            ).fetchone()

            # High-water metadata alone cannot detect deleted/replaced projection
            # rows when the event count is unchanged. Compare the identity keysets
            # against the authoritative log before accepting the projection.
            candidate_keys_match = self.db.execute("""
                WITH expected AS (
                    SELECT scope,
                        json_extract(payload_json,'$.body.candidate.candidate_id') AS candidate_id,
                        json_extract(payload_json,'$.body.candidate.version') AS candidate_version
                    FROM memory_events
                    WHERE event_type='e12a6_lifecycle'
                      AND json_extract(payload_json,'$.kind') IN ('candidate_registered','revision_created')
                      AND json_extract(payload_json,'$.body.candidate.candidate_id') IS NOT NULL
                    GROUP BY scope,candidate_id,candidate_version
                )
                SELECT
                    EXISTS(
                        SELECT scope,candidate_id,candidate_version FROM expected
                        EXCEPT
                        SELECT scope,candidate_id,candidate_version FROM e12a6_candidate_state_projection
                    ) OR EXISTS(
                        SELECT scope,candidate_id,candidate_version FROM e12a6_candidate_state_projection
                        EXCEPT
                        SELECT scope,candidate_id,candidate_version FROM expected
                    )
            """).fetchone()[0] == 0
            evidence_keys_match = self.db.execute("""
                WITH expected AS (
                    SELECT scope,
                        json_extract(payload_json,'$.body.evidence.evidence_id') AS evidence_id
                    FROM memory_events
                    WHERE event_type='e12a6_lifecycle'
                      AND json_extract(payload_json,'$.kind')='evidence_registered'
                      AND json_extract(payload_json,'$.body.evidence.evidence_id') IS NOT NULL
                    GROUP BY scope,evidence_id
                )
                SELECT
                    EXISTS(
                        SELECT scope,evidence_id FROM expected
                        EXCEPT
                        SELECT scope,evidence_id FROM e12a6_evidence_state_projection
                    ) OR EXISTS(
                        SELECT scope,evidence_id FROM e12a6_evidence_state_projection
                        EXCEPT
                        SELECT scope,evidence_id FROM expected
                    )
            """).fetchone()[0] == 0
            action_keys_match = self.db.execute("""
                WITH expected AS (
                    SELECT scope,
                        json_extract(payload_json,'$.body.action.action_id') AS action_id
                    FROM memory_events
                    WHERE event_type='e12a6_lifecycle'
                      AND json_extract(payload_json,'$.kind')='action_applied'
                      AND json_extract(payload_json,'$.body.action.action_id') IS NOT NULL
                    GROUP BY scope,action_id
                )
                SELECT
                    EXISTS(
                        SELECT scope,action_id FROM expected
                        EXCEPT
                        SELECT scope,action_id FROM e12a6_action_state_projection
                    ) OR EXISTS(
                        SELECT scope,action_id FROM e12a6_action_state_projection
                        EXCEPT
                        SELECT scope,action_id FROM expected
                    )
            """).fetchone()[0] == 0

            if (not action_projection_migrated
                    and meta is not None
                    and meta["schema_version"] == "e12a6-current-state-v1"
                    and meta["initialized_event_count"] == current["event_count"]
                    and meta["initialized_through_seq"] == current["high_water"]
                    and candidate_keys_match
                    and evidence_keys_match
                    and action_keys_match):
                return
            self.rebuild_e12a6_current_state_projection()

    def rebuild_e12a6_current_state_projection(self) -> None:
        """Atomically rebuild derived lifecycle state after digest-verifying the event log."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                scopes = [row["scope"] for row in self.db.execute(
                    "SELECT DISTINCT scope FROM memory_events WHERE event_type='e12a6_lifecycle'"
                )]
                for scope in scopes:
                    for _event in self.iter_domain_events(
                        event_type="e12a6_lifecycle", scope=scope, page_size=64,
                    ):
                        pass
                self.db.execute("DELETE FROM e12a6_candidate_state_projection")
                self.db.execute("DELETE FROM e12a6_evidence_state_projection")
                self.db.execute("DELETE FROM e12a6_action_state_projection")
                self.db.execute("""
                    INSERT OR REPLACE INTO e12a6_candidate_state_projection(
                        scope,candidate_id,candidate_version,candidate_json,source_seq
                    )
                    SELECT scope,
                        json_extract(payload_json,'$.body.candidate.candidate_id'),
                        json_extract(payload_json,'$.body.candidate.version'),
                        json_extract(payload_json,'$.body.candidate'),seq
                    FROM memory_events
                    WHERE event_type='e12a6_lifecycle'
                      AND json_extract(payload_json,'$.kind') IN ('candidate_registered','revision_created')
                      AND json_extract(payload_json,'$.body.candidate.candidate_id') IS NOT NULL
                    ORDER BY seq
                """)
                self.db.execute("""
                    INSERT OR REPLACE INTO e12a6_evidence_state_projection(
                        scope,evidence_id,evidence_json,source_seq
                    )
                    SELECT scope,json_extract(payload_json,'$.body.evidence.evidence_id'),
                        json_extract(payload_json,'$.body.evidence'),seq
                    FROM memory_events
                    WHERE event_type='e12a6_lifecycle'
                      AND json_extract(payload_json,'$.kind')='evidence_registered'
                      AND json_extract(payload_json,'$.body.evidence.evidence_id') IS NOT NULL
                    ORDER BY seq
                """)
                self.db.execute("""
                    INSERT OR REPLACE INTO e12a6_action_state_projection(
                        scope,action_id,candidate_id,candidate_version,action_json,source_seq
                    )
                    SELECT scope,
                        json_extract(payload_json,'$.body.action.action_id'),
                        json_extract(payload_json,'$.body.action.candidate_id'),
                        json_extract(payload_json,'$.body.action.candidate_version'),
                        json_extract(payload_json,'$.body.action'),seq
                    FROM memory_events
                    WHERE event_type='e12a6_lifecycle'
                      AND json_extract(payload_json,'$.kind')='action_applied'
                      AND json_extract(payload_json,'$.body.action.action_id') IS NOT NULL
                    ORDER BY seq
                """)
                self.db.execute("""
                    UPDATE e12a6_candidate_state_projection AS c
                    SET candidate_json=json_set(
                            c.candidate_json,'$.state',
                            (SELECT json_extract(e.payload_json,'$.body.action.to_state')
                             FROM memory_events e
                             WHERE e.event_type='e12a6_lifecycle'
                               AND e.scope=c.scope
                               AND json_extract(e.payload_json,'$.kind')='action_applied'
                               AND json_extract(e.payload_json,'$.body.action.candidate_id')=c.candidate_id
                               AND json_extract(e.payload_json,'$.body.action.candidate_version')=c.candidate_version
                               AND json_extract(e.payload_json,'$.body.action.to_state') IS NOT NULL
                             ORDER BY e.seq DESC LIMIT 1)
                        ),
                        source_seq=MAX(
                            c.source_seq,
                            COALESCE((SELECT MAX(e.seq) FROM memory_events e
                             WHERE e.event_type='e12a6_lifecycle'
                               AND e.scope=c.scope
                               AND json_extract(e.payload_json,'$.kind')='action_applied'
                               AND json_extract(e.payload_json,'$.body.action.candidate_id')=c.candidate_id
                               AND json_extract(e.payload_json,'$.body.action.candidate_version')=c.candidate_version
                               AND json_extract(e.payload_json,'$.body.action.to_state') IS NOT NULL),0)
                        )
                    WHERE EXISTS(
                        SELECT 1 FROM memory_events e
                        WHERE e.event_type='e12a6_lifecycle' AND e.scope=c.scope
                          AND json_extract(e.payload_json,'$.kind')='action_applied'
                          AND json_extract(e.payload_json,'$.body.action.candidate_id')=c.candidate_id
                          AND json_extract(e.payload_json,'$.body.action.candidate_version')=c.candidate_version
                          AND json_extract(e.payload_json,'$.body.action.to_state') IS NOT NULL
                    )
                """)
                high_water = int(self.db.execute(
                    "SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type='e12a6_lifecycle'"
                ).fetchone()[0])
                event_count = int(self.db.execute(
                    "SELECT COUNT(*) FROM memory_events WHERE event_type='e12a6_lifecycle'"
                ).fetchone()[0])
                self.db.execute(
                    "INSERT OR REPLACE INTO e12a6_current_state_projection_meta("
                    "singleton,schema_version,initialized_through_seq,initialized_event_count) "
                    "VALUES(1,'e12a6-current-state-v1',?,?)",
                    (high_water,event_count),
                )
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def verify_e12a6_current_state_projection(self, *, scope: str) -> dict[str, Any]:
        """Compare scoped SQL projections with a digest-verified event-log fold.

        Event payload verification is streamed in bounded pages. Projection
        comparisons are performed by SQLite set differences, avoiding Python
        materialization of candidate/evidence/action collections.
        """
        if not isinstance(scope,str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        verified_events=0
        for _event in self.iter_domain_events(event_type="e12a6_lifecycle", scope=scope, page_size=64):
            verified_events+=1

        candidate_cte = """
        WITH candidate_events AS (
            SELECT scope,
                json_extract(payload_json,'$.body.candidate.candidate_id') AS candidate_id,
                json_extract(payload_json,'$.body.candidate.version') AS candidate_version,
                json_extract(payload_json,'$.body.candidate') AS candidate_json,
                seq,
                ROW_NUMBER() OVER (
                    PARTITION BY scope,
                    json_extract(payload_json,'$.body.candidate.candidate_id'),
                    json_extract(payload_json,'$.body.candidate.version')
                    ORDER BY seq DESC
                ) AS rn
            FROM memory_events
            WHERE event_type='e12a6_lifecycle' AND scope=?
              AND json_extract(payload_json,'$.kind') IN ('candidate_registered','revision_created')
        ),
        latest_actions AS (
            SELECT scope,
                json_extract(payload_json,'$.body.action.candidate_id') AS candidate_id,
                json_extract(payload_json,'$.body.action.candidate_version') AS candidate_version,
                json_extract(payload_json,'$.body.action.to_state') AS to_state,
                seq,
                ROW_NUMBER() OVER (
                    PARTITION BY scope,
                    json_extract(payload_json,'$.body.action.candidate_id'),
                    json_extract(payload_json,'$.body.action.candidate_version')
                    ORDER BY seq DESC
                ) AS rn
            FROM memory_events
            WHERE event_type='e12a6_lifecycle' AND scope=?
              AND json_extract(payload_json,'$.kind')='action_applied'
              AND json_extract(payload_json,'$.body.action.to_state') IS NOT NULL
        ),
        expected AS (
            SELECT c.scope,c.candidate_id,c.candidate_version,
                CASE WHEN a.to_state IS NULL THEN c.candidate_json
                     ELSE json_set(c.candidate_json,'$.state',a.to_state) END AS candidate_json,
                MAX(c.seq,COALESCE(a.seq,0)) AS source_seq
            FROM candidate_events c
            LEFT JOIN latest_actions a
              ON a.scope=c.scope AND a.candidate_id=c.candidate_id
             AND a.candidate_version=c.candidate_version AND a.rn=1
            WHERE c.rn=1
        )
        """
        def candidate_diff(reverse):
            expected_side = "SELECT scope,candidate_id,candidate_version,candidate_json,source_seq FROM expected"
            actual_side = "SELECT scope,candidate_id,candidate_version,candidate_json,source_seq FROM e12a6_candidate_state_projection WHERE scope=?"
            return candidate_cte + "SELECT COUNT(*) FROM (" + (
                actual_side + " EXCEPT " + expected_side if reverse
                else expected_side + " EXCEPT " + actual_side
            ) + ")"
        with self.lock:
            candidate_missing = int(self.db.execute(candidate_diff(False),(scope,scope,scope)).fetchone()[0])
            candidate_unexpected = int(self.db.execute(candidate_diff(True),(scope,scope,scope)).fetchone()[0])

        evidence_cte = """
        WITH ranked AS (
            SELECT scope,
                json_extract(payload_json,'$.body.evidence.evidence_id') AS evidence_id,
                json_extract(payload_json,'$.body.evidence') AS evidence_json,
                seq,
                ROW_NUMBER() OVER (
                    PARTITION BY scope,json_extract(payload_json,'$.body.evidence.evidence_id')
                    ORDER BY seq DESC
                ) AS rn
            FROM memory_events
            WHERE event_type='e12a6_lifecycle' AND scope=?
              AND json_extract(payload_json,'$.kind')='evidence_registered'
        ), expected AS (
            SELECT scope,evidence_id,evidence_json,seq AS source_seq FROM ranked WHERE rn=1
        )
        """
        def evidence_diff(reverse):
            expected_side = "SELECT scope,evidence_id,evidence_json,source_seq FROM expected"
            actual_side = "SELECT scope,evidence_id,evidence_json,source_seq FROM e12a6_evidence_state_projection WHERE scope=?"
            return evidence_cte + "SELECT COUNT(*) FROM (" + (
                actual_side + " EXCEPT " + expected_side if reverse
                else expected_side + " EXCEPT " + actual_side
            ) + ")"
        with self.lock:
            evidence_missing = int(self.db.execute(evidence_diff(False),(scope,scope)).fetchone()[0])
            evidence_unexpected = int(self.db.execute(evidence_diff(True),(scope,scope)).fetchone()[0])

        action_cte = """
        WITH ranked AS (
            SELECT scope,
                json_extract(payload_json,'$.body.action.action_id') AS action_id,
                json_extract(payload_json,'$.body.action.candidate_id') AS candidate_id,
                json_extract(payload_json,'$.body.action.candidate_version') AS candidate_version,
                json_extract(payload_json,'$.body.action') AS action_json,
                seq,
                ROW_NUMBER() OVER (
                    PARTITION BY scope,json_extract(payload_json,'$.body.action.action_id')
                    ORDER BY seq DESC
                ) AS rn
            FROM memory_events
            WHERE event_type='e12a6_lifecycle' AND scope=?
              AND json_extract(payload_json,'$.kind')='action_applied'
        ), expected AS (
            SELECT scope,action_id,candidate_id,candidate_version,action_json,seq AS source_seq
            FROM ranked WHERE rn=1
        )
        """
        def action_diff(reverse):
            expected_side = "SELECT scope,action_id,candidate_id,candidate_version,action_json,source_seq FROM expected"
            actual_side = "SELECT scope,action_id,candidate_id,candidate_version,action_json,source_seq FROM e12a6_action_state_projection WHERE scope=?"
            return action_cte + "SELECT COUNT(*) FROM (" + (
                actual_side + " EXCEPT " + expected_side if reverse
                else expected_side + " EXCEPT " + actual_side
            ) + ")"
        with self.lock:
            action_missing = int(self.db.execute(action_diff(False),(scope,scope)).fetchone()[0])
            action_unexpected = int(self.db.execute(action_diff(True),(scope,scope)).fetchone()[0])

        counts = {
            "candidate_missing": candidate_missing,
            "candidate_unexpected": candidate_unexpected,
            "evidence_missing": evidence_missing,
            "evidence_unexpected": evidence_unexpected,
            "action_missing": action_missing,
            "action_unexpected": action_unexpected,
        }
        return {
            "scope": scope,
            "verified_event_count": verified_events,
            **counts,
            "ok": all(value == 0 for value in counts.values()),
        }

    def get_lifecycle_candidate_projection(
        self, *, scope: str, candidate_id: str, candidate_version: int,
    ) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute(
                "SELECT candidate_json,source_seq FROM e12a6_candidate_state_projection "
                "WHERE scope=? AND candidate_id=? AND candidate_version=?",
                (scope,candidate_id,candidate_version),
            ).fetchone()
        if row is None:
            return None
        return {"candidate":json.loads(row["candidate_json"]),"source_seq":int(row["source_seq"])}

    def get_lifecycle_evidence_projection(
        self, *, scope: str, evidence_id: str,
    ) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute(
                "SELECT evidence_json,source_seq FROM e12a6_evidence_state_projection "
                "WHERE scope=? AND evidence_id=?",(scope,evidence_id),
            ).fetchone()
        if row is None:
            return None
        return {"evidence":json.loads(row["evidence_json"]),"source_seq":int(row["source_seq"])}

    def get_lifecycle_action_projection(
        self, *, scope: str, action_id: str,
    ) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute(
                "SELECT action_json,source_seq FROM e12a6_action_state_projection "
                "WHERE scope=? AND action_id=?",(scope,action_id),
            ).fetchone()
        if row is None:
            return None
        return {"action":json.loads(row["action_json"]),"source_seq":int(row["source_seq"])}

    def lifecycle_state_projection_counts(self, *, scope: str) -> dict[str, int]:
        counts={}
        with self.lock:
            for kind,table in (
                ("candidates","e12a6_candidate_state_projection"),
                ("evidence","e12a6_evidence_state_projection"),
                ("actions","e12a6_action_state_projection"),
            ):
                counts[kind]=int(self.db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE scope=?",(scope,)
                ).fetchone()[0])
        return counts

    def _iter_e12a6_projection_rows(
        self, *, scope: str, table: str, json_column: str, output_key: str,
        page_size: int = 256,
    ):
        """Yield one scoped projection row at a time using bounded keyset pages."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 4096:
            raise ZPCMError("page_size must be an integer between 1 and 4096")
        allowed = {
            ("e12a6_candidate_state_projection", "candidate_json", "candidate"),
            ("e12a6_evidence_state_projection", "evidence_json", "evidence"),
            ("e12a6_action_state_projection", "action_json", "action"),
        }
        if (table, json_column, output_key) not in allowed:
            raise ZPCMError("unsupported lifecycle projection")
        last_seq = 0
        while True:
            with self.lock:
                rows = self.db.execute(
                    f"SELECT {json_column} AS payload,source_seq FROM {table} "
                    "WHERE scope=? AND source_seq>? ORDER BY source_seq LIMIT ?",
                    (scope, last_seq, page_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                last_seq = int(row["source_seq"])
                yield {
                    output_key: json.loads(row["payload"]),
                    "source_seq": last_seq,
                }
            if len(rows) < page_size:
                return

    def iter_lifecycle_candidate_projections(self, *, scope: str, page_size: int = 256):
        """Stream candidate current-state projections in source-event order."""
        yield from self._iter_e12a6_projection_rows(
            scope=scope, table="e12a6_candidate_state_projection",
            json_column="candidate_json", output_key="candidate", page_size=page_size,
        )

    def iter_lifecycle_evidence_projections(self, *, scope: str, page_size: int = 256):
        """Stream evidence projections in source-event order."""
        yield from self._iter_e12a6_projection_rows(
            scope=scope, table="e12a6_evidence_state_projection",
            json_column="evidence_json", output_key="evidence", page_size=page_size,
        )

    def iter_lifecycle_action_projections(self, *, scope: str, page_size: int = 256):
        """Stream action projections in source-event order."""
        yield from self._iter_e12a6_projection_rows(
            scope=scope, table="e12a6_action_state_projection",
            json_column="action_json", output_key="action", page_size=page_size,
        )

    def close(self):
        with self.lock:self.db.close()
    def _rebuild_authorization_consumption_index(self):
        """Backfill and validate receipt/nonce uniqueness using bounded event pages."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            scopes = self.db.execute(
                "SELECT DISTINCT scope FROM memory_events "
                "WHERE event_type='e12a6_lifecycle' ORDER BY scope"
            ).fetchall()
            for scope_row in scopes:
                scope = scope_row["scope"]
                for event in self.iter_domain_events(
                    event_type="e12a6_lifecycle", scope=scope,
                ):
                    payload = event["payload"]
                    if payload.get("kind") != "authorization_consumed":
                        continue
                    body = payload.get("body")
                    if not isinstance(body, dict):
                        raise ZPCMError("authorization consumption body must be an object")
                    receipt_id, nonce = body.get("receipt_id"), body.get("nonce")
                    if (not isinstance(receipt_id, str) or not receipt_id.strip()
                            or not isinstance(nonce, str) or not nonce.strip()
                            or body.get("scope") != scope
                            or event["event_id"] != f"e12a6:authorization-consumed:{receipt_id}"):
                        raise ZPCMError("authorization consumption index data is malformed")
                    existing = self.db.execute(
                        "SELECT receipt_id,nonce,event_id,scope FROM e12a6_authorization_consumptions "
                        "WHERE receipt_id=? OR nonce=? OR event_id=?",
                        (receipt_id, nonce, event["event_id"]),
                    ).fetchone()
                    expected = (receipt_id, nonce, event["event_id"], scope)
                    if existing is not None:
                        actual = (
                            existing["receipt_id"], existing["nonce"],
                            existing["event_id"], existing["scope"],
                        )
                        if actual != expected:
                            raise ZPCMError("duplicate receipt ID or nonce in persisted lifecycle history")
                        continue
                    self.db.execute(
                        "INSERT INTO e12a6_authorization_consumptions(receipt_id,nonce,event_id,scope) "
                        "VALUES(?,?,?,?)", expected,
                    )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def _append(self,event_id,event_type,scope,payload):
        if not all(isinstance(x,str) and x.strip() for x in (event_id,event_type,scope)):raise ZPCMError("event identifiers/type/scope required")
        raw=canonical(payload)
        payload_size=len(raw.encode("utf-8"))
        if payload_size > self.max_event_payload_bytes:
            raise ZPCMError(f"event payload exceeds max_event_payload_bytes: {payload_size} > {self.max_event_payload_bytes}")
        d=digest(payload)
        old=self.db.execute("SELECT seq,event_type,scope,payload_digest FROM memory_events WHERE event_id=?",(event_id,)).fetchone()
        if old:
            if (old["event_type"],old["scope"],old["payload_digest"])!=(event_type,scope,d):raise ZPCMError("event ID content conflict")
            return old["seq"],True
        cur=self.db.execute("INSERT INTO memory_events(event_id,event_type,scope,payload_json,payload_digest,recorded_at) VALUES(?,?,?,?,?,?)",(event_id,event_type,scope,raw,d,datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid,False

    def append_domain_event(self, *, event_type: str, event_id: str, scope: str,
                            payload: dict[str, Any], expected_sequence: int) -> dict[str, Any]:
        """Append one namespaced domain event to the shared append-only ZPCM log.

        Sequence checks are scoped by (event_type, scope). This is a generic
        extension point, not a second event table or independent ledger.
        """
        if not isinstance(payload, dict):
            raise ZPCMError("domain event payload must be an object")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        # E12-A6 authorization consumption is a privileged atomic bundle.
        # Never allow the generic domain-event API to bypass its validator
        # or the database-enforced receipt/nonce consumption index.
        if event_type == "e12a6_lifecycle" or payload.get("kind") == "authorization_consumed":
            raise ZPCMError("E12-A6 lifecycle events must use the authorized lifecycle append API")
        if not isinstance(expected_sequence, int) or isinstance(expected_sequence, bool) or expected_sequence < 0:
            raise ZPCMError("expected_sequence must be a non-negative integer")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                prior = self.db.execute(
                    "SELECT seq,event_type,scope,payload_digest FROM memory_events WHERE event_id=?",
                    (event_id,),
                ).fetchone()
                if prior is not None:
                    seq, replay = self._append(event_id, event_type, scope, payload)
                    self.db.execute("COMMIT")
                    return {"sequence": seq, "payload_digest": prior["payload_digest"], "replayed": replay}
                current = self.db.execute(
                    "SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type=? AND scope=?",
                    (event_type, scope),
                ).fetchone()[0]
                if current != expected_sequence:
                    raise ZPCMError(
                        f"stale domain sequence for {event_type}/{scope}: "
                        f"expected {expected_sequence}, current {current}"
                    )
                seq, replay = self._append(event_id, event_type, scope, payload)
                self.db.execute("COMMIT")
                return {"sequence": seq, "payload_digest": digest(payload), "replayed": replay}
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def iter_domain_events(
        self, *, event_type: str, scope: str, after_sequence: int = 0,
        page_size: int = 128,
    ) -> Iterator[dict[str, Any]]:
        """Keyset-page a stable snapshot with count and aggregate-byte bounds."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if isinstance(after_sequence, bool) or not isinstance(after_sequence, int) or after_sequence < 0:
            raise ZPCMError("after_sequence must be a non-negative integer")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 4096:
            raise ZPCMError("page_size must be an integer in [1, 4096]")
        with self.lock:
            high_water = self.db.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM memory_events WHERE event_type=? AND scope=?",
                (event_type, scope),
            ).fetchone()[0]
        cursor = after_sequence
        while cursor < high_water:
            with self.lock:
                rows = self.db.execute(
                    "SELECT seq,event_id,event_type,scope,length(CAST(payload_json AS BLOB)) AS payload_bytes,payload_digest,recorded_at "
                    "FROM memory_events WHERE event_type=? AND scope=? AND seq>? AND seq<=? "
                    "ORDER BY seq LIMIT ?",
                    (event_type, scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            selected = []
            used = 0
            for row in rows:
                size = int(row["payload_bytes"])
                if size > self.max_event_payload_bytes:
                    raise ZPCMError(f"persisted event payload exceeds max_event_payload_bytes: {row['event_id']}")
                if used + size > self.max_page_bytes:
                    break
                selected.append(row)
                used += size
            if not selected:
                raise ZPCMError("event page cannot make progress within max_page_bytes")
            for row in selected:
                # Fetch payload bytes only after metadata has passed the
                # aggregate page budget. Never fetchall() a page of JSON blobs.
                with self.lock:
                    raw = self.db.execute(
                        "SELECT payload_json FROM memory_events WHERE seq=? AND event_id=?",
                        (row["seq"], row["event_id"]),
                    ).fetchone()
                if raw is None:
                    raise ZPCMError("event disappeared during forward keyset iteration")
                payload = json.loads(raw["payload_json"])
                if digest(payload) != row["payload_digest"]:
                    raise ZPCMError(f"domain event digest mismatch: {row['event_id']}")
                cursor = row["seq"]
                yield {
                    "sequence": row["seq"], "event_id": row["event_id"],
                    "event_type": row["event_type"], "scope": row["scope"],
                    "payload": payload, "payload_digest": row["payload_digest"],
                    "recorded_at": row["recorded_at"],
                }

    def latest_domain_sequence(self, *, event_type: str, scope: str) -> int:
        """Return the current global event sequence for one typed scope stream."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        with self.lock:
            return int(self.db.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM memory_events WHERE event_type=? AND scope=?",
                (event_type, scope),
            ).fetchone()[0])

    def iter_domain_events_reverse(
        self, *, event_type: str, scope: str, before_sequence: int | None = None,
        page_size: int = 128,
    ) -> Iterator[dict[str, Any]]:
        """Keyset-page a typed event stream newest-first with byte bounds."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if before_sequence is not None and (
            isinstance(before_sequence, bool) or not isinstance(before_sequence, int)
            or before_sequence < 1
        ):
            raise ZPCMError("before_sequence must be a positive integer")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 4096:
            raise ZPCMError("page_size must be an integer in [1, 4096]")
        with self.lock:
            high_water = self.db.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM memory_events WHERE event_type=? AND scope=?",
                (event_type, scope),
            ).fetchone()[0]
        cursor = min(high_water + 1, before_sequence) if before_sequence is not None else high_water + 1
        while cursor > 1:
            with self.lock:
                rows = self.db.execute(
                    "SELECT seq,event_id,event_type,scope,length(CAST(payload_json AS BLOB)) AS payload_bytes,payload_digest,recorded_at "
                    "FROM memory_events WHERE event_type=? AND scope=? AND seq<? AND seq<=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (event_type, scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            selected = []
            used = 0
            for row in rows:
                size = int(row["payload_bytes"])
                if size > self.max_event_payload_bytes:
                    raise ZPCMError(f"persisted event payload exceeds max_event_payload_bytes: {row['event_id']}")
                if used + size > self.max_page_bytes:
                    break
                selected.append(row)
                used += size
            if not selected:
                raise ZPCMError("event page cannot make progress within max_page_bytes")
            for row in selected:
                with self.lock:
                    raw = self.db.execute(
                        "SELECT payload_json FROM memory_events WHERE seq=? AND event_id=?",
                        (row["seq"], row["event_id"]),
                    ).fetchone()
                if raw is None:
                    raise ZPCMError("event disappeared during reverse keyset iteration")
                payload = json.loads(raw["payload_json"])
                if digest(payload) != row["payload_digest"]:
                    raise ZPCMError(f"domain event digest mismatch: {row['event_id']}")
                cursor = row["seq"]
                yield {
                    "sequence": row["seq"], "event_id": row["event_id"],
                    "event_type": row["event_type"], "scope": row["scope"],
                    "payload": payload, "payload_digest": row["payload_digest"],
                    "recorded_at": row["recorded_at"],
                }

    def get_domain_event(
        self, *, event_type: str, scope: str, event_id: str,
    ) -> dict[str, Any] | None:
        """Fetch one indexed event after enforcing its persisted byte length."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ZPCMError("event_id must be non-empty")
        with self.lock:
            row = self.db.execute(
                "SELECT seq,event_id,event_type,scope,length(CAST(payload_json AS BLOB)) AS payload_bytes,payload_json,payload_digest,recorded_at "
                "FROM memory_events WHERE event_id=? AND event_type=? AND scope=?",
                (event_id, event_type, scope),
            ).fetchone()
        if row is None:
            return None
        if int(row["payload_bytes"]) > self.max_event_payload_bytes:
            raise ZPCMError(f"persisted event payload exceeds max_event_payload_bytes: {event_id}")
        payload = json.loads(row["payload_json"])
        if digest(payload) != row["payload_digest"]:
            raise ZPCMError(f"domain event digest mismatch: {event_id}")
        return {
            "sequence": row["seq"], "event_id": row["event_id"],
            "event_type": row["event_type"], "scope": row["scope"],
            "payload": payload, "payload_digest": row["payload_digest"],
            "recorded_at": row["recorded_at"],
        }

    def replay_domain_events(self, *, event_type: str, scope: str,
                             after_sequence: int = 0) -> list[dict[str, Any]]:
        """Materialize a complete typed stream; prefer iter_domain_events for bounded reads."""
        return list(self.iter_domain_events(
            event_type=event_type, scope=scope, after_sequence=after_sequence,
        ))

    def e12a6_lifecycle_prefix_digest(self, *, scope: str, through_sequence: int) -> tuple[int, str]:
        """Verify and hash a lifecycle event prefix using bounded, digest-checked pages."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if isinstance(through_sequence, bool) or not isinstance(through_sequence, int) or through_sequence < 0:
            raise ZPCMError("through_sequence must be a non-negative integer")
        prefix = hashlib.sha256()
        count = 0
        last_sequence = 0
        for event in self.iter_domain_events(event_type="e12a6_lifecycle", scope=scope):
            if event["sequence"] > through_sequence:
                break
            prefix.update(
                str(event["sequence"]).encode("ascii") + b"\0"
                + event["event_id"].encode("utf-8") + b"\0"
                + event["payload_digest"].encode("ascii") + b"\n"
            )
            count += 1
            last_sequence = event["sequence"]
        if last_sequence != through_sequence:
            if through_sequence != 0:
                raise ZPCMError("checkpoint sequence is not a lifecycle event boundary")
        return count, prefix.hexdigest()

    def save_e12a6_lifecycle_checkpoint(
        self, *, scope: str, checkpoint_schema: str, checkpoint_sequence: int,
        event_count: int, prefix_digest: str, snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically publish a checkpoint only if its event high-water mark is current."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(checkpoint_schema, str) or not checkpoint_schema.strip():
            raise ZPCMError("checkpoint_schema must be non-empty")
        if (isinstance(checkpoint_sequence, bool) or not isinstance(checkpoint_sequence, int)
                or checkpoint_sequence < 0 or isinstance(event_count, bool)
                or not isinstance(event_count, int) or event_count < 0):
            raise ZPCMError("invalid checkpoint sequence or event count")
        if not isinstance(prefix_digest, str) or len(prefix_digest) != 64:
            raise ZPCMError("invalid checkpoint prefix digest")
        if not isinstance(snapshot, dict):
            raise ZPCMError("checkpoint snapshot must be an object")
        snapshot_json = canonical(snapshot)
        snapshot_digest = hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest()
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute(
                    "SELECT COALESCE(MAX(seq),0),COUNT(*) FROM memory_events "
                    "WHERE event_type='e12a6_lifecycle' AND scope=?",
                    (scope,),
                ).fetchone()
                if int(row[0]) != checkpoint_sequence or int(row[1]) != event_count:
                    raise ZPCMError("lifecycle stream changed while checkpoint was being published")
                actual_count, actual_prefix_digest = self.e12a6_lifecycle_prefix_digest(
                    scope=scope, through_sequence=checkpoint_sequence,
                )
                if actual_count != event_count or actual_prefix_digest != prefix_digest:
                    raise ZPCMError("checkpoint prefix digest does not match the authoritative event log")
                if (snapshot.get("scope") != scope
                        or snapshot.get("last_sequence") != checkpoint_sequence):
                    raise ZPCMError("checkpoint snapshot scope or sequence mismatch")
                created_at = datetime.now(timezone.utc).isoformat()
                self.db.execute(
                    "INSERT INTO e12a6_lifecycle_checkpoints("
                    "scope,checkpoint_schema,checkpoint_sequence,event_count,prefix_digest,"
                    "snapshot_json,snapshot_digest,created_at) VALUES(?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(scope) DO UPDATE SET checkpoint_schema=excluded.checkpoint_schema,"
                    "checkpoint_sequence=excluded.checkpoint_sequence,event_count=excluded.event_count,"
                    "prefix_digest=excluded.prefix_digest,snapshot_json=excluded.snapshot_json,"
                    "snapshot_digest=excluded.snapshot_digest,created_at=excluded.created_at",
                    (scope, checkpoint_schema, checkpoint_sequence, event_count, prefix_digest,
                     snapshot_json, snapshot_digest, created_at),
                )
                self.db.execute("COMMIT")
                return {
                    "scope": scope, "checkpoint_schema": checkpoint_schema,
                    "checkpoint_sequence": checkpoint_sequence, "event_count": event_count,
                    "prefix_digest": prefix_digest, "snapshot_digest": snapshot_digest,
                    "created_at": created_at,
                }
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def load_e12a6_lifecycle_checkpoint(self, *, scope: str) -> dict[str, Any] | None:
        """Load a checkpoint only after verifying its canonical snapshot digest."""
        with self.lock:
            row = self.db.execute(
                "SELECT checkpoint_schema,checkpoint_sequence,event_count,prefix_digest,"
                "snapshot_json,snapshot_digest,created_at,pages_digest FROM e12a6_lifecycle_checkpoints WHERE scope=?",
                (scope,),
            ).fetchone()
        if row is None:
            return None
        try:
            snapshot = json.loads(row["snapshot_json"])
            if (not isinstance(snapshot, dict)
                    or hashlib.sha256(canonical(snapshot).encode("utf-8")).hexdigest()
                    != row["snapshot_digest"]):
                raise ZPCMError("checkpoint snapshot digest mismatch")
            return {
                "scope": scope, "checkpoint_schema": row["checkpoint_schema"],
                "checkpoint_sequence": int(row["checkpoint_sequence"]),
                "event_count": int(row["event_count"]), "prefix_digest": row["prefix_digest"],
                "snapshot": snapshot, "snapshot_digest": row["snapshot_digest"],
                "pages_digest": row["pages_digest"],
                "created_at": row["created_at"],
            }
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise ZPCMError("checkpoint snapshot is malformed") from exc


    def e12a6_authorization_projection_digest(
        self, *, scope: str, through_sequence: int,
    ) -> tuple[int, str]:
        """Digest the scoped receipt projection in stable receipt-ID order without materializing it."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if isinstance(through_sequence, bool) or not isinstance(through_sequence, int) or through_sequence < 0:
            raise ZPCMError("through_sequence must be a non-negative integer")
        digest_state = hashlib.sha256()
        count = 0
        with self.lock:
            cursor = self.db.execute(
                "SELECT c.receipt_id,e.event_id,e.payload_json,e.payload_digest "
                "FROM e12a6_authorization_consumptions c "
                "JOIN memory_events e ON e.event_id=c.event_id "
                "WHERE c.scope=? AND e.seq<=? ORDER BY c.receipt_id",
                (scope, through_sequence),
            )
            while True:
                rows = cursor.fetchmany(128)
                if not rows:
                    break
                for row in rows:
                    payload = json.loads(row["payload_json"])
                    if digest(payload) != row["payload_digest"]:
                        raise ZPCMError(f"authorization event digest mismatch: {row['event_id']}")
                    if payload.get("kind") != "authorization_consumed" or not isinstance(payload.get("body"), dict):
                        raise ZPCMError("authorization projection points to an invalid lifecycle event")
                    digest_state.update(
                        row["receipt_id"].encode("utf-8") + b"\\0"
                        + canonical(payload["body"]).encode("utf-8") + b"\\n"
                    )
                    count += 1
        return count, digest_state.hexdigest()

    def save_e12a6_lifecycle_checkpoint_pages(
        self, *, scope: str, checkpoint_schema: str, checkpoint_sequence: int,
        event_count: int, prefix_digest: str, snapshot_header: dict[str, Any],
        pages: Iterable[tuple[str, int, list[dict[str, Any]]]],
    ) -> dict[str, Any]:
        """Atomically publish a bounded-page checkpoint tied to a verified event prefix."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(checkpoint_schema, str) or not checkpoint_schema.strip():
            raise ZPCMError("checkpoint_schema must be non-empty")
        if (isinstance(checkpoint_sequence, bool) or not isinstance(checkpoint_sequence, int)
                or checkpoint_sequence < 0 or isinstance(event_count, bool)
                or not isinstance(event_count, int) or event_count < 0):
            raise ZPCMError("invalid checkpoint sequence or event count")
        if not isinstance(prefix_digest, str) or len(prefix_digest) != 64:
            raise ZPCMError("invalid checkpoint prefix digest")
        required_header = {
            "schema_version", "scope", "last_sequence", "candidate_count",
            "evidence_count", "action_count", "authorization_count", "authorization_digest",
        }
        if (not isinstance(snapshot_header, dict) or set(snapshot_header) != required_header
                or snapshot_header.get("schema_version") != "e12a6-lifecycle-event-v1"
                or snapshot_header.get("scope") != scope
                or snapshot_header.get("last_sequence") != checkpoint_sequence):
            raise ZPCMError("checkpoint header metadata mismatch")
        header_json = canonical(snapshot_header)
        header_digest = hashlib.sha256(header_json.encode("utf-8")).hexdigest()
        expected_counts = {
            "candidates": snapshot_header["candidate_count"],
            "evidence": snapshot_header["evidence_count"],
            "actions": snapshot_header["action_count"],
        }
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in expected_counts.values()):
            raise ZPCMError("checkpoint header row counts are invalid")
        if (isinstance(snapshot_header["authorization_count"], bool)
                or not isinstance(snapshot_header["authorization_count"], int)
                or snapshot_header["authorization_count"] < 0
                or not isinstance(snapshot_header["authorization_digest"], str)
                or len(snapshot_header["authorization_digest"]) != 64):
            raise ZPCMError("checkpoint authorization digest metadata is invalid")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute(
                    "SELECT COALESCE(MAX(seq),0),COUNT(*) FROM memory_events "
                    "WHERE event_type='e12a6_lifecycle' AND scope=?",
                    (scope,),
                ).fetchone()
                if int(row[0]) != checkpoint_sequence or int(row[1]) != event_count:
                    raise ZPCMError("lifecycle stream changed while checkpoint was being published")
                actual_count, actual_prefix_digest = self.e12a6_lifecycle_prefix_digest(
                    scope=scope, through_sequence=checkpoint_sequence,
                )
                if actual_count != event_count or actual_prefix_digest != prefix_digest:
                    raise ZPCMError("checkpoint prefix digest does not match the authoritative event log")
                auth_count, auth_digest = self.e12a6_authorization_projection_digest(
                    scope=scope, through_sequence=checkpoint_sequence,
                )
                if (auth_count != snapshot_header["authorization_count"]
                        or auth_digest != snapshot_header["authorization_digest"]):
                    raise ZPCMError("checkpoint authorization projection changed during publication")
                self.db.execute(
                    "DELETE FROM e12a6_lifecycle_checkpoint_pages WHERE scope=?",
                    (scope,),
                )
                page_state = hashlib.sha256()
                page_counts = {"candidates": 0, "evidence": 0, "actions": 0}
                next_indices = {"candidates": 0, "evidence": 0, "actions": 0}
                for page_kind, page_index, items in pages:
                    if page_kind not in page_counts:
                        raise ZPCMError("checkpoint page kind is invalid")
                    if (isinstance(page_index, bool) or not isinstance(page_index, int)
                            or page_index != next_indices[page_kind]):
                        raise ZPCMError("checkpoint page index is not contiguous")
                    if not isinstance(items, list) or not items:
                        raise ZPCMError("checkpoint pages must contain a non-empty list")
                    page_json = canonical(items)
                    page_bytes = page_json.encode("utf-8")
                    if len(page_bytes) > self.max_page_bytes:
                        raise ZPCMError("checkpoint page exceeds max_page_bytes")
                    page_digest = hashlib.sha256(page_bytes).hexdigest()
                    page_state.update(
                        page_kind.encode("ascii") + b"\\0"
                        + str(page_index).encode("ascii") + b"\\0"
                        + page_digest.encode("ascii") + b"\\n"
                    )
                    self.db.execute(
                        "INSERT INTO e12a6_lifecycle_checkpoint_pages("
                        "scope,checkpoint_sequence,page_kind,page_index,page_json,page_digest"
                        ") VALUES(?,?,?,?,?,?)",
                        (scope, checkpoint_sequence, page_kind, page_index, page_json, page_digest),
                    )
                    page_counts[page_kind] += len(items)
                    next_indices[page_kind] += 1
                if page_counts != expected_counts:
                    raise ZPCMError("checkpoint page row counts do not match the runtime state")
                pages_digest = page_state.hexdigest()
                created_at = datetime.now(timezone.utc).isoformat()
                self.db.execute(
                    "INSERT INTO e12a6_lifecycle_checkpoints("
                    "scope,checkpoint_schema,checkpoint_sequence,event_count,prefix_digest,"
                    "snapshot_json,snapshot_digest,created_at,pages_digest"
                    ") VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(scope) DO UPDATE SET "
                    "checkpoint_schema=excluded.checkpoint_schema,"
                    "checkpoint_sequence=excluded.checkpoint_sequence,"
                    "event_count=excluded.event_count,prefix_digest=excluded.prefix_digest,"
                    "snapshot_json=excluded.snapshot_json,snapshot_digest=excluded.snapshot_digest,"
                    "created_at=excluded.created_at,pages_digest=excluded.pages_digest",
                    (scope, checkpoint_schema, checkpoint_sequence, event_count, prefix_digest,
                     header_json, header_digest, created_at, pages_digest),
                )
                self.db.execute("COMMIT")
                return {
                    "scope": scope, "checkpoint_schema": checkpoint_schema,
                    "checkpoint_sequence": checkpoint_sequence, "event_count": event_count,
                    "prefix_digest": prefix_digest, "snapshot_digest": header_digest,
                    "pages_digest": pages_digest, "created_at": created_at,
                }
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def iter_e12a6_lifecycle_checkpoint_pages(
        self, *, scope: str, checkpoint_sequence: int, expected_pages_digest: str,
    ) -> Iterator[dict[str, Any]]:
        """Stream and verify checkpoint pages with bounded SQLite fetches."""
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if isinstance(checkpoint_sequence, bool) or not isinstance(checkpoint_sequence, int) or checkpoint_sequence < 0:
            raise ZPCMError("checkpoint_sequence must be non-negative")
        if not isinstance(expected_pages_digest, str) or len(expected_pages_digest) != 64:
            raise ZPCMError("checkpoint pages digest is invalid")
        page_state = hashlib.sha256()
        next_indices = {"candidates": 0, "evidence": 0, "actions": 0}
        with self.lock:
            cursor = self.db.execute(
                "SELECT page_kind,page_index,page_json,page_digest "
                "FROM e12a6_lifecycle_checkpoint_pages "
                "WHERE scope=? AND checkpoint_sequence=? "
                "ORDER BY CASE page_kind WHEN 'candidates' THEN 0 WHEN 'evidence' THEN 1 WHEN 'actions' THEN 2 ELSE 3 END,page_index",
                (scope, checkpoint_sequence),
            )
            while True:
                rows = cursor.fetchmany(16)
                if not rows:
                    break
                for row in rows:
                    kind = row["page_kind"]
                    index = int(row["page_index"])
                    if kind not in next_indices or index != next_indices[kind]:
                        raise ZPCMError("checkpoint page sequence is incomplete")
                    page_bytes = row["page_json"].encode("utf-8")
                    if len(page_bytes) > self.max_page_bytes:
                        raise ZPCMError("persisted checkpoint page exceeds max_page_bytes")
                    actual_digest = hashlib.sha256(page_bytes).hexdigest()
                    if actual_digest != row["page_digest"]:
                        raise ZPCMError("checkpoint page digest mismatch")
                    items = json.loads(row["page_json"])
                    if not isinstance(items, list) or not items:
                        raise ZPCMError("checkpoint page payload is malformed")
                    page_state.update(
                        kind.encode("ascii") + b"\\0"
                        + str(index).encode("ascii") + b"\\0"
                        + actual_digest.encode("ascii") + b"\\n"
                    )
                    next_indices[kind] += 1
                    yield {"kind": kind, "page_index": index, "items": items}
        if page_state.hexdigest() != expected_pages_digest:
            raise ZPCMError("checkpoint page manifest digest mismatch")

    def append_lifecycle_event(self, *, event_id: str, scope: str, payload: dict[str, Any],
                               expected_sequence: int) -> dict[str, Any]:
        """Append a versioned E12-A6 event to the unbounded durable event log."""
        if not isinstance(payload, dict): raise ZPCMError("lifecycle payload must be an object")
        if payload.get("kind") == "authorization_consumed":
            raise ZPCMError("authorization consumption must be appended with its candidate/evidence bundle")
        if isinstance(expected_sequence, bool) or not isinstance(expected_sequence, int) or expected_sequence < 0:
            raise ZPCMError("expected_sequence must be a non-negative integer")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                prior = self.db.execute("SELECT seq,event_type,scope,payload_digest FROM memory_events WHERE event_id=?",
                                        (event_id,)).fetchone()
                if prior is not None:
                    seq, replay = self._append(event_id, "e12a6_lifecycle", scope, payload)
                    self.db.execute("COMMIT")
                    return {"sequence":seq,"payload_digest":prior["payload_digest"],"replayed":replay}
                current = self.db.execute("SELECT COALESCE(MAX(seq),0) FROM memory_events WHERE event_type='e12a6_lifecycle' AND scope=?",
                                          (scope,)).fetchone()[0]
                if current != expected_sequence:
                    raise ZPCMError(f"stale lifecycle sequence: expected {expected_sequence}, current {current}")
                seq, replay = self._append(event_id, "e12a6_lifecycle", scope, payload)
                if not replay:
                    self._index_e12a6_candidate_event(scope, seq, event_id, payload)
                    self.db.execute(
                        "INSERT INTO e12a6_lifecycle_candidate_history_meta(scope,high_water_seq,event_count) "
                        "VALUES(?,?,1) ON CONFLICT(scope) DO UPDATE SET "
                        "high_water_seq=MAX(high_water_seq,excluded.high_water_seq),event_count=event_count+1",
                        (scope, seq),
                    )
                self.db.execute("COMMIT")
                return {"sequence":seq,"payload_digest":digest(payload),"replayed":replay}
            except sqlite3.IntegrityError as exc:
                self.db.execute("ROLLBACK")
                raise ZPCMError("lifecycle event database integrity error") from exc
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def replay_lifecycle_events(self, *, scope: str, after_sequence: int = 0) -> list[dict[str, Any]]:
        """Replay every scoped lifecycle event; unlike retrieve(), this never truncates."""
        if not isinstance(scope, str) or not scope.strip(): raise ZPCMError("scope must be non-empty")
        if isinstance(after_sequence, bool) or not isinstance(after_sequence, int) or after_sequence < 0:
            raise ZPCMError("after_sequence must be a non-negative integer")
        with self.lock:
            rows = self.db.execute(
                "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                "FROM memory_events WHERE event_type='e12a6_lifecycle' AND scope=? AND seq>? ORDER BY seq",
                (scope, after_sequence),
            ).fetchall()
        events = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if digest(payload) != row["payload_digest"]:
                raise ZPCMError(f"lifecycle event digest mismatch: {row['event_id']}")
            events.append({"sequence":row["seq"],"event_id":row["event_id"],
                "event_type":row["event_type"],"scope":row["scope"],"payload":payload,
                "payload_digest":row["payload_digest"],"recorded_at":row["recorded_at"]})
        return events


    def _validate_authorization_consumption_batch(self, normalized, scope, authorization_uses):
        if len(authorization_uses) != 1:
            raise ZPCMError("one candidate bundle may consume exactly one authorization receipt")
        receipt_id, nonce, auth_event_id, _ = authorization_uses[0]
        payload_by_id = dict(normalized)
        auth_payload = payload_by_id[auth_event_id]
        body = auth_payload["body"]
        candidate_rows = [
            (event_id, payload) for event_id, payload in normalized
            if payload.get("kind") == "candidate_registered"
        ]
        evidence_rows = [
            (event_id, payload) for event_id, payload in normalized
            if payload.get("kind") == "evidence_registered"
        ]
        if len(candidate_rows) != 1 or not evidence_rows:
            raise ZPCMError("authorization consumption must share a batch with one candidate and its evidence")
        candidate_event_id, candidate_payload = candidate_rows[0]
        candidate = candidate_payload.get("body", {}).get("candidate")
        if not isinstance(candidate, dict):
            raise ZPCMError("authorized candidate event is malformed")
        candidate_id, version = candidate.get("candidate_id"), candidate.get("version")
        if (candidate_event_id != f"e12a6:candidate:{candidate_id}@{version}"
                or body.get("candidate_id") != candidate_id
                or body.get("candidate_version") != version
                or candidate.get("state") != "observed"):
            raise ZPCMError("authorization consumption candidate identity/state mismatch")
        evidence_ids = candidate.get("evidence_ids")
        if (not isinstance(evidence_ids, list) or not evidence_ids
                or len(evidence_ids) != len(set(evidence_ids))
                or set(evidence_ids) != set(body.get("evidence_refs", ()))):
            raise ZPCMError("authorization receipt evidence set does not match candidate")
        batch_evidence = {}
        for event_id, payload in evidence_rows:
            item = payload.get("body", {}).get("evidence")
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                raise ZPCMError("authorized evidence event is malformed")
            evidence_id = item["evidence_id"]
            if event_id != f"e12a6:evidence:{evidence_id}" or evidence_id in batch_evidence:
                raise ZPCMError("authorized evidence event ID mismatch or duplicate")
            if item.get("episode_id") != body.get("episode_id"):
                raise ZPCMError("authorized evidence episode mismatch")
            batch_evidence[evidence_id] = item
        if set(batch_evidence) != set(evidence_ids):
            raise ZPCMError("authorization receipt requires every candidate evidence event in the same batch")
        if (not set(body.get("authorization_evidence_refs", ())).issubset(set(evidence_ids))
                or body.get("scope") != scope):
            raise ZPCMError("authorization receipt scope/evidence binding mismatch")
        try:
            definition = json.loads(candidate["canonical_expression"])
            merge = definition["branch_merge"]
            issued = datetime.fromisoformat(body["receipt_issued_at"].replace("Z", "+00:00"))
            expires = datetime.fromisoformat(body["receipt_expires_at"].replace("Z", "+00:00"))
            consumed = datetime.fromisoformat(body["consumed_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError, KeyError) as exc:
            raise ZPCMError("authorized candidate or receipt time binding is malformed") from exc
        if (not isinstance(merge, dict)
                or definition.get("schema") != "csg-gcr-typed-candidate-v1"
                or merge.get("authorization_ref") != body.get("authorization_ref")
                or set(definition.get("branch_ids", ())) != set(body.get("branch_ids", ()))
                or set(merge.get("authorization_evidence_refs", ())) != set(body.get("authorization_evidence_refs", ()))
                or body.get("parent_state_ref") not in candidate.get("parent_refs", ())
                or issued.tzinfo is None or expires.tzinfo is None or consumed.tzinfo is None
                or consumed < issued or consumed >= expires):
            raise ZPCMError("authorization receipt does not bind the typed candidate merge")
        if (not isinstance(body.get("issuer_id"), str) or not body["issuer_id"].strip()
                or not isinstance(body.get("verifier_id"), str) or not body["verifier_id"].strip()
                or not isinstance(body.get("authorization_event_digest"), str)
                or len(body["authorization_event_digest"]) != 64):
            raise ZPCMError("authorization receipt issuer/verifier/digest fields are invalid")
        submitter_fields = (
            "submitter_workload_id", "submitter_identity_provider",
            "submitter_authentication_method", "submitter_credential_fingerprint",
        )
        if any(not isinstance(body.get(field), str) or not body[field].strip() for field in submitter_fields):
            raise ZPCMError("authorization consumption submitter identity is incomplete")
        fingerprint = body["submitter_credential_fingerprint"]
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ZPCMError("authorization consumption submitter fingerprint is invalid")
        if normalized[-1][0] != auth_event_id:
            raise ZPCMError("authorization consumption event must be last in its atomic bundle")

    def append_lifecycle_events(self, *, events: Sequence[dict[str, Any]], scope: str,
                                expected_sequence: int) -> list[dict[str, Any]]:
        """Atomically append a complete lifecycle event bundle.

        The batch is all-new or all-replayed. Mixed prior/new batches are
        rejected so retries cannot silently complete a partially committed
        logical ingestion.
        """
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(events, (list, tuple)) or not events:
            raise ZPCMError("events must be a non-empty sequence")
        if isinstance(expected_sequence, bool) or not isinstance(expected_sequence, int) or expected_sequence < 0:
            raise ZPCMError("expected_sequence must be a non-negative integer")
        normalized = []
        ids = set()
        authorization_uses = []
        receipt_ids = set()
        nonces = set()
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("payload"), dict):
                raise ZPCMError("each lifecycle event requires an object payload")
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not event_id.strip() or event_id in ids:
                raise ZPCMError("lifecycle batch event IDs must be unique non-empty strings")
            ids.add(event_id)
            payload = event["payload"]
            if payload.get("kind") == "authorization_consumed":
                body = payload.get("body")
                if not isinstance(body, dict):
                    raise ZPCMError("authorization consumption body must be an object")
                receipt_id, nonce = body.get("receipt_id"), body.get("nonce")
                if (not isinstance(receipt_id, str) or not receipt_id.strip()
                        or not isinstance(nonce, str) or not nonce.strip()
                        or body.get("scope") != scope
                        or event_id != f"e12a6:authorization-consumed:{receipt_id}"):
                    raise ZPCMError("authorization consumption event is malformed")
                if receipt_id in receipt_ids or nonce in nonces:
                    raise ZPCMError("duplicate receipt ID or nonce within lifecycle batch")
                receipt_ids.add(receipt_id)
                nonces.add(nonce)
                authorization_uses.append((receipt_id, nonce, event_id, scope))
            normalized.append((event_id, payload))
        if authorization_uses:
            self._validate_authorization_consumption_batch(normalized, scope, authorization_uses)
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                prior_rows = [
                    self.db.execute(
                        "SELECT seq,event_type,scope,payload_digest FROM memory_events WHERE event_id=?",
                        (event_id,),
                    ).fetchone()
                    for event_id, _ in normalized
                ]
                existing_count = sum(row is not None for row in prior_rows)
                if existing_count not in (0, len(normalized)):
                    raise ZPCMError("partial lifecycle batch replay conflict")
                if existing_count == 0:
                    current = self.db.execute(
                        "SELECT COALESCE(MAX(seq),0) FROM memory_events "
                        "WHERE event_type='e12a6_lifecycle' AND scope=?",
                        (scope,),
                    ).fetchone()[0]
                    if current != expected_sequence:
                        raise ZPCMError(
                            f"stale lifecycle sequence: expected {expected_sequence}, current {current}"
                        )
                receipts = []
                for event_id, payload in normalized:
                    seq, replay = self._append(event_id, "e12a6_lifecycle", scope, payload)
                    if not replay:
                        self._index_e12a6_candidate_event(scope, seq, event_id, payload)
                        self.db.execute(
                            "INSERT INTO e12a6_lifecycle_candidate_history_meta(scope,high_water_seq,event_count) "
                            "VALUES(?,?,1) ON CONFLICT(scope) DO UPDATE SET "
                            "high_water_seq=MAX(high_water_seq,excluded.high_water_seq),event_count=event_count+1",
                            (scope, seq),
                        )
                    if payload.get("kind") == "authorization_consumed" and not replay:
                        body = payload["body"]
                        self.db.execute(
                            "INSERT INTO e12a6_authorization_consumptions(receipt_id,nonce,event_id,scope) "
                            "VALUES(?,?,?,?)",
                            (body["receipt_id"], body["nonce"], event_id, scope),
                        )
                    receipts.append({
                        "event_id": event_id, "sequence": seq,
                        "payload_digest": digest(payload), "replayed": replay,
                    })
                self.db.execute("COMMIT")
                return receipts
            except sqlite3.IntegrityError as exc:
                self.db.execute("ROLLBACK")
                raise ZPCMError("authorization receipt ID or nonce was already consumed") from exc
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def append_item(self,*,item_id,item_type,scope,content,source_event_id):
        if not isinstance(content,dict):raise ZPCMError("content must be object")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                seq,replay=self._append(source_event_id,"memory_item",scope,{"item_id":item_id,"item_type":item_type,"content":content})
                if replay:
                    row=self.db.execute("SELECT item_type,scope,content_json FROM memory_items WHERE item_id=?",(item_id,)).fetchone()
                    if row is None or (row["item_type"],row["scope"],row["content_json"])!=(item_type,scope,canonical(content)):raise ZPCMError("projection mismatch")
                    self.db.execute("COMMIT");return False
                self.db.execute("INSERT INTO memory_items VALUES(?,?,?,?,?,?,1)",(item_id,item_type,scope,canonical(content),source_event_id,seq))
                self.db.execute("COMMIT");return True
            except Exception:self.db.execute("ROLLBACK");raise
    def add_assertion(self,*,assertion_id,subject_id,predicate,object_value,scope,source_event_id,valid_from=None,valid_to=None):
        if not all(isinstance(x,str) and x.strip() for x in (assertion_id,subject_id,predicate,scope,source_event_id)):raise ZPCMError("assertion identity fields required")
        if valid_from and valid_to and valid_to<valid_from:raise ZPCMError("invalid validity interval")
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                payload={"assertion_id":assertion_id,"subject_id":subject_id,"predicate":predicate,"object":object_value,"valid_from":valid_from,"valid_to":valid_to}
                seq,replay=self._append(source_event_id,"assertion_added",scope,payload); obj=canonical(object_value)
                old=self.db.execute("SELECT * FROM assertions WHERE assertion_id=?",(assertion_id,)).fetchone()
                if old:
                    if (old["subject_id"],old["predicate"],old["object_json"],old["scope"])!=(subject_id,predicate,obj,scope):raise ZPCMError("assertion ID immutable")
                    self.db.execute("COMMIT");return old["status"]
                peers=self.db.execute("SELECT object_json FROM assertions WHERE scope=? AND subject_id=? AND predicate=? AND status IN ('ACTIVE','CONTESTED')",(scope,subject_id,predicate)).fetchall()
                status="CONTESTED" if any(p["object_json"]!=obj for p in peers) else "ACTIVE"
                if status=="CONTESTED":self.db.execute("UPDATE assertions SET status='CONTESTED' WHERE scope=? AND subject_id=? AND predicate=? AND status='ACTIVE'",(scope,subject_id,predicate))
                self.db.execute("INSERT INTO assertions VALUES(?,?,?,?,?,?,?,?,?,?)",(assertion_id,subject_id,predicate,obj,scope,valid_from,valid_to,status,source_event_id,seq))
                self.db.execute("COMMIT");return status
            except Exception:self.db.execute("ROLLBACK");raise
    def retract_assertion(self,assertion_id,*,event_id,scope,reason=""):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row=self.db.execute("SELECT * FROM assertions WHERE assertion_id=? AND scope=?",(assertion_id,scope)).fetchone()
                if row is None:raise ZPCMError("assertion not found in scope")
                self._append(event_id,"assertion_retracted",scope,{"assertion_id":assertion_id,"reason":reason})
                if row["status"]=="RETRACTED":self.db.execute("COMMIT");return False
                self.db.execute("UPDATE assertions SET status='RETRACTED' WHERE assertion_id=?",(assertion_id,))
                objects=self.db.execute("SELECT DISTINCT object_json FROM assertions WHERE scope=? AND subject_id=? AND predicate=? AND status IN ('ACTIVE','CONTESTED')",(scope,row["subject_id"],row["predicate"])).fetchall()
                if len(objects)==1:self.db.execute("UPDATE assertions SET status='ACTIVE' WHERE scope=? AND subject_id=? AND predicate=? AND status='CONTESTED'",(scope,row["subject_id"],row["predicate"]))
                self.db.execute("COMMIT");return True
            except Exception:self.db.execute("ROLLBACK");raise
    def sync_protocol_events(self,events:Iterable[dict],*,scope:str,learner_track:str)->int:
        if not scope.strip() or not learner_track.strip():raise ZPCMError("scope and learner track required")
        added=0
        for event in events:
            eid=event.get("event_id"); typ=event.get("event_type"); p=event.get("payload") or {}
            if p.get("learner_track") not in (None,learner_track):continue
            if typ not in {"observation","prediction_commit","evidence_reveal","structure_version","revision"}:continue
            safe=dict(p)
            if typ=="evidence_reveal":
                safe.pop("target_or_feedback",None)
                safe.pop("reveal_source",None)
            if typ=="structure_version" and isinstance(safe.get("definition"),dict):safe["definition"]={k:v for k,v in safe["definition"].items() if k not in {"snapshot","ledger_snapshot"}}
            safe.pop("raw_input",None)
            s=str(safe.get("scope",scope))
            with self.lock:
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    seq,replay=self._append(str(eid),"protocol:"+typ,s,{"source_event_id":eid,"source_payload_digest":event.get("payload_digest"),"payload":safe,"protocol_version":event.get("protocol_version")})
                    if not replay:
                        self.db.execute("INSERT INTO memory_items VALUES(?,?,?,?,?,?,1)",("protocol:"+str(eid),"protocol:"+typ,s,canonical({"source_event_id":eid,"payload":safe}),str(eid),seq));added+=1
                    self.db.execute("COMMIT")
                except Exception:self.db.execute("ROLLBACK");raise
        return added
    def sync_episode(self,protocol_store,*,episode_id:str,scope:str,learner_track:str)->int:
        """Project the authoritative E09 episode log; repeated full scans are idempotent."""
        if not isinstance(episode_id,str) or not episode_id.strip():raise ZPCMError("episode_id required")
        events=protocol_store.replay_episode(episode_id)
        return self.sync_protocol_events(events,scope=scope,learner_track=learner_track)
    def retrieve(self,*,scope,query_terms:Sequence[str]=(),item_types:Sequence[str]=(),max_items=64,max_bytes=32768):
        if not isinstance(scope,str) or not scope.strip() or max_items<1 or max_bytes<1:raise ZPCMError("valid scope and positive budgets required")
        terms=tuple(t.casefold() for t in query_terms if isinstance(t,str) and t.strip())
        sql="SELECT * FROM memory_items WHERE scope=? AND active=1";args=[scope]
        if item_types:sql+=" AND item_type IN ("+",".join("?" for _ in item_types)+")";args.extend(item_types)
        rows=self.db.execute(sql+" ORDER BY created_seq DESC",args).fetchall(); ranked=[]
        for r in rows:
            content=json.loads(r["content_json"]); hay=canonical(content).casefold();score=sum(t in hay for t in terms)
            if terms and score==0:continue
            ranked.append((score,r["created_seq"],r,content))
        ranked.sort(key=lambda x:(x[0],x[1]),reverse=True);items=[];used=0;truncated=False
        for _,_,r,c in ranked:
            item={"item_id":r["item_id"],"item_type":r["item_type"],"source_event_id":r["source_event_id"],"content":c}
            size=len(canonical(item).encode())
            if len(items)>=max_items or used+size>max_bytes:truncated=True;continue
            items.append(item);used+=size
        return {"schema_version":self.SCHEMA_VERSION,"scope":scope,"items":items,"source_refs":[x["source_event_id"] for x in items],"complete":not truncated,"truncated":truncated,"item_count":len(items),"bytes_used":used,"candidate_count":len(ranked)}
    def assertions(self,*,scope,subject_id=None,predicate=None):
        sql="SELECT * FROM assertions WHERE scope=?";args=[scope]
        if subject_id is not None:sql+=" AND subject_id=?";args.append(subject_id)
        if predicate is not None:sql+=" AND predicate=?";args.append(predicate)
        sql+=" ORDER BY created_seq"
        return [{"assertion_id":r["assertion_id"],"subject_id":r["subject_id"],"predicate":r["predicate"],"object":json.loads(r["object_json"]),"scope":r["scope"],"valid_from":r["valid_from"],"valid_to":r["valid_to"],"status":r["status"],"source_event_id":r["source_event_id"]} for r in self.db.execute(sql,args).fetchall()]
    def verify_integrity(self):
        check=self.db.execute("PRAGMA integrity_check").fetchone()[0]
        rows=self.db.execute("SELECT event_id,payload_json,payload_digest FROM memory_events ORDER BY seq").fetchall()
        bad=[r["event_id"] for r in rows if digest(json.loads(r["payload_json"]))!=r["payload_digest"]]
        return {"sqlite_integrity":check,"event_count":len(rows),"digest_mismatches":bad,"ok":check=="ok" and not bad}
