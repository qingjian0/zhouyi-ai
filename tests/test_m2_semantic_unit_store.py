import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import EvidenceResolutionError, SQLiteEvidenceRefResolver
from prototype.m2_semantic_unit_store import (
    PersistentM2SemanticUnitStore, SemanticUnitStoreError,
)
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope, RoleBinding,
    SemanticUnitCandidate, TruthStatus, TypedAttribute, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


class PersistentM2SemanticUnitStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.evidence_db, self.memory_db = root / "evidence.sqlite3", root / "zpcm.sqlite3"
        ingestor = SQLiteEvidenceIngestor(self.evidence_db)
        source = "甲使用工具处理乙".encode("utf-8")
        self.assertTrue(ingestor.ingest("doc-1", "fixture.txt", io.BytesIO(source),
                                        chunk_bytes=128).complete)
        chunk = ingestor.get_chunks("doc-1")[0]
        self.resolver = SQLiteEvidenceRefResolver(self.evidence_db)
        self.reference = self.resolver.make_reference("doc-1", chunk.chunk_id)
        self.memory = ZPCMMemory(self.memory_db)
        self.store = PersistentM2SemanticUnitStore(self.memory, self.resolver, scope="project-a")

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def candidate(self, rid, *, predecessor=None, surface="使用工具",
                   confidence=0.8, scope="project-a"):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1", record_id=rid,
                record_kind="SemanticUnitCandidate", producer="test-extractor",
                producer_version="1.0", recorded_at="2026-11-12T00:00:00Z",
                scope=scope, source_refs=(self.reference,),
                derivation_refs=("obs-1",) + ((predecessor,) if predecessor else ()),
            ),
            kind=UnitKind.EVENT, surface_forms=(surface,),
            typed_attributes=(TypedAttribute(
                "agent", "entity_ref", "entity:甲", source_refs=(self.reference,)),),
            role_bindings=(RoleBinding("agent", "entity:甲"),
                           RoleBinding("patient", "entity:乙")),
            grounding_status=GroundingStatus.GROUNDED,
            epistemic_status=EpistemicStatus.ASSERTED,
            extractor_confidence=confidence,
            truth_status=TruthStatus.UNKNOWN,
        )

    def test_candidate_round_trip_and_idempotency(self):
        candidate = self.candidate("su-1")
        first = self.store.record_candidate(candidate)
        retry = self.store.record_candidate(candidate)
        self.assertFalse(first.replayed)
        self.assertTrue(retry.replayed)
        self.assertEqual(first.sequence, retry.sequence)
        self.assertEqual(self.store.candidates["su-1"], candidate)
        events = self.memory.replay_domain_events(event_type="m2_semantic_unit", scope="project-a")
        self.assertEqual(len(events), 1)
        self.assertNotIn("甲使用工具处理乙", str(events[0]["payload"]))

    def test_revision_is_append_only_and_restores_latest_version(self):
        first = self.candidate("su-1")
        self.store.record_candidate(first)
        revised = self.candidate("su-2", predecessor="su-1",
                                 surface="通过工具", confidence=0.9)
        receipt = self.store.revise_candidate("su-1", revised)
        retry = self.store.revise_candidate("su-1", revised)
        self.assertFalse(receipt.replayed)
        self.assertTrue(retry.replayed)
        self.assertEqual(receipt.sequence, retry.sequence)
        self.assertEqual(self.store.history, {"su-1": first, "su-2": revised})
        self.assertEqual(self.store.candidates, {"su-1": revised})
        with self.assertRaises(SemanticUnitStoreError):
            self.store.record_candidate(revised)
        with self.assertRaises(SemanticUnitStoreError):
            self.store.revise_candidate("obs-1", revised)
        self.assertEqual(len(self.memory.replay_domain_events(
            event_type="m2_semantic_unit", scope="project-a")), 2)
        self.memory.close()
        self.memory = ZPCMMemory(self.memory_db)
        restored = PersistentM2SemanticUnitStore(
            self.memory, self.resolver, scope="project-a", replay_page_size=1)
        self.assertEqual(restored.history, {"su-1": first, "su-2": revised})
        self.assertEqual(restored.candidates, {"su-1": revised})
        self.assertTrue(restored._receipts["su-2"].replayed)

    def test_revision_requires_explicit_predecessor_and_new_immutable_id(self):
        self.store.record_candidate(self.candidate("su-1"))
        with self.assertRaises(SemanticUnitStoreError):
            self.store.revise_candidate("su-1", self.candidate("su-2"))
        with self.assertRaises(SemanticUnitStoreError):
            self.store.revise_candidate("su-1", self.candidate("su-1", predecessor="su-1"))

    def test_retraction_is_tombstone_and_never_deletes_history(self):
        candidate = self.candidate("su-1")
        self.store.record_candidate(candidate)
        receipt = self.store.retract_candidate("su-1", reason="source contradicted")
        retry = self.store.retract_candidate("su-1", reason="source contradicted")
        self.assertFalse(receipt.replayed)
        self.assertTrue(retry.replayed)
        self.assertEqual(self.store.candidates, {})
        self.assertEqual(self.store.history, {"su-1": candidate})
        with self.assertRaises(SemanticUnitStoreError):
            self.store.retract_candidate("su-1", reason="different reason")
        self.memory.close()
        self.memory = ZPCMMemory(self.memory_db)
        restored = PersistentM2SemanticUnitStore(self.memory, self.resolver, scope="project-a")
        self.assertEqual(restored.candidates, {})
        self.assertEqual(restored.retractions, {"su-1": "source contradicted"})

    def test_rejects_scope_mismatch_and_invalid_evidence(self):
        with self.assertRaises(SemanticUnitStoreError):
            self.store.record_candidate(self.candidate("bad-scope", scope="project-b"))
        forged = type(self.reference)(
            document_id=self.reference.document_id, chunk_id=self.reference.chunk_id,
            content_sha256="0" * 64, byte_start=self.reference.byte_start,
            byte_end=self.reference.byte_end, source_version=self.reference.source_version)
        bad = self.candidate("bad-evidence")
        object.__setattr__(bad.envelope, "source_refs", (forged,))
        with self.assertRaises(EvidenceResolutionError):
            self.store.record_candidate(bad)
        self.assertEqual(self.memory.replay_domain_events(
            event_type="m2_semantic_unit", scope="project-a"), [])

    def test_replay_page_size_is_validated(self):
        with self.assertRaises(ValueError):
            PersistentM2SemanticUnitStore(
                self.memory, self.resolver, scope="project-a", replay_page_size=0)
        with self.assertRaises(ValueError):
            PersistentM2SemanticUnitStore(
                self.memory, self.resolver, scope="project-a", replay_page_size=True)

    def test_replay_fails_closed_after_source_mutation(self):
        self.store.record_candidate(self.candidate("su-1"))
        with sqlite3.connect(self.evidence_db) as db:
            db.execute("UPDATE evidence_chunks SET text_utf8=? WHERE chunk_id=?",
                       (b"tampered", self.reference.chunk_id))
        self.memory.close()
        self.memory = ZPCMMemory(self.memory_db)
        with self.assertRaises(EvidenceResolutionError):
            PersistentM2SemanticUnitStore(self.memory, self.resolver, scope="project-a")


if __name__ == "__main__":
    unittest.main()
