import io
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import EvidenceResolutionError, SQLiteEvidenceRefResolver
from prototype.m2_semantic_unit_store import (
    PersistentSemanticUnitCandidateStore,
    SemanticUnitStoreError,
)
from prototype.observation_contract import (
    EpistemicStatus,
    GroundingStatus,
    RecordEnvelope,
    SemanticUnitCandidate,
    TruthStatus,
    UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


class PersistentSemanticUnitCandidateStoreTests(unittest.TestCase):
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
        self.store = PersistentSemanticUnitCandidateStore(
            self.memory, self.resolver, scope="project-a",
        )

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def make_candidate(self, *, record_id="candidate-1", surface="甲"):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1",
                record_id=record_id,
                record_kind="SemanticUnitCandidate",
                producer="test-grounder",
                producer_version="1.0",
                recorded_at="2026-11-12T00:00:00Z",
                scope="project-a",
                source_refs=(self.reference,),
            ),
            kind=UnitKind.ENTITY,
            surface_forms=(surface,),
            grounding_status=GroundingStatus.GROUNDED,
            epistemic_status=EpistemicStatus.ASSERTED,
            truth_status=TruthStatus.UNKNOWN,
        )

    def test_persists_and_streams_candidate_without_a_second_ledger(self):
        candidate = self.make_candidate()
        receipt = self.store.record_candidate(candidate)
        self.assertFalse(receipt.replayed)
        self.assertEqual(
            self.memory.db.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.memory.db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE '%semantic%'"
            ).fetchone()[0],
            0,
        )
        restored = list(self.store.iter_candidates(page_size=1))
        self.assertEqual(restored, [candidate])
        event = next(self.memory.iter_domain_events(
            event_type="m2_semantic_unit_candidate", scope="project-a", page_size=1,
        ))
        self.assertEqual(event["event_id"], "m2:semantic-unit:candidate-1")
        self.assertEqual(event["payload"]["body_digest"], receipt.record_digest)

    def test_identical_retry_is_idempotent_and_record_id_is_immutable(self):
        candidate = self.make_candidate()
        first = self.store.record_candidate(candidate)
        retry = self.store.record_candidate(candidate)
        self.assertTrue(retry.replayed)
        self.assertEqual(first.sequence, retry.sequence)
        with self.assertRaises(SemanticUnitStoreError):
            self.store.record_candidate(self.make_candidate(surface="甲（修订）"))

    def test_rejects_wrong_scope_and_invalid_source_evidence(self):
        wrong_scope = self.make_candidate()
        object.__setattr__(wrong_scope.envelope, "scope", "project-b")
        with self.assertRaises(SemanticUnitStoreError):
            self.store.record_candidate(wrong_scope)

        forged = type(self.reference)(
            document_id=self.reference.document_id,
            chunk_id=self.reference.chunk_id,
            content_sha256="0" * 64,
            byte_start=self.reference.byte_start,
            byte_end=self.reference.byte_end,
            source_version=self.reference.source_version,
        )
        forged_candidate = self.make_candidate()
        object.__setattr__(forged_candidate.envelope, "source_refs", (forged,))
        with self.assertRaises(EvidenceResolutionError):
            self.store.record_candidate(forged_candidate)
        self.assertEqual(
            list(self.store.iter_candidates()),
            [],
        )

    def test_paged_iteration_is_ordered_and_resumable(self):
        receipts = [
            self.store.record_candidate(self.make_candidate(record_id=f"candidate-{i}", surface=f"实体{i}"))
            for i in range(3)
        ]
        iterator = self.store.iter_candidates(page_size=1)
        first = next(iterator)
        self.assertEqual(first.envelope.record_id, "candidate-0")
        tail = list(self.store.iter_candidates(after_sequence=receipts[0].sequence, page_size=1))
        self.assertEqual(
            [item.envelope.record_id for item in tail],
            ["candidate-1", "candidate-2"],
        )

    def test_replay_fails_closed_when_source_evidence_changes(self):
        self.store.record_candidate(self.make_candidate())
        import sqlite3
        with sqlite3.connect(self.evidence_db) as db:
            db.execute(
                "UPDATE evidence_chunks SET text_utf8 = ? WHERE chunk_id = ?",
                (b"tampered", self.reference.chunk_id),
            )
        with self.assertRaises(EvidenceResolutionError):
            list(self.store.iter_candidates(page_size=1))


if __name__ == "__main__":
    unittest.main()
