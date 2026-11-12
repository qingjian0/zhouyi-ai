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

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
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
                    complete INTEGER NOT NULL DEFAULT 0 CHECK(complete IN (0, 1))
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
            """SELECT ordinal, byte_start, byte_end, content_sha256
               FROM evidence_chunks WHERE document_id = ? ORDER BY ordinal""",
            (document_id,),
        )
        for stored_ordinal, start, end, expected_digest in rows:
            if (
                stored_ordinal != ordinal
                or start != cursor
                or end <= start
                or end - start > chunk_bytes
            ):
                raise IngestContractError("persisted evidence spans are not contiguous")
            stream.seek(start)
            raw = stream.read(end - start)
            if len(raw) != end - start:
                raise IngestContractError("source is shorter than the committed evidence prefix")
            if hashlib.sha256(raw).hexdigest() != expected_digest:
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
        if isinstance(chunk_bytes, bool) or not isinstance(chunk_bytes, int) or chunk_bytes < 4:
            raise IngestContractError("chunk_bytes must be an integer >= 4")
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
                    db.execute(
                        "UPDATE ingest_documents SET complete = 1 WHERE document_id = ?",
                        (document_id,),
                    )
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

    def get_chunks(self, document_id: str, *, limit: int = 100, offset: int = 0) -> list[EvidenceChunk]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        with self._connect() as db:
            rows = db.execute(
                """SELECT chunk_id, document_id, ordinal, byte_start, byte_end,
                          text_utf8, content_sha256, token_count
                   FROM evidence_chunks WHERE document_id = ?
                   ORDER BY ordinal LIMIT ? OFFSET ?""",
                (document_id, limit, offset),
            ).fetchall()
        return [
            EvidenceChunk(
                chunk_id=row[0], document_id=row[1], ordinal=row[2],
                byte_start=row[3], byte_end=row[4],
                text=bytes(row[5]).decode("utf-8"), content_sha256=row[6],
                token_count=row[7],
            )
            for row in rows
        ]

    def document_state(self, document_id: str) -> tuple[int, int, bool] | None:
        with self._connect() as db:
            row = db.execute(
                """SELECT next_byte_offset, next_ordinal, complete
                   FROM ingest_documents WHERE document_id = ?""",
                (document_id,),
            ).fetchone()
        return None if row is None else (int(row[0]), int(row[1]), bool(row[2]))
