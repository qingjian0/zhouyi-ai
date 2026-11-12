"""Read-only resolver from M2 EvidenceRef to the immutable M1 SQLite chunks.

The document version is a deterministic manifest hash over the complete ordered
chunk sequence. Resolution verifies every stored chunk byte-for-byte and keeps
working memory bounded by one chunk.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import sqlite3
from pathlib import Path

from prototype.observation_contract import ContractError, EvidenceRef


class EvidenceResolutionError(ContractError):
    """An EvidenceRef cannot be proven against the M1 evidence database."""


@dataclass(frozen=True)
class ResolvedEvidence:
    reference: EvidenceRef
    text: str
    ordinal: int


def _manifest_digest(document_id: str, rows) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    digest.update(b"zhouyi-evidence-document-manifest-v1\0")
    expected_ordinal = 0
    expected_start = 0
    for ordinal, start, end, chunk_id, content_sha256, text_utf8 in rows:
        if ordinal != expected_ordinal or start != expected_start or end <= start:
            raise EvidenceResolutionError("M1 evidence chunks are not a contiguous ordered sequence")
        raw = bytes(text_utf8)
        actual_digest = hashlib.sha256(raw).hexdigest()
        if len(raw) != end - start or actual_digest != content_sha256:
            raise EvidenceResolutionError("M1 stored chunk bytes do not match their committed span/hash")
        material = f"zhouyi-evidence-chunk-v1\0{document_id}\0{ordinal}\0{content_sha256}"
        expected_chunk_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
        if chunk_id != expected_chunk_id:
            raise EvidenceResolutionError("M1 chunk ID does not match its immutable identity fields")
        digest.update(
            f"{ordinal}:{start}:{end}:{chunk_id}:{content_sha256}\n".encode("ascii")
        )
        expected_ordinal += 1
        expected_start = end
    if expected_ordinal == 0:
        raise EvidenceResolutionError("document has no committed evidence chunks")
    return "manifest-sha256:" + digest.hexdigest(), expected_ordinal, expected_start


class SQLiteEvidenceRefResolver:
    """Resolve a single M1 chunk while keeping memory bounded by chunk size.

    Resolution is restricted to completed documents so the manifest version
    cannot change underneath a reference while ingestion is still in progress.
    """

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=30.0)
        db.execute("PRAGMA query_only = ON")
        db.execute("PRAGMA busy_timeout = 30000")
        return db

    def document_version(self, document_id: str) -> str:
        if not isinstance(document_id, str) or not document_id.strip():
            raise EvidenceResolutionError("document_id must be non-empty")
        with self._connect() as db:
            state = db.execute(
                "SELECT next_byte_offset, next_ordinal, complete FROM ingest_documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if state is None:
                raise EvidenceResolutionError("unknown M1 document")
            if not bool(state[2]):
                raise EvidenceResolutionError("cannot version an incomplete M1 document")
            rows = db.execute(
                """SELECT ordinal, byte_start, byte_end, chunk_id, content_sha256, text_utf8
                   FROM evidence_chunks WHERE document_id = ? ORDER BY ordinal""",
                (document_id,),
            )
            digest, manifest_chunks, manifest_bytes = _manifest_digest(document_id, rows)
            if manifest_chunks != int(state[1]) or manifest_bytes != int(state[0]):
                raise EvidenceResolutionError("durable document cursor does not match the evidence manifest")
            return digest

    def make_reference(self, document_id: str, chunk_id: str) -> EvidenceRef:
        version = self.document_version(document_id)
        with self._connect() as db:
            row = db.execute(
                """SELECT byte_start, byte_end, content_sha256
                   FROM evidence_chunks WHERE document_id = ? AND chunk_id = ?""",
                (document_id, chunk_id),
            ).fetchone()
        if row is None:
            raise EvidenceResolutionError("chunk does not belong to the requested document")
        return EvidenceRef(
            document_id=document_id,
            chunk_id=chunk_id,
            content_sha256=str(row[2]),
            byte_start=int(row[0]),
            byte_end=int(row[1]),
            source_version=version,
        )

    def resolve(self, reference: EvidenceRef) -> ResolvedEvidence:
        if not isinstance(reference, EvidenceRef):
            raise EvidenceResolutionError("reference must be an EvidenceRef")
        current_version = self.document_version(reference.document_id)
        if current_version != reference.source_version:
            raise EvidenceResolutionError("EvidenceRef source version is stale or does not match M1")
        with self._connect() as db:
            row = db.execute(
                """SELECT ordinal, byte_start, byte_end, text_utf8, content_sha256
                   FROM evidence_chunks
                   WHERE document_id = ? AND chunk_id = ?""",
                (reference.document_id, reference.chunk_id),
            ).fetchone()
        if row is None:
            raise EvidenceResolutionError("EvidenceRef chunk was not found")
        ordinal, start, end, raw_blob, stored_digest = row
        raw = bytes(raw_blob)
        actual_digest = hashlib.sha256(raw).hexdigest()
        if (int(start), int(end)) != (reference.byte_start, reference.byte_end):
            raise EvidenceResolutionError("EvidenceRef byte span does not match the stored chunk")
        if stored_digest != reference.content_sha256 or actual_digest != stored_digest:
            raise EvidenceResolutionError("EvidenceRef content hash does not match stored source bytes")
        if len(raw) != int(end) - int(start):
            raise EvidenceResolutionError("stored chunk byte length does not match its span")
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise EvidenceResolutionError("stored evidence chunk is not valid UTF-8") from exc
        return ResolvedEvidence(reference=reference, text=text, ordinal=int(ordinal))
