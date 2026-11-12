import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import (
    EvidenceResolutionError,
    SQLiteEvidenceRefResolver,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor


class SQLiteEvidenceRefResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "evidence.sqlite3"
        self.store = SQLiteEvidenceIngestor(self.database)
        self.resolver = SQLiteEvidenceRefResolver(self.database)

    def ingest_complete(self, document_id="doc-resolve"):
        source = "甲乙🙂丙丁戊".encode("utf-8")
        result = self.store.ingest(
            document_id, "fixture.txt", io.BytesIO(source), chunk_bytes=8
        )
        self.assertTrue(result.complete)
        return self.store.get_chunks(document_id, limit=100)

    def test_make_and_resolve_reference_round_trip(self):
        chunks = self.ingest_complete()
        chunk = chunks[1]
        ref = self.resolver.make_reference("doc-resolve", chunk.chunk_id)
        resolved = self.resolver.resolve(ref)
        self.assertEqual(resolved.text, chunk.text)
        self.assertEqual(resolved.ordinal, chunk.ordinal)
        self.assertEqual(ref.content_sha256, chunk.content_sha256)
        self.assertTrue(ref.source_version.startswith("manifest-sha256:"))

    def test_durable_cursor_must_match_manifest(self):
        self.ingest_complete()
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE ingest_documents SET next_ordinal = next_ordinal + 1 WHERE document_id = ?",
                ("doc-resolve",),
            )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.document_version("doc-resolve")

    def test_incomplete_document_cannot_be_versioned_or_resolved(self):
        self.store.ingest(
            "doc-incomplete", "fixture.txt", io.BytesIO(b"abcdefghijk"),
            chunk_bytes=4, max_chunks=1,
        )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.document_version("doc-incomplete")

    def test_wrong_document_chunk_pair_is_rejected(self):
        self.ingest_complete("doc-a")
        self.ingest_complete("doc-b")
        chunk_a = self.store.get_chunks("doc-a")[0]
        ref_a = self.resolver.make_reference("doc-a", chunk_a.chunk_id)
        forged = type(ref_a)(
            document_id="doc-b",
            chunk_id=ref_a.chunk_id,
            content_sha256=ref_a.content_sha256,
            byte_start=ref_a.byte_start,
            byte_end=ref_a.byte_end,
            source_version=self.resolver.document_version("doc-b"),
        )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.resolve(forged)

    def test_stale_document_manifest_is_rejected(self):
        chunks = self.ingest_complete()
        ref = self.resolver.make_reference("doc-resolve", chunks[0].chunk_id)
        # Simulate corruption or an out-of-band mutation to committed metadata.
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE evidence_chunks SET content_sha256 = ? WHERE chunk_id = ?",
                ("0" * 64, chunks[0].chunk_id),
            )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.resolve(ref)

    def test_wrong_span_is_rejected(self):
        chunks = self.ingest_complete()
        ref = self.resolver.make_reference("doc-resolve", chunks[0].chunk_id)
        forged = type(ref)(
            document_id=ref.document_id,
            chunk_id=ref.chunk_id,
            content_sha256=ref.content_sha256,
            byte_start=ref.byte_start + 1,
            byte_end=ref.byte_end,
            source_version=ref.source_version,
        )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.resolve(forged)


    def test_tampering_in_another_chunk_invalidates_document_manifest(self):
        chunks = self.ingest_complete()
        ref = self.resolver.make_reference("doc-resolve", chunks[-1].chunk_id)
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE evidence_chunks SET text_utf8 = ? WHERE chunk_id = ?",
                (b"tampered!", chunks[0].chunk_id),
            )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.resolve(ref)

    def test_in_place_blob_tampering_is_detected(self):
        chunks = self.ingest_complete()
        ref = self.resolver.make_reference("doc-resolve", chunks[0].chunk_id)
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE evidence_chunks SET text_utf8 = ? WHERE chunk_id = ?",
                (b"tampered!", chunks[0].chunk_id),
            )
        with self.assertRaises(EvidenceResolutionError):
            self.resolver.resolve(ref)


if __name__ == "__main__":
    unittest.main()
