"""Crash-resumable, bounded-memory UTF-8 evidence ingestion backed by SQLite.

The reader stores raw text chunks and byte spans. Token counts are optional and
must come from a caller-supplied exact tokenizer; byte/character counts are
never presented as token counts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import sqlite3
from pathlib import Path
from typing import BinaryIO, Callable


Tokenizer = Callable[[str], int]


class IngestContractError(ValueError):
    """Raised when a document or stream violates the ingestion contract."""


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    chunks_committed: int
    next_byte_offset: int
    complete: bool
    token_count_known: bool


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    document_id: str
    ordinal: int
    byte_start: int
    byte_end: int
    text: str
    content_sha256: str
    token_count: int | None


def _read_utf8_chunk(stream: BinaryIO, offset: int, max_bytes: int) -> bytes:
    """Read at most max_bytes, ending only at a UTF-8 code-point boundary."""
    stream.seek(offset)
    data = stream.read(max_bytes + 4)
    if not data:
        return b""

    upper = min(max_bytes, len(data))
    lower = max(1, upper - 3)
    for size in range(upper, lower - 1, -1):
        candidate = data[:size]
        try:
            candidate.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            # Only an incomplete trailing code point can be repaired by
            # shortening the chunk. Interior invalid UTF-8 is a hard failure.
            if exc.reason != "unexpected end of data" or exc.start < size - 4:
                continue
        else:
            stream.seek(offset + size)
            return candidate

    # A short final read can be smaller than max_bytes. Validate it as-is so
    # malformed input is not silently skipped or replaced.
    if len(data) <= max_bytes:
        data.decode("utf-8", errors="strict")
        stream.seek(offset + len(data))
        return data
    raise IngestContractError("unable to find a valid UTF-8 chunk boundary")


class SQLiteEvidenceIngestor:
    """Persist source chunks and the resume cursor in one SQLite transaction.

    The input stream must be seekable and binary. The caller owns the stream
    and must provide the same source bytes when resuming a document ID.
    """

    DEFAULT_MAX_CHUNK_BYTES = 64 * 1024
    DEFAULT_MAX_PAGE_BYTES = 1024 * 1024
    MAX_PAGE_ROWS = 4096

    def __init__(
        self,
        database: str | Path,
        *,
        max_chunk_bytes: int = DEFAULT_MAX_CHUNK_BYTES,
        max_page_bytes: int = DEFAULT_MAX_PAGE_BYTES,
    ) -> None:
        if isinstance(max_chunk_bytes, bool) or not isinstance(max_chunk_bytes, int) or not 4 <= max_chunk_bytes <= self.DEFAULT_MAX_CHUNK_BYTES:
            raise IngestContractError("max_chunk_bytes must be between 4 and 65536")
        if isinstance(max_page_bytes, bool) or not isinstance(max_page_bytes, int) or not 1 <= max_page_bytes <= self.DEFAULT_MAX_PAGE_BYTES:
            raise IngestContractError("max_page_bytes must be between 1 and 1048576")
        self.database = str(database)
        self.max_chunk_bytes = max_chunk_bytes
        self.max_page_bytes = max_page_bytes
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30.0)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ingest_documents (
                    document_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    chunk_bytes INTEGER NOT NULL CHECK(chunk_bytes >= 4),
                    next_byte_offset INTEGER NOT NULL DEFAULT 0,
                    next_ordinal INTEGER NOT NULL DEFAULT 0,
                    complete INTEGER NOT NULL DEFAULT 0 CHECK(complete IN (0, 1)),
                    manifest_digest TEXT,
                    manifest_chunks INTEGER,
                    manifest_bytes INTEGER,
                    chunk_generation INTEGER NOT NULL DEFAULT 0,
                    manifest_generation INTEGER
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES ingest_documents(document_id),
                    ordinal INTEGER NOT NULL,
                    byte_start INTEGER NOT NULL,
                    byte_end INTEGER NOT NULL,
                    text_utf8 BLOB NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    token_count INTEGER,
                    UNIQUE(document_id, ordinal),
                    UNIQUE(document_id, byte_start, byte_end),
                    CHECK(byte_start >= 0 AND byte_end > byte_start),
                    CHECK(token_count IS NULL OR token_count >= 0)
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evidence_chunks_document_span
                ON evidence_chunks(document_id, byte_start, byte_end)
                """
            )
            document_columns = {
                row[1] for row in db.execute("PRAGMA table_info(ingest_documents)")
            }
            migrations = {
                "manifest_digest": "TEXT",
                "manifest_chunks": "INTEGER",
                "manifest_bytes": "INTEGER",
                "chunk_generation": "INTEGER NOT NULL DEFAULT 0",
                "manifest_generation": "INTEGER",
            }
            legacy_generation_column = "chunk_generation" not in document_columns
            for name, declaration in migrations.items():
                if name not in document_columns:
                    db.execute(
                        f"ALTER TABLE ingest_documents ADD COLUMN {name} {declaration}"
                    )
            # Older databases predate generation tracking. Seed the counter
            # from their committed rows exactly once, before installing the
            # manifest backfill below.
            if legacy_generation_column:
                db.execute(
                    """UPDATE ingest_documents
                       SET chunk_generation=(
                           SELECT COUNT(*) FROM evidence_chunks
                           WHERE evidence_chunks.document_id=ingest_documents.document_id
                       )
                       WHERE next_ordinal > 0"""
                )
            db.executescript("""
            CREATE TRIGGER IF NOT EXISTS evidence_chunk_generation_insert
            AFTER INSERT ON evidence_chunks
            BEGIN
                UPDATE ingest_documents SET chunk_generation=chunk_generation+1
                WHERE document_id=NEW.document_id;
            END;
            CREATE TRIGGER IF NOT EXISTS evidence_chunk_generation_update
            AFTER UPDATE ON evidence_chunks
            BEGIN
                UPDATE ingest_documents SET chunk_generation=chunk_generation+1
                WHERE document_id=OLD.document_id;
                UPDATE ingest_documents SET chunk_generation=chunk_generation+1
                WHERE document_id=NEW.document_id AND NEW.document_id<>OLD.document_id;
            END;
            CREATE TRIGGER IF NOT EXISTS evidence_chunk_generation_delete
            AFTER DELETE ON evidence_chunks
            BEGIN
                UPDATE ingest_documents SET chunk_generation=chunk_generation+1
                WHERE document_id=OLD.document_id;
            END;
            """)
            self._backfill_completed_manifests(db)

    @staticmethod
    def _manifest_from_rows(document_id: str, rows) -> tuple[str, int, int]:
        digest = hashlib.sha256()
        digest.update(b"zhouyi-evidence-document-manifest-v1\0")
        expected_ordinal = 0
        expected_start = 0
        for ordinal, start, end, chunk_id, content_sha256, text_utf8 in rows:
            raw = bytes(text_utf8)
            actual_digest = hashlib.sha256(raw).hexdigest()
            if (
                len(raw) > SQLiteEvidenceIngestor.DEFAULT_MAX_CHUNK_BYTES
                or ordinal != expected_ordinal or start != expected_start or end <= start
                or len(raw) != end - start or actual_digest != content_sha256
                or chunk_id != SQLiteEvidenceIngestor._chunk_id(
                    document_id, ordinal, content_sha256
                )
            ):
                raise IngestContractError(
                    "persisted evidence chunks do not match their immutable manifest fields"
                )
            digest.update(
                f"{ordinal}:{start}:{end}:{chunk_id}:{content_sha256}\n".encode("ascii")
            )
            expected_ordinal += 1
            expected_start = end
        if expected_ordinal == 0:
            raise IngestContractError("document has no committed evidence chunks")
        return "manifest-sha256:" + digest.hexdigest(), expected_ordinal, expected_start

    @classmethod
    def _store_manifest(cls, db: sqlite3.Connection, document_id: str) -> None:
        rows = db.execute(
            """SELECT ordinal,byte_start,byte_end,chunk_id,content_sha256,text_utf8
               FROM evidence_chunks WHERE document_id=? ORDER BY ordinal""",
            (document_id,),
        )
        manifest, chunks, byte_count = cls._manifest_from_rows(document_id, rows)
        generation = int(db.execute(
            "SELECT chunk_generation FROM ingest_documents WHERE document_id=?",
            (document_id,),
        ).fetchone()[0])
        db.execute(
            """UPDATE ingest_documents SET complete=1,manifest_digest=?,
               manifest_chunks=?,manifest_bytes=?,manifest_generation=?
               WHERE document_id=?""",
            (manifest, chunks, byte_count, generation, document_id),
        )

    @classmethod
    def _backfill_completed_manifests(cls, db: sqlite3.Connection) -> None:
        legacy = db.execute(
            """SELECT document_id FROM ingest_documents
               WHERE complete=1 AND manifest_digest IS NULL ORDER BY document_id"""
        )
        while True:
            batch = legacy.fetchmany(64)
            if not batch:
                break
            for (document_id,) in batch:
                db.execute("BEGIN IMMEDIATE")
                cls._store_manifest(db, document_id)
                db.commit()

    @staticmethod
    def _chunk_id(document_id: str, ordinal: int, digest: str) -> str:
        material = f"zhouyi-evidence-chunk-v1\0{document_id}\0{ordinal}\0{digest}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _verify_committed_prefix(
        db: sqlite3.Connection,
        document_id: str,
        stream: BinaryIO,
        expected_offset: int,
        expected_ordinal: int,
        chunk_bytes: int,
    ) -> None:
        """Re-hash the persisted prefix before resuming or declaring idempotence.

        This is O(bytes already ingested) I/O but O(chunk_bytes) memory. It
        prevents a reused document ID from silently appending a different
        source file to an existing evidence sequence.
        """
        cursor = 0
        ordinal = 0
        rows = db.execute(
            """SELECT ordinal, byte_start, byte_end, content_sha256, text_utf8
               FROM evidence_chunks WHERE document_id = ? ORDER BY ordinal""",
            (document_id,),
        )
        for stored_ordinal, start, end, expected_digest, stored_payload in rows:
            if (
                stored_ordinal != ordinal
                or start != cursor
                or end <= start
                or end - start > chunk_bytes
            ):
                raise IngestContractError("persisted evidence spans are not contiguous")
            stored_raw = bytes(stored_payload)
            if (
                len(stored_raw) != end - start
                or hashlib.sha256(stored_raw).hexdigest() != expected_digest
            ):
                raise IngestContractError("persisted evidence chunk failed content digest verification")
            stream.seek(start)
            raw = stream.read(end - start)
            if len(raw) != end - start:
                raise IngestContractError("source is shorter than the committed evidence prefix")
            if raw != stored_raw or hashlib.sha256(raw).hexdigest() != expected_digest:
                raise IngestContractError("source bytes differ from the committed evidence prefix")
            cursor = end
            ordinal += 1
        if cursor != expected_offset or ordinal != expected_ordinal:
            raise IngestContractError("persisted resume cursor does not match evidence chunks")
        stream.seek(expected_offset)

    @staticmethod
    def _all_token_counts_known(db: sqlite3.Connection, document_id: str) -> bool:
        total, missing = db.execute(
            """SELECT COUNT(*), SUM(CASE WHEN token_count IS NULL THEN 1 ELSE 0 END)
               FROM evidence_chunks WHERE document_id = ?""",
            (document_id,),
        ).fetchone()
        return bool(total) and int(missing or 0) == 0

    def ingest(
        self,
        document_id: str,
        source_name: str,
        stream: BinaryIO,
        *,
        chunk_bytes: int = 8192,
        tokenizer: Tokenizer | None = None,
        max_chunks: int | None = None,
    ) -> IngestResult:
        if not document_id or not document_id.strip():
            raise IngestContractError("document_id must be non-empty")
        if not source_name or not source_name.strip():
            raise IngestContractError("source_name must be non-empty")
        if (
            isinstance(chunk_bytes, bool) or not isinstance(chunk_bytes, int)
            or not 4 <= chunk_bytes <= self.max_chunk_bytes
        ):
            raise IngestContractError(
                f"chunk_bytes must be between 4 and configured max_chunk_bytes ({self.max_chunk_bytes})"
            )
        if max_chunks is not None and (
            isinstance(max_chunks, bool) or not isinstance(max_chunks, int) or max_chunks < 1
        ):
            raise IngestContractError("max_chunks must be a positive integer")
        if not stream.seekable():
            raise IngestContractError("source stream must be seekable")

        committed = 0
        with self._connect() as db:
            # Register the document independently. Every evidence chunk and
            # its resume cursor are then committed atomically as one unit.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT source_name, chunk_bytes, next_byte_offset, next_ordinal, complete
                   FROM ingest_documents WHERE document_id = ?""",
                (document_id,),
            ).fetchone()
            if row is None:
                db.execute(
                    """INSERT INTO ingest_documents
                       (document_id, source_name, chunk_bytes)
                       VALUES (?, ?, ?)""",
                    (document_id, source_name, chunk_bytes),
                )
                offset, ordinal, complete = 0, 0, 0
            else:
                old_source, old_chunk_bytes, offset, ordinal, complete = row
                if old_source != source_name or old_chunk_bytes != chunk_bytes:
                    raise IngestContractError(
                        "resume metadata mismatch: source_name and chunk_bytes are immutable"
                    )
                self._verify_committed_prefix(
                    db, document_id, stream, offset, ordinal, chunk_bytes
                )
                if complete:
                    db.commit()
                    token_counts_known = self._all_token_counts_known(db, document_id)
                    return IngestResult(document_id, 0, offset, True, token_counts_known)
            db.commit()

            stream.seek(offset)
            while max_chunks is None or committed < max_chunks:
                raw = _read_utf8_chunk(stream, offset, chunk_bytes)
                if not raw:
                    db.execute("BEGIN IMMEDIATE")
                    self._store_manifest(db, document_id)
                    db.commit()
                    complete = 1
                    break

                text = raw.decode("utf-8", errors="strict")
                digest = hashlib.sha256(raw).hexdigest()
                token_count = tokenizer(text) if tokenizer is not None else None
                if token_count is not None and (
                    isinstance(token_count, bool) or not isinstance(token_count, int) or token_count < 0
                ):
                    raise IngestContractError("tokenizer must return a non-negative integer")

                end = offset + len(raw)
                chunk_id = self._chunk_id(document_id, ordinal, digest)
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    """INSERT INTO evidence_chunks
                       (chunk_id, document_id, ordinal, byte_start, byte_end,
                        text_utf8, content_sha256, token_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (chunk_id, document_id, ordinal, offset, end, raw, digest, token_count),
                )
                next_ordinal = ordinal + 1
                db.execute(
                    """UPDATE ingest_documents
                       SET next_byte_offset = ?, next_ordinal = ?
                       WHERE document_id = ?""",
                    (end, next_ordinal, document_id),
                )
                db.commit()
                offset, ordinal = end, next_ordinal
                committed += 1

        with self._connect() as db:
            token_counts_known = self._all_token_counts_known(db, document_id)

        return IngestResult(
            document_id=document_id,
            chunks_committed=committed,
            next_byte_offset=offset,
            complete=bool(complete),
            token_count_known=token_counts_known,
        )

    def get_chunks(
        self, document_id: str, *, limit: int = 100, offset: int = 0,
        page_bytes: int | None = None,
    ) -> list[EvidenceChunk]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= self.MAX_PAGE_ROWS:
            raise ValueError(f"limit must be between 1 and {self.MAX_PAGE_ROWS}")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        budget = self.max_page_bytes if page_bytes is None else page_bytes
        if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= self.max_page_bytes:
            raise ValueError(f"page_bytes must be between 1 and configured max_page_bytes ({self.max_page_bytes})")
        result: list[EvidenceChunk] = []
        consumed = 0
        with self._connect() as db:
            # Pin a single WAL snapshot so the document generation check and
            # every payload read observe the same committed database state.
            db.execute("BEGIN")
            document = db.execute(
                """SELECT complete,next_byte_offset,next_ordinal,manifest_digest,
                          manifest_chunks,manifest_bytes,chunk_generation,manifest_generation
                   FROM ingest_documents WHERE document_id=?""",
                (document_id,),
            ).fetchone()
            if document is None:
                return result
            complete, next_offset, next_ordinal, manifest_digest, manifest_chunks, manifest_bytes, chunk_generation, manifest_generation = document
            if next_offset < 0 or next_ordinal < 0:
                raise IngestContractError(
                    "persisted evidence document cursor is invalid"
                )
            completed_manifest_invalid = bool(
                complete and (
                    not isinstance(manifest_digest, str)
                    or not manifest_digest.startswith("manifest-sha256:")
                    or manifest_chunks != next_ordinal
                    or manifest_bytes != next_offset
                    or chunk_generation != next_ordinal
                    or manifest_generation != chunk_generation
                )
            )
            if not complete and chunk_generation != next_ordinal:
                raise IngestContractError(
                    "persisted evidence chunk generation does not match the document cursor"
                )
            elif (
                manifest_digest is not None or manifest_chunks is not None
                or manifest_bytes is not None or manifest_generation is not None
            ):
                raise IngestContractError(
                    "incomplete evidence document unexpectedly has a finalized manifest"
                )
            metadata = db.execute(
                """SELECT chunk_id,document_id,ordinal,byte_start,byte_end,
                          content_sha256,token_count,length(text_utf8)
                   FROM evidence_chunks WHERE document_id=?
                   ORDER BY ordinal LIMIT ? OFFSET ?""",
                (document_id, limit, offset),
            )
            for row in metadata:
                payload_bytes = int(row[7])
                if payload_bytes > self.max_chunk_bytes:
                    raise IngestContractError("persisted evidence chunk exceeds configured hard chunk limit")
                if payload_bytes > budget - consumed:
                    if not result:
                        raise IngestContractError("single evidence chunk exceeds requested page byte budget")
                    break
                payload = db.execute(
                    "SELECT text_utf8 FROM evidence_chunks WHERE document_id=? AND chunk_id=?",
                    (document_id, row[0]),
                ).fetchone()
                if payload is None:
                    raise IngestContractError("evidence chunk disappeared during page read")
                raw = bytes(payload[0])
                if len(raw) != payload_bytes:
                    raise IngestContractError("evidence chunk byte length changed during page read")
                if hashlib.sha256(raw).hexdigest() != row[5]:
                    raise IngestContractError("persisted evidence chunk failed content digest verification")
                if row[2] < 0 or row[4] - row[3] != payload_bytes:
                    raise IngestContractError("persisted evidence chunk byte span is inconsistent")
                if row[0] != self._chunk_id(row[1], row[2], row[5]):
                    raise IngestContractError("persisted evidence chunk ID is inconsistent")
                try:
                    decoded = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise IngestContractError("persisted evidence chunk is not valid UTF-8") from exc
                result.append(EvidenceChunk(
                    chunk_id=row[0], document_id=row[1], ordinal=row[2],
                    byte_start=row[3], byte_end=row[4], text=decoded,
                    content_sha256=row[5], token_count=row[6],
                ))
                consumed += payload_bytes
            # Prefer the specific chunk-digest failure when payload corruption
            # also makes the finalized manifest inconsistent.
            if completed_manifest_invalid:
                raise IngestContractError(
                    "completed evidence manifest is stale or inconsistent"
                )
        return result

    def document_state(self, document_id: str) -> tuple[int, int, bool] | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT next_byte_offset, next_ordinal, complete
                   FROM ingest_documents WHERE document_id = ?""",
                (document_id,),
            ).fetchone()
        return None if row is None else (int(row[0]), int(row[1]), bool(row[2]))
