import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from prototype.e09_snapshot_publisher import (
    SnapshotPublicationError,
    SQLiteEvidenceSnapshotPublisher,
)
from prototype.shared_evidence_protocol import (
    SQLiteEvidenceReader,
    SQLiteEvidenceStore,
)


class SQLiteEvidenceSnapshotPublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "authority.sqlite3"
        self.snapshot = self.root / "verifier" / "evidence.sqlite3"
        self.snapshot.parent.mkdir(mode=0o700)
        self.store = SQLiteEvidenceStore(self.source)
        self.store.append_event(
            episode_id="episode-1",
            event_id="observation-1",
            event_type="observation",
            idempotency_key="observation-1",
            payload={"observation_id": "observation-1", "scope": "world/test"},
        )
        self.store.put_payload(
            __import__("prototype.shared_evidence_protocol", fromlist=["digest_payload"]).digest_payload(
                {"text": "private input"}
            ),
            {"text": "private input"},
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_publishes_standalone_read_only_consistent_snapshot(self):
        publication = SQLiteEvidenceSnapshotPublisher(self.source, self.snapshot).publish()
        self.assertEqual(publication.event_count, 1)
        self.assertEqual(publication.episode_count, 1)
        self.assertEqual(publication.journal_mode, "DELETE")
        self.assertEqual(publication.byte_size, self.snapshot.stat().st_size)
        self.assertEqual(stat.S_IMODE(self.snapshot.stat().st_mode), 0o600)
        self.assertTrue((self.snapshot.parent / (self.snapshot.name + ".lock")).exists())
        self.assertFalse(Path(str(self.snapshot) + "-wal").exists())
        self.assertFalse(Path(str(self.snapshot) + "-shm").exists())

        reader = SQLiteEvidenceReader(self.snapshot)
        try:
            events = reader.replay_episode("episode-1")
            self.assertEqual([event["event_id"] for event in events], ["observation-1"])
            with self.assertRaises(sqlite3.OperationalError):
                reader._db.execute("DELETE FROM events")
        finally:
            reader.close()

    def test_failed_publication_keeps_previous_snapshot_intact(self):
        SQLiteEvidenceSnapshotPublisher(self.source, self.snapshot).publish()
        before = self.snapshot.read_bytes()
        invalid_source = self.root / "empty.sqlite3"
        sqlite3.connect(invalid_source).close()

        with self.assertRaises(SnapshotPublicationError):
            SQLiteEvidenceSnapshotPublisher(invalid_source, self.snapshot).publish()

        self.assertEqual(self.snapshot.read_bytes(), before)
        reader = SQLiteEvidenceReader(self.snapshot)
        try:
            self.assertEqual(len(reader.replay_episode("episode-1")), 1)
        finally:
            reader.close()

    def test_rejects_source_and_destination_alias(self):
        with self.assertRaises(SnapshotPublicationError):
            SQLiteEvidenceSnapshotPublisher(self.source, self.source)

    def test_rejects_symlink_source(self):
        link = self.root / "source-link.sqlite3"
        link.symlink_to(self.source)
        with self.assertRaises(SnapshotPublicationError):
            SQLiteEvidenceSnapshotPublisher(link, self.snapshot)

    def test_rejects_group_or_world_writable_snapshot_directory(self):
        unsafe = self.root / "unsafe"
        unsafe.mkdir(mode=0o700)
        unsafe.chmod(0o770)
        try:
            with self.assertRaises(SnapshotPublicationError):
                SQLiteEvidenceSnapshotPublisher(self.source, unsafe / "snapshot.sqlite3")
        finally:
            unsafe.chmod(0o700)

    def test_refuses_existing_destination_wal_sidecar(self):
        sidecar = Path(str(self.snapshot) + "-wal")
        sidecar.write_bytes(b"stale")
        try:
            with self.assertRaises(SnapshotPublicationError):
                SQLiteEvidenceSnapshotPublisher(self.source, self.snapshot).publish()
            self.assertFalse(self.snapshot.exists())
        finally:
            sidecar.unlink(missing_ok=True)

    def test_refuses_symlink_destination(self):
        real = self.root / "real.sqlite3"
        real.touch()
        link = self.root / "verifier" / "link.sqlite3"
        link.symlink_to(real)
        with self.assertRaises(SnapshotPublicationError):
            SQLiteEvidenceSnapshotPublisher(self.source, link)


if __name__ == "__main__":
    unittest.main()
