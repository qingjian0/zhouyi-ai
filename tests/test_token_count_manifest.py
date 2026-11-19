import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.token_count_manifest import (
    TokenCountManifestError,
    count_and_persist_evidence_document,
    get_token_count_manifest,
)


class TinyExactTokenizer:
    tokenizer_id = "fixture-exact-v1"

    def __init__(self):
        self.pending = ""
        self.closed = False

    def feed(self, text, *, final=False):
        if self.closed:
            raise RuntimeError("already finalized")
        value = self.pending + text
        if final:
            self.closed = True
            self.pending = ""
            return tuple(ord(char) for char in value)
        self.pending = value[-1:] if value.endswith("~") else ""
        stable = value[:-1] if self.pending else value
        return tuple(ord(char) for char in stable)


class TokenCountManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "evidence.sqlite3"
        self.store = SQLiteEvidenceIngestor(
            self.db_path, max_chunk_bytes=8, max_page_bytes=8
        )
        self.store.ingest(
            "doc", "source.txt", io.BytesIO("alpha~beta🙂".encode()),
            chunk_bytes=5,
        )

    def test_persists_exact_count_bound_to_evidence_and_tokenizer(self):
        manifest = count_and_persist_evidence_document(
            self.store, "doc", TinyExactTokenizer(), page_size=1
        )
        self.assertEqual(manifest.tokenizer_id, TinyExactTokenizer.tokenizer_id)
        self.assertEqual(manifest.token_count, len("alpha~beta🙂"))
        self.assertEqual(manifest.characters, len("alpha~beta🙂"))
        self.assertEqual(manifest.chunks, len(self.store.get_chunks("doc", limit=100)))
        self.assertEqual(
            get_token_count_manifest(self.store, "doc", TinyExactTokenizer.tokenizer_id),
            manifest,
        )

    def test_different_tokenizer_identity_has_independent_manifest(self):
        count_and_persist_evidence_document(
            self.store, "doc", TinyExactTokenizer()
        )
        self.assertIsNone(
            get_token_count_manifest(self.store, "doc", "other-model@revision")
        )

    def test_evidence_mutation_invalidates_previously_persisted_count(self):
        count_and_persist_evidence_document(
            self.store, "doc", TinyExactTokenizer()
        )
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE ingest_documents SET manifest_digest=? WHERE document_id=?",
                ("manifest-sha256:changed-source-generation", "doc"),
            )
        self.assertIsNone(
            get_token_count_manifest(self.store, "doc", TinyExactTokenizer.tokenizer_id)
        )

    def test_incomplete_document_is_rejected(self):
        self.store.ingest(
            "partial", "partial.txt", io.BytesIO(b"abcdefghijk"),
            chunk_bytes=4, max_chunks=1,
        )
        with self.assertRaisesRegex(TokenCountManifestError, "not complete"):
            count_and_persist_evidence_document(
                self.store, "partial", TinyExactTokenizer()
            )


if __name__ == "__main__":
    unittest.main()
