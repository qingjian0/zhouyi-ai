import io
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import EvidenceResolutionError, SQLiteEvidenceRefResolver
from prototype.m2_observation_store import (
    ObservationStoreError,
    PersistentM2ObservationStore,
)
from prototype.observation_contract import (
    ExtractionMethod,
    Modality,
    Observation,
    ParseStatus,
    RecordEnvelope,
    SourceLocator,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


class PersistentM2ObservationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.evidence_db = root / "evidence.sqlite3"
        self.memory_db = root / "zpcm.sqlite3"
        ingestor = SQLiteEvidenceIngestor(self.evidence_db)
        source = "甲使用工具处理乙".encode("utf-8")
        result = ingestor.ingest("doc-1", "fixture.txt", io.BytesIO(source), chunk_bytes=128)
        self.assertTrue(result.complete)
        chunk = ingestor.get_chunks("doc-1")[0]
        self.resolver = SQLiteEvidenceRefResolver(self.evidence_db)
        self.reference = self.resolver.make_reference("doc-1", chunk.chunk_id)
        self.memory = ZPCMMemory(self.memory_db)
        self.store = PersistentM2ObservationStore(self.memory, self.resolver, scope="project-a")

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def make_observation(self, *, record_id="obs-1", extractor_version="1.0", scope="project-a"):
        return Observation(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1",
                record_id=record_id,
                record_kind="Observation",
                producer="test-extractor",
                producer_version=extractor_version,
                recorded_at="2026-11-12T00:00:00Z",
                scope=scope,
                source_refs=(self.reference,),
            ),
            modality=Modality.TEXT,
            source_locator=SourceLocator(
                Modality.TEXT,
                self.reference.source_version,
                byte_start=self.reference.byte_start,
                byte_end=self.reference.byte_end,
            ),
            extractor_id="test-extractor",
            extractor_version=extractor_version,
            extraction_method=ExtractionMethod.RULE,
            parse_status=ParseStatus.PARSED,
        )

    def test_persists_only_typed_reference_and_restores_after_reopen(self):
        observation = self.make_observation()
        receipt = self.store.record_observation(observation)
        self.assertFalse(receipt.replayed)
        event = self.memory.replay_domain_events(event_type="m2_observation", scope="project-a")[0]
        self.assertNotIn("甲使用工具处理乙", str(event))
        self.assertEqual(event["payload"]["body"]["envelope"]["source_refs"][0]["chunk_id"],
                         self.reference.chunk_id)

        self.memory.close()
        self.memory = ZPCMMemory(self.memory_db)
        restored = PersistentM2ObservationStore(self.memory, self.resolver, scope="project-a")
        self.assertEqual(restored.observations["obs-1"], observation)
        restored_receipt = next(restored._memory.iter_domain_events(
            event_type="m2_observation", scope="project-a", page_size=1,
        ))
        self.assertEqual(restored_receipt["event_id"], "m2:observation:obs-1")

    def test_constructor_does_not_eagerly_restore_observation_history(self):
        original = self.memory.iter_domain_events
        def forbidden_full_scan(**kwargs):
            raise AssertionError("constructor must not iterate observation history")
        self.memory.iter_domain_events = forbidden_full_scan
        try:
            store = PersistentM2ObservationStore(
                self.memory, self.resolver, scope="project-a",
            )
            self.assertFalse(hasattr(store, "_observations"))
        finally:
            self.memory.iter_domain_events = original

    def test_observations_are_available_as_a_lazy_paged_iterator(self):
        receipts = [
            self.store.record_observation(self.make_observation(record_id=f"obs-{i}"))
            for i in range(3)
        ]
        iterator = self.store.iter_observations(page_size=1)
        self.assertEqual(next(iterator).envelope.record_id, "obs-0")
        tail = list(self.store.iter_observations(
            after_sequence=receipts[0].sequence, page_size=1,
        ))
        self.assertEqual(
            [item.envelope.record_id for item in tail],
            ["obs-1", "obs-2"],
        )
        # The compatibility property is an explicit materializing snapshot.
        self.assertEqual(set(self.store.observations), {"obs-0", "obs-1", "obs-2"})

    def test_identical_retry_after_reopen_is_idempotent(self):
        observation = self.make_observation()
        first = self.store.record_observation(observation)
        self.memory.close()
        self.memory = ZPCMMemory(self.memory_db)
        restored = PersistentM2ObservationStore(
            self.memory, self.resolver, scope="project-a",
        )
        retry = restored.record_observation(observation)
        self.assertTrue(retry.replayed)
        self.assertEqual(retry.sequence, first.sequence)

    def test_identical_retry_is_idempotent_but_record_id_is_immutable(self):
        observation = self.make_observation()
        first = self.store.record_observation(observation)
        replay = self.store.record_observation(observation)
        self.assertFalse(first.replayed)
        self.assertTrue(replay.replayed)
        self.assertEqual(first.sequence, replay.sequence)
        with self.assertRaises(ObservationStoreError):
            self.store.record_observation(self.make_observation(extractor_version="2.0"))

    def test_rejects_wrong_scope_before_durable_append(self):
        with self.assertRaises(ObservationStoreError):
            self.store.record_observation(self.make_observation(scope="project-b"))
        self.assertEqual(
            self.memory.replay_domain_events(event_type="m2_observation", scope="project-a"),
            [],
        )

    def test_rejects_stale_or_corrupted_evidence_before_append(self):
        forged = type(self.reference)(
            document_id=self.reference.document_id,
            chunk_id=self.reference.chunk_id,
            content_sha256="0" * 64,
            byte_start=self.reference.byte_start,
            byte_end=self.reference.byte_end,
            source_version=self.reference.source_version,
        )
        observation = self.make_observation()
        object.__setattr__(observation.envelope, "source_refs", (forged,))
        with self.assertRaises(EvidenceResolutionError):
            self.store.record_observation(observation)
        self.assertEqual(
            self.memory.replay_domain_events(event_type="m2_observation", scope="project-a"),
            [],
        )

    def test_replay_fails_closed_if_evidence_is_corrupted_after_commit(self):
        observation = self.make_observation()
        self.store.record_observation(observation)
        import sqlite3
        with sqlite3.connect(self.evidence_db) as db:
            db.execute(
                "UPDATE evidence_chunks SET text_utf8 = ? WHERE chunk_id = ?",
                (b"tampered", self.reference.chunk_id),
            )
        self.memory.close()
        self.memory = ZPCMMemory(self.memory_db)
        restored = PersistentM2ObservationStore(self.memory, self.resolver, scope="project-a")
        with self.assertRaises(EvidenceResolutionError):
            list(restored.iter_observations(page_size=1))


if __name__ == "__main__":
    unittest.main()
