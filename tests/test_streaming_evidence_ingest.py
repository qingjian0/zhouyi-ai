import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from prototype.streaming_evidence_ingest import (
    IngestContractError,
    SQLiteEvidenceIngestor,
)


class SQLiteEvidenceIngestorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "evidence.sqlite3"
        self.ingestor = SQLiteEvidenceIngestor(self.db_path)

    def test_streams_utf8_with_exact_byte_spans_and_stable_ids(self):
        source = ("甲乙丙丁🙂" * 100).encode("utf-8")
        result = self.ingestor.ingest(
            "doc-1", "fixture.txt", io.BytesIO(source), chunk_bytes=17,
            tokenizer=lambda text: len(text),
        )
        chunks = self.ingestor.get_chunks("doc-1", limit=1000)
        self.assertTrue(result.complete)
        self.assertEqual(b"".join(chunk.text.encode("utf-8") for chunk in chunks), source)
        self.assertEqual(chunks[0].byte_start, 0)
        self.assertEqual(chunks[-1].byte_end, len(source))
        self.assertTrue(all(chunk.byte_end - chunk.byte_start <= 17 for chunk in chunks))
        self.assertTrue(all(chunk.token_count == len(chunk.text) for chunk in chunks))
        for chunk in chunks:
            self.assertEqual(
                chunk.content_sha256,
                hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            )

    def test_resume_after_committed_batch_does_not_duplicate_chunks(self):
        source = ("alpha🙂beta\n" * 80).encode()
        first = self.ingestor.ingest(
            "doc-resume", "resume.txt", io.BytesIO(source),
            chunk_bytes=16, max_chunks=3,
        )
        self.assertFalse(first.complete)
        state_after_first = self.ingestor.document_state("doc-resume")
        second = self.ingestor.ingest(
            "doc-resume", "resume.txt", io.BytesIO(source),
            chunk_bytes=16,
        )
        self.assertTrue(second.complete)
        chunks = self.ingestor.get_chunks("doc-resume", limit=1000)
        self.assertEqual(len(chunks), len({chunk.chunk_id for chunk in chunks}))
        self.assertEqual(len(chunks), self.ingestor.document_state("doc-resume")[1])
        self.assertGreater(state_after_first[0], 0)
        self.assertEqual(b"".join(c.text.encode() for c in chunks), source)

    def test_completed_document_is_idempotent(self):
        source = io.BytesIO(b"repeat me")
        first = self.ingestor.ingest("doc-idem", "same.txt", source, chunk_bytes=4)
        second = self.ingestor.ingest(
            "doc-idem", "same.txt", io.BytesIO(b"repeat me"), chunk_bytes=4
        )
        self.assertTrue(first.complete)
        self.assertEqual(second.chunks_committed, 0)
        self.assertEqual(len(self.ingestor.get_chunks("doc-idem")), 3)

    def test_resume_rejects_changed_configuration(self):
        self.ingestor.ingest(
            "doc-config", "source.txt", io.BytesIO(b"abcdefgh"), chunk_bytes=4,
            max_chunks=1,
        )
        with self.assertRaises(IngestContractError):
            self.ingestor.ingest(
                "doc-config", "source.txt", io.BytesIO(b"abcdefgh"), chunk_bytes=8
            )

    def test_tokenizer_is_optional_and_invalid_counts_fail(self):
        self.ingestor.ingest("doc-no-tokenizer", "x", io.BytesIO(b"abc"), chunk_bytes=4)
        self.assertIsNone(self.ingestor.get_chunks("doc-no-tokenizer")[0].token_count)
        with self.assertRaises(IngestContractError):
            self.ingestor.ingest(
                "doc-bad-tokenizer", "x", io.BytesIO(b"abc"), chunk_bytes=4,
                tokenizer=lambda _: -1,
            )
        self.assertIsNone(self.ingestor.document_state("doc-bad-tokenizer"))

    def test_invalid_utf8_is_not_silently_replaced(self):
        with self.assertRaises(UnicodeDecodeError):
            self.ingestor.ingest(
                "doc-invalid", "bad.bin", io.BytesIO(b"ok\xffbad"), chunk_bytes=8
            )

        self.assertEqual(self.ingestor.document_state("doc-invalid"), (0, 0, False))
        self.assertEqual(self.ingestor.get_chunks("doc-invalid"), [])

    def test_non_seekable_stream_is_rejected(self):
        class NonSeekable(io.BytesIO):
            def seekable(self):
                return False
        with self.assertRaises(IngestContractError):
            self.ingestor.ingest("doc-stream", "x", NonSeekable(b"abc"), chunk_bytes=4)


if __name__ == "__main__":
    unittest.main()
