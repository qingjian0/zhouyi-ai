import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.e09_authority_services import E09VerifierService
from prototype.shared_evidence_protocol import SQLiteEvidenceReader, SQLiteEvidenceStore


class SQLiteEvidenceReaderTests(unittest.TestCase):
    def test_reader_replays_without_exposing_write_api(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "e09.sqlite"
            writer = SQLiteEvidenceStore(database)
            writer.close()

            reader = SQLiteEvidenceReader(database)
            try:
                self.assertEqual(reader.replay_episode("no-events"), [])
                self.assertFalse(hasattr(reader, "append_event"))
                self.assertFalse(hasattr(reader, "put_payload"))
                with self.assertRaises(sqlite3.OperationalError):
                    reader._db.execute("CREATE TABLE forbidden_write(id INTEGER)")
            finally:
                reader.close()

    def test_reader_requires_an_existing_database_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((FileNotFoundError, ValueError)):
                SQLiteEvidenceReader(Path(directory) / "missing.sqlite")

    def test_verifier_service_accepts_read_only_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "e09.sqlite"
            writer = SQLiteEvidenceStore(database)
            writer.close()
            reader = SQLiteEvidenceReader(database)
            try:
                verifier = E09VerifierService(
                    reader,
                    signature_verifier=lambda issuer_id, key_id, message, signature: False,
                    verifier_id="verifier-readonly-test",
                )
                self.assertEqual(verifier.verifier_id, "verifier-readonly-test")
                self.assertEqual(reader.replay_episode("episode-empty"), [])
            finally:
                reader.close()


if __name__ == "__main__":
    unittest.main()
