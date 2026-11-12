import hashlib
import io
import subprocess
import sys
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
        # Re-open the database through a fresh store instance to model
        # process restart rather than merely continuing the same object.
        restarted = SQLiteEvidenceIngestor(self.db_path)
        second = restarted.ingest(
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
        with self.assertRaises(IngestContractError):
            self.ingestor.ingest(
                "doc-idem", "same.txt", io.BytesIO(b"changed!"), chunk_bytes=4
            )

    def test_hard_process_exit_recovers_only_committed_chunks(self):
        source_path = Path(self.temp.name) / "crash-source.txt"
        source = b"01234567" * 30
        source_path.write_bytes(source)
        script = r"""
import os
import sys
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor

database, source_path = sys.argv[1], sys.argv[2]
calls = 0
def crash_on_fifth_chunk(text):
    global calls
    calls += 1
    if calls == 5:
        os._exit(73)
    return 1

store = SQLiteEvidenceIngestor(database)
with open(source_path, "rb") as stream:
    store.ingest("doc-hard-crash", source_path, stream,
                 chunk_bytes=8, tokenizer=crash_on_fifth_chunk)
"""
        child = subprocess.run(
            [sys.executable, "-c", script, str(self.db_path), str(source_path)],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
        )
        self.assertEqual(child.returncode, 73)
        restarted = SQLiteEvidenceIngestor(self.db_path)
        self.assertEqual(restarted.document_state("doc-hard-crash"), (32, 4, False))
        resumed = restarted.ingest(
            "doc-hard-crash", str(source_path), io.BytesIO(source), chunk_bytes=8
        )
        self.assertTrue(resumed.complete)
        chunks = restarted.get_chunks("doc-hard-crash", limit=1000)
        self.assertEqual(b"".join(chunk.text.encode() for chunk in chunks), source)
        self.assertEqual(len(chunks), 30)
        self.assertEqual(len({chunk.chunk_id for chunk in chunks}), 30)

    def test_hard_process_exit_recovers_across_multiple_commit_boundaries(self):
        source_path = Path(self.temp.name) / "multi-crash-source.txt"
        source = b"abcdefgh" * 15
        source_path.write_bytes(source)

        # Each value is the number of chunks committed before the child exits.
        # The callback exits before the next chunk's transaction begins.
        for committed_before_exit in (0, 1, 4, 8, 14):
            with self.subTest(committed_before_exit=committed_before_exit):
                database = Path(self.temp.name) / f"crash-{committed_before_exit}.sqlite3"
                script = r"""
import os
import sys
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor

database, source_path = sys.argv[1], sys.argv[2]
exit_on_call = int(sys.argv[3]) + 1
calls = 0
def crash_at_boundary(text):
    global calls
    calls += 1
    if calls == exit_on_call:
        os._exit(73)
    return 1

store = SQLiteEvidenceIngestor(database)
with open(source_path, "rb") as stream:
    store.ingest("doc-multi-crash", source_path, stream,
                 chunk_bytes=8, tokenizer=crash_at_boundary)
"""
                child = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        script,
                        str(database),
                        str(source_path),
                        str(committed_before_exit),
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    check=False,
                )
                self.assertEqual(child.returncode, 73)
                restarted = SQLiteEvidenceIngestor(database)
                self.assertEqual(
                    restarted.document_state("doc-multi-crash"),
                    (committed_before_exit * 8, committed_before_exit, False),
                )
                resumed = restarted.ingest(
                    "doc-multi-crash",
                    str(source_path),
                    io.BytesIO(source),
                    chunk_bytes=8,
                )
                self.assertTrue(resumed.complete)
                chunks = restarted.get_chunks("doc-multi-crash", limit=1000)
                self.assertEqual(len(chunks), 15)
                self.assertEqual(
                    b"".join(chunk.text.encode("utf-8") for chunk in chunks),
                    source,
                )
                self.assertEqual(
                    len({chunk.chunk_id for chunk in chunks}),
                    15,
                )
                self.assertEqual(
                    [(chunk.byte_start, chunk.byte_end) for chunk in chunks],
                    [(index * 8, (index + 1) * 8) for index in range(15)],
                )

    def test_tokenizer_coverage_reflects_persisted_chunks(self):
        source = io.BytesIO(b"abcdefgh")
        first = self.ingestor.ingest(
            "doc-token-coverage", "tokens.txt", source,
            chunk_bytes=4, max_chunks=1,
        )
        self.assertFalse(first.token_count_known)
        second = self.ingestor.ingest(
            "doc-token-coverage", "tokens.txt", io.BytesIO(b"abcdefgh"),
            chunk_bytes=4, tokenizer=lambda text: 2,
        )
        self.assertTrue(second.complete)
        self.assertFalse(second.token_count_known)
        chunks = self.ingestor.get_chunks("doc-token-coverage")
        self.assertIsNone(chunks[0].token_count)
        self.assertEqual(chunks[1].token_count, 2)

    def test_resume_rejects_changed_source_prefix(self):
        self.ingestor.ingest(
            "doc-source-change", "source.txt", io.BytesIO(b"abcdefghijk"),
            chunk_bytes=4, max_chunks=2,
        )
        with self.assertRaises(IngestContractError):
            self.ingestor.ingest(
                "doc-source-change", "source.txt", io.BytesIO(b"abXXefghijk"),
                chunk_bytes=4,
            )

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
        self.assertEqual(self.ingestor.document_state("doc-bad-tokenizer"), (0, 0, False))
        self.assertEqual(self.ingestor.get_chunks("doc-bad-tokenizer"), [])

    def test_invalid_utf8_is_not_silently_replaced(self):
        with self.assertRaises(UnicodeDecodeError):
            self.ingestor.ingest(
                "doc-invalid", "bad.bin", io.BytesIO(b"ok\xffbad"), chunk_bytes=8
            )

        # The whole bounded chunk is rejected; no partial source bytes
        # are persisted and the durable cursor remains unchanged.
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
