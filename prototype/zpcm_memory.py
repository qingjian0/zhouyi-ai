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
    def __init__(self,path:str|Path):
        self.path=str(path); self.lock=threading.RLock()
        self.db=sqlite3.connect(self.path,isolation_level=None,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        mode="WAL" if sqlite3.sqlite_version_info >= (3,51,3) else "DELETE"
        self.journal_mode=str(self.db.execute(f"PRAGMA journal_mode={mode}").fetchone()[0]).upper()
        self.db.execute("PRAGMA synchronous=FULL"); self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS memory_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,event_type TEXT NOT NULL,scope TEXT NOT NULL,payload_json TEXT NOT NULL,payload_digest TEXT NOT NULL,recorded_at TEXT NOT NULL);
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
        """)
        self._rebuild_authorization_consumption_index()
    def close(self):
        with self.lock:self.db.close()
    def _rebuild_authorization_consumption_index(self):
        """Backfill and validate DB-enforced unique receipt/nonce consumption."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            rows = self.db.execute(
                "SELECT event_id,scope,payload_json,payload_digest FROM memory_events "
                "WHERE event_type='e12a6_lifecycle'"
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload_json"])
                if digest(payload) != row["payload_digest"]:
                    raise ZPCMError("authorization consumption event digest mismatch")
                if payload.get("kind") != "authorization_consumed":
                    continue
                body = payload.get("body")
                if not isinstance(body, dict):
                    raise ZPCMError("authorization consumption body must be an object")
                receipt_id, nonce = body.get("receipt_id"), body.get("nonce")
                if (not isinstance(receipt_id, str) or not receipt_id.strip()
                        or not isinstance(nonce, str) or not nonce.strip()
                        or body.get("scope") != row["scope"]
                        or row["event_id"] != f"e12a6:authorization-consumed:{receipt_id}"):
                    raise ZPCMError("authorization consumption index data is malformed")
                existing = self.db.execute(
                    "SELECT receipt_id,nonce,event_id,scope FROM e12a6_authorization_consumptions "
                    "WHERE receipt_id=? OR nonce=? OR event_id=?",
                    (receipt_id, nonce, row["event_id"]),
                ).fetchone()
                expected = (receipt_id, nonce, row["event_id"], row["scope"])
                if existing is not None:
                    actual = (existing["receipt_id"], existing["nonce"], existing["event_id"], existing["scope"])
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
        raw=canonical(payload); d=digest(payload)
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
        """Keyset-page a stable snapshot of one typed event stream.

        The high-water mark is captured once, so concurrent appends do not
        extend this iteration indefinitely. Each page is fetched and released
        before yielding; memory use is bounded by page_size decoded events.
        """
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
                    "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                    "FROM memory_events WHERE event_type=? AND scope=? AND seq>? AND seq<=? "
                    "ORDER BY seq LIMIT ?",
                    (event_type, scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                payload = json.loads(row["payload_json"])
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

    def replay_domain_events(self, *, event_type: str, scope: str,
                             after_sequence: int = 0) -> list[dict[str, Any]]:
        """Materialize a complete typed stream; prefer iter_domain_events for bounded reads."""
        return list(self.iter_domain_events(
            event_type=event_type, scope=scope, after_sequence=after_sequence,
        ))

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
        """Keyset-page a stable snapshot of one typed event stream.

        The high-water mark is captured once, so concurrent appends do not
        extend this iteration indefinitely. Each page is fetched and released
        before yielding; memory use is bounded by page_size decoded events.
        """
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
                    "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                    "FROM memory_events WHERE event_type=? AND scope=? AND seq>? AND seq<=? "
                    "ORDER BY seq LIMIT ?",
                    (event_type, scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                payload = json.loads(row["payload_json"])
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

    def replay_domain_events(self, *, event_type: str, scope: str,
                             after_sequence: int = 0) -> list[dict[str, Any]]:
        """Materialize a complete typed stream; prefer iter_domain_events for bounded reads."""
        return list(self.iter_domain_events(
            event_type=event_type, scope=scope, after_sequence=after_sequence,
        ))

    def get_domain_event(
        self, *, event_type: str, scope: str, event_id: str,
    ) -> dict[str, Any] | None:
        """Fetch one indexed event without replaying or materializing its stream."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ZPCMError("event_id must be non-empty")
        with self.lock:
            row = self.db.execute(
                "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                "FROM memory_events WHERE event_id=? AND event_type=? AND scope=?",
                (event_id, event_type, scope),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if digest(payload) != row["payload_digest"]:
            raise ZPCMError(f"domain event digest mismatch: {event_id}")
        return {
            "sequence": row["seq"], "event_id": row["event_id"],
            "event_type": row["event_type"], "scope": row["scope"],
            "payload": payload, "payload_digest": row["payload_digest"],
            "recorded_at": row["recorded_at"],
        }

    def iter_domain_events_reverse(
        self, *, event_type: str, scope: str, before_sequence: int | None = None,
        page_size: int = 128,
    ) -> Iterator[dict[str, Any]]:
        """Keyset-page one typed event stream newest-first with bounded memory."""
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
                    "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                    "FROM memory_events WHERE event_type=? AND scope=? AND seq<? AND seq<=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (event_type, scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                payload = json.loads(row["payload_json"])
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
        """Fetch one indexed event without replaying or materializing its stream."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ZPCMError("event_type must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ZPCMError("scope must be non-empty")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ZPCMError("event_id must be non-empty")
        with self.lock:
            row = self.db.execute(
                "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                "FROM memory_events WHERE event_id=? AND event_type=? AND scope=?",
                (event_id, event_type, scope),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if digest(payload) != row["payload_digest"]:
            raise ZPCMError(f"domain event digest mismatch: {event_id}")
        return {
            "sequence": row["seq"], "event_id": row["event_id"],
            "event_type": row["event_type"], "scope": row["scope"],
            "payload": payload, "payload_digest": row["payload_digest"],
            "recorded_at": row["recorded_at"],
        }

    def iter_domain_events_reverse(
        self, *, event_type: str, scope: str, before_sequence: int | None = None,
        page_size: int = 128,
    ) -> Iterator[dict[str, Any]]:
        """Keyset-page one typed event stream newest-first with bounded memory."""
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
                    "SELECT seq,event_id,event_type,scope,payload_json,payload_digest,recorded_at "
                    "FROM memory_events WHERE event_type=? AND scope=? AND seq<? AND seq<=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (event_type, scope, cursor, high_water, page_size),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                payload = json.loads(row["payload_json"])
                if digest(payload) != row["payload_digest"]:
                    raise ZPCMError(f"domain event digest mismatch: {row['event_id']}")
                cursor = row["seq"]
                yield {
                    "sequence": row["seq"], "event_id": row["event_id"],
                    "event_type": row["event_type"], "scope": row["scope"],
                    "payload": payload, "payload_digest": row["payload_digest"],
                    "recorded_at": row["recorded_at"],
                }

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
