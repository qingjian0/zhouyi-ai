"""End-to-end tests for the M1 streaming-ingest benchmark CLI."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StreamingIngestBenchmarkTests(unittest.TestCase):
    def test_cli_creates_missing_database_parent_and_reports_complete_ingest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_bytes(("类象与证据🙂\n" * 40).encode("utf-8"))
            database = root / "new-output" / "nested" / "evidence.sqlite3"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "prototype.benchmark_streaming_ingest",
                    str(source),
                    str(database),
                    "--document-id",
                    "benchmark-test-v1",
                    "--chunk-bytes",
                    "16",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertTrue(database.is_file())
            self.assertTrue(report["complete"])
            self.assertEqual(report["source_bytes"], source.stat().st_size)
            self.assertGreater(report["chunks_committed"], 1)
            self.assertFalse(report["tokenizer_configured"])
            self.assertFalse(report["all_persisted_token_counts_known"])
            self.assertGreater(report["database_bytes"], 0)

    def test_cli_rejects_existing_database_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_bytes(b"test")
            database = root / "existing.sqlite3"
            database.write_bytes(b"do-not-overwrite")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "prototype.benchmark_streaming_ingest",
                    str(source),
                    str(database),
                    "--document-id",
                    "benchmark-existing-v1",
                    "--json",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("database already exists", completed.stderr)
            self.assertEqual(database.read_bytes(), b"do-not-overwrite")


if __name__ == "__main__":
    unittest.main()
