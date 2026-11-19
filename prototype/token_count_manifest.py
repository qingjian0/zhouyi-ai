"""Versioned, source-bound persistence for exact document token counts.

Counts are computed over the complete logical document by an
IncrementalTokenizer, then committed only if the evidence manifest generation
is unchanged. Per-chunk counts are never summed.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from prototype.streaming_token_count import (
    IncrementalTokenizer,
    TokenStreamContractError,
    count_evidence_document,
)


class TokenCountManifestError(ValueError):
    """Raised when a token-count manifest cannot be safely created or read."""


@dataclass(frozen=True)
class TokenCountManifest:
    document_id: str
    tokenizer_id: str
    token_count: int
    characters: int
    chunks: int
    evidence_manifest_digest: str
    evidence_manifest_generation: int


def _connect(store):
    db = sqlite3.connect(store.database, timeout=30.0)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    return db


def _document_identity(db, document_id: str):
    row = db.execute(
        """SELECT complete,manifest_digest,chunk_generation,manifest_generation
           FROM ingest_documents WHERE document_id=?""",
        (document_id,),
    ).fetchone()
    if row is None:
        raise TokenCountManifestError("evidence document does not exist")
    complete, digest, generation, manifest_generation = row
    if not complete:
        raise TokenCountManifestError("evidence document is not complete")
    if (
        not isinstance(digest, str)
        or not digest.startswith("manifest-sha256:")
        or generation != manifest_generation
    ):
        raise TokenCountManifestError("evidence manifest is stale or inconsistent")
    return digest, int(generation)


def _ensure_table(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS document_token_counts (
            document_id TEXT NOT NULL
                REFERENCES ingest_documents(document_id) ON DELETE CASCADE,
            tokenizer_id TEXT NOT NULL CHECK(length(trim(tokenizer_id)) > 0),
            token_count INTEGER NOT NULL CHECK(token_count >= 0),
            characters INTEGER NOT NULL CHECK(characters >= 0),
            chunks INTEGER NOT NULL CHECK(chunks >= 0),
            evidence_manifest_digest TEXT NOT NULL,
            evidence_manifest_generation INTEGER NOT NULL CHECK(evidence_manifest_generation >= 0),
            PRIMARY KEY(document_id, tokenizer_id)
        )"""
    )


def count_and_persist_evidence_document(
    store,
    document_id: str,
    tokenizer: IncrementalTokenizer,
    *,
    page_size: int = 128,
) -> TokenCountManifest:
    """Count a complete document and persist only against its unchanged source."""
    tokenizer_id = getattr(tokenizer, "tokenizer_id", None)
    if not isinstance(tokenizer_id, str) or not tokenizer_id.strip():
        raise TokenCountManifestError("tokenizer_id must be stable and non-empty")

    with _connect(store) as db:
        db.execute("BEGIN")
        evidence_digest, evidence_generation = _document_identity(db, document_id)
        _ensure_table(db)
        db.commit()

    result = count_evidence_document(
        store, document_id, tokenizer, page_size=page_size
    )
    if result.tokenizer_id != tokenizer_id:
        raise TokenCountManifestError("tokenizer identity changed during counting")

    manifest = TokenCountManifest(
        document_id=document_id,
        tokenizer_id=tokenizer_id,
        token_count=result.token_count,
        characters=result.characters,
        chunks=result.chunks,
        evidence_manifest_digest=evidence_digest,
        evidence_manifest_generation=evidence_generation,
    )

    with _connect(store) as db:
        db.execute("BEGIN IMMEDIATE")
        current_digest, current_generation = _document_identity(db, document_id)
        if (
            current_digest != evidence_digest
            or current_generation != evidence_generation
        ):
            raise TokenCountManifestError(
                "evidence changed while token counting; result was not persisted"
            )
        _ensure_table(db)
        db.execute(
            """INSERT INTO document_token_counts
               (document_id,tokenizer_id,token_count,characters,chunks,
                evidence_manifest_digest,evidence_manifest_generation)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(document_id,tokenizer_id) DO UPDATE SET
                 token_count=excluded.token_count,
                 characters=excluded.characters,
                 chunks=excluded.chunks,
                 evidence_manifest_digest=excluded.evidence_manifest_digest,
                 evidence_manifest_generation=excluded.evidence_manifest_generation""",
            (
                manifest.document_id, manifest.tokenizer_id,
                manifest.token_count, manifest.characters, manifest.chunks,
                manifest.evidence_manifest_digest,
                manifest.evidence_manifest_generation,
            ),
        )
        db.commit()
    return manifest


def get_token_count_manifest(
    store, document_id: str, tokenizer_id: str
) -> TokenCountManifest | None:
    """Return a count only while its source evidence identity remains current."""
    if not isinstance(tokenizer_id, str) or not tokenizer_id.strip():
        raise TokenCountManifestError("tokenizer_id must be stable and non-empty")
    with _connect(store) as db:
        db.execute("BEGIN")
        try:
            digest, generation = _document_identity(db, document_id)
        except TokenCountManifestError:
            return None
        row = db.execute(
            """SELECT token_count,characters,chunks,evidence_manifest_digest,
                      evidence_manifest_generation
               FROM document_token_counts
               WHERE document_id=? AND tokenizer_id=?""",
            (document_id, tokenizer_id),
        ).fetchone()
        if row is None:
            return None
        count, characters, chunks, stored_digest, stored_generation = row
        if stored_digest != digest or stored_generation != generation:
            return None
        return TokenCountManifest(
            document_id=document_id,
            tokenizer_id=tokenizer_id,
            token_count=int(count),
            characters=int(characters),
            chunks=int(chunks),
            evidence_manifest_digest=stored_digest,
            evidence_manifest_generation=int(stored_generation),
        )
