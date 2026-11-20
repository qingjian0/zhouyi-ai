"""Read-only resolver from M2 EvidenceRef to immutable M1 SQLite chunks.

Normal resolution checks the finalized manifest generation in bounded metadata
and hashes only the referenced chunk. Full-document byte verification remains
available as an explicit audit operation.
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
    """Resolve one bounded M1 chunk against a persisted document manifest."""

    MAX_CHUNK_BYTES = 64 * 1024

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=30.0)
        db.execute("PRAGMA query_only = ON")
        db.execute("PRAGMA busy_timeout = 30000")
        return db

    @staticmethod
    def _verified_document_version(db: sqlite3.Connection, document_id: str) -> str:
        """Validate finalized manifest metadata without scanning the document corpus.

        The ingestor's chunk-generation triggers invalidate the manifest whenever
        a chunk row is inserted, updated or deleted. The resolver is read-only;
        its normal trust boundary assumes only the ingestor can mutate this DB.
        """
        state = db.execute(
            """SELECT next_byte_offset,next_ordinal,complete,manifest_digest,
                      manifest_chunks,manifest_bytes,chunk_generation,manifest_generation
               FROM ingest_documents WHERE document_id=?""",
            (document_id,),
        ).fetchone()
        if state is None:
            raise EvidenceResolutionError("unknown M1 document")
        if not bool(state[2]):
            raise EvidenceResolutionError("cannot version an incomplete M1 document")
        if (
            not isinstance(state[3], str)
            or not state[3].startswith("manifest-sha256:")
            or len(state[3]) != len("manifest-sha256:") + 64
            or any(char not in "0123456789abcdef" for char in state[3][len("manifest-sha256:"):])
            or state[4] is None or state[5] is None or state[7] is None
        ):
            raise EvidenceResolutionError("durable document manifest is missing, stale, or invalid")
        try:
            next_bytes, next_chunks = int(state[0]), int(state[1])
            manifest_chunks, manifest_bytes = int(state[4]), int(state[5])
            chunk_generation, manifest_generation = int(state[6]), int(state[7])
        except (TypeError, ValueError, OverflowError) as exc:
            raise EvidenceResolutionError(
                "durable document manifest contains invalid metadata"
            ) from exc
        if (
            next_bytes < 1 or next_chunks < 1
            or manifest_chunks != next_chunks
            or manifest_bytes != next_bytes
            or chunk_generation != next_chunks
            or manifest_generation != chunk_generation
        ):
            raise EvidenceResolutionError(
                "durable document manifest generation or cursor is stale"
            )
        return str(state[3])

    @staticmethod
    def _verify_complete_document_manifest(
        db: sqlite3.Connection, document_id: str,
    ) -> str:
        """Re-hash every committed chunk for explicit integrity audits and repair."""
        version = SQLiteEvidenceRefResolver._verified_document_version(db, document_id)
        state = db.execute(
            """SELECT next_byte_offset,next_ordinal,manifest_chunks,manifest_bytes
               FROM ingest_documents WHERE document_id=?""",
            (document_id,),
        ).fetchone()
        actual_digest, actual_chunks, actual_bytes = _manifest_digest(
            document_id,
            db.execute(
                """SELECT ordinal,byte_start,byte_end,chunk_id,content_sha256,text_utf8
                   FROM evidence_chunks WHERE document_id=? ORDER BY ordinal""",
                (document_id,),
            ),
        )
        if (
            actual_digest != version
            or actual_chunks != int(state[1])
            or actual_chunks != int(state[2])
            or actual_bytes != int(state[0])
            or actual_bytes != int(state[3])
        ):
            raise EvidenceResolutionError(
                "durable document manifest does not match its complete chunk sequence"
            )
        return version

    def verify_document_manifest(self, document_id: str) -> str:
        """Perform an explicit full-document integrity audit (O(document bytes))."""
        if not isinstance(document_id, str) or not document_id.strip():
            raise EvidenceResolutionError("document_id must be non-empty")
        with self._connect() as db:
            db.execute("BEGIN")
            return self._verify_complete_document_manifest(db, document_id)

    def document_version(self, document_id: str) -> str:
        if not isinstance(document_id, str) or not document_id.strip():
            raise EvidenceResolutionError("document_id must be non-empty")
        with self._connect() as db:
            db.execute("BEGIN")
            return self._verified_document_version(db, document_id)

    def make_reference(self, document_id: str, chunk_id: str) -> EvidenceRef:
        if not isinstance(document_id, str) or not document_id.strip():
            raise EvidenceResolutionError("document_id must be non-empty")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise EvidenceResolutionError("chunk_id must be non-empty")
        with self._connect() as db:
            db.execute("BEGIN")
            version = self._verified_document_version(db, document_id)
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

    def resolve_many(self, references: list[EvidenceRef]) -> list[ResolvedEvidence]:
        """Resolve references with one bounded manifest-metadata check per document.

        Results preserve input order. Repeated references are independently returned,
        while each distinct document's generation metadata is checked only once.
        Each requested chunk is still independently length/hash/UTF-8 verified.
        """
        if not isinstance(references, list):
            raise EvidenceResolutionError("references must be a list")
        if any(not isinstance(reference, EvidenceRef) for reference in references):
            raise EvidenceResolutionError("every reference must be an EvidenceRef")
        if not references:
            return []
        with self._connect() as db:
            db.execute("BEGIN")
            versions: dict[str, str] = {}
            resolved: list[ResolvedEvidence] = []
            for reference in references:
                current_version = versions.get(reference.document_id)
                if current_version is None:
                    current_version = self._verified_document_version(
                        db, reference.document_id
                    )
                    versions[reference.document_id] = current_version
                if current_version != reference.source_version:
                    raise EvidenceResolutionError(
                        "EvidenceRef source version is stale or does not match M1"
                    )
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
                if len(raw) > self.MAX_CHUNK_BYTES:
                    raise EvidenceResolutionError("stored evidence chunk exceeds hard chunk byte limit")
                actual_digest = hashlib.sha256(raw).hexdigest()
                if (int(start), int(end)) != (reference.byte_start, reference.byte_end):
                    raise EvidenceResolutionError("EvidenceRef byte span does not match the stored chunk")
                if stored_digest != reference.content_sha256 or actual_digest != stored_digest:
                    raise EvidenceResolutionError("EvidenceRef content hash does not match stored source bytes")
                if len(raw) != int(end) - int(start):
                    raise EvidenceResolutionError("stored chunk byte length does not match its span")
                try:
                    decoded = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise EvidenceResolutionError("stored evidence chunk is not valid UTF-8") from exc
                resolved.append(ResolvedEvidence(reference=reference, text=decoded, ordinal=int(ordinal)))
            return resolved

    def resolve(self, reference: EvidenceRef) -> ResolvedEvidence:
        if not isinstance(reference, EvidenceRef):
            raise EvidenceResolutionError("reference must be an EvidenceRef")
        return self.resolve_many([reference])[0]

