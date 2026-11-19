import io
import json
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import EvidenceResolutionError, SQLiteEvidenceRefResolver
from prototype.m2_semantic_unit_store import (
    PersistentSemanticUnitCandidateStore,
    SemanticUnitStoreError,
)
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope,
    SemanticUnitCandidate, TruthStatus, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory, digest


class IndexedSemanticUnitReadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        evidence_db = root / "evidence.sqlite3"
        self.memory_db = root / "memory.sqlite3"
        ingestor = SQLiteEvidenceIngestor(evidence_db)
        result = ingestor.ingest(
            "doc-1", "fixture.txt", io.BytesIO("周易".encode("utf-8")),
            chunk_bytes=128,
        )
        self.assertTrue(result.complete)
        chunk = ingestor.get_chunks("doc-1")[0]
        self.resolver = SQLiteEvidenceRefResolver(evidence_db)
        self.reference = self.resolver.make_reference("doc-1", chunk.chunk_id)
        self.memory = ZPCMMemory(self.memory_db)
        self.addCleanup(self.memory.close)
        self.store = PersistentSemanticUnitCandidateStore(
            self.memory, self.resolver, scope="project-a",
        )

    def candidate(self, record_id="candidate-1"):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1", record_id=record_id,
                record_kind="SemanticUnitCandidate", producer="test-extractor",
                producer_version="1", recorded_at="2026-11-19T00:00:00Z",
                scope="project-a", source_refs=(self.reference,),
                derivation_refs=("m2:observation:obs-1",),
            ),
            kind=UnitKind.CONCEPT, surface_forms=("周易",),
            grounding_status=GroundingStatus.UNRESOLVED,
            epistemic_status=EpistemicStatus.UNKNOWN,
            truth_status=TruthStatus.UNKNOWN,
        )

    def test_indexed_candidate_and_receipt_round_trip(self):
        candidate = self.candidate()
        written = self.store.record_candidate(candidate)
        restored = self.store.get_candidate(candidate.envelope.record_id)
        receipt = self.store.get_receipt(candidate.envelope.record_id)
        self.assertEqual(restored, candidate)
        self.assertEqual(receipt.event_id, written.event_id)
        self.assertEqual(receipt.sequence, written.sequence)
        self.assertEqual(receipt.payload_digest, written.payload_digest)
        self.assertEqual(receipt.record_digest, written.record_digest)
        self.assertFalse(receipt.replayed)

    def test_missing_candidate_returns_none(self):
        self.assertIsNone(self.store.get_candidate("missing"))
        self.assertIsNone(self.store.get_receipt("missing"))

    def test_indexed_read_does_not_replay_candidate_stream(self):
        candidate = self.candidate()
        self.store.record_candidate(candidate)
        original = self.memory.iter_domain_events
        self.memory.iter_domain_events = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("indexed read must not replay the candidate stream")
        )
        try:
            self.assertEqual(self.store.get_candidate(candidate.envelope.record_id), candidate)
            self.assertIsNotNone(self.store.get_receipt(candidate.envelope.record_id))
        finally:
            self.memory.iter_domain_events = original

    def test_indexed_read_revalidates_source_evidence(self):
        candidate = self.candidate()
        self.store.record_candidate(candidate)
        import sqlite3
        evidence_db = self.resolver.database
        with sqlite3.connect(evidence_db) as db:
            db.execute(
                "UPDATE evidence_chunks SET text_utf8 = ? WHERE chunk_id = ?",
                (b"tampered", self.reference.chunk_id),
            )
        with self.assertRaises(EvidenceResolutionError):
            self.store.get_candidate(candidate.envelope.record_id)

    def test_indexed_read_rejects_event_identity_or_body_tampering(self):
        candidate = self.candidate()
        self.store.record_candidate(candidate)
        event = self.memory.get_domain_event(
            event_type="m2_semantic_unit_candidate",
            scope="project-a",
            event_id=f"m2:semantic-unit:{candidate.envelope.record_id}",
        )
        payload = dict(event["payload"])
        payload["body_digest"] = "0" * 64
        with self.memory.db:
            db = self.memory.db
            db.execute(
                "UPDATE memory_events SET payload_json = ?, payload_digest = ? WHERE event_id = ?",
                (
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    digest(payload),
                    event["event_id"],
                ),
            )
        with self.assertRaisesRegex(SemanticUnitStoreError, "digest mismatch"):
            self.store.get_candidate(candidate.envelope.record_id)


if __name__ == "__main__":
    unittest.main()
