import io
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import SQLiteEvidenceRefResolver
from prototype.m2_semantic_unit_reader import PersistentM2SemanticUnitReader
from prototype.m2_semantic_unit_store import PersistentM2SemanticUnitStore
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope, RoleBinding,
    SemanticUnitCandidate, TruthStatus, TypedAttribute, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.trlw_working_set import (
    PacketStatus, TRLWQuery, build_trlw_working_set_from_store,
)
from prototype.zpcm_memory import ZPCMMemory


class TRLWFromPagedSemanticReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        evidence_db, memory_db = root / "evidence.sqlite3", root / "zpcm.sqlite3"
        ingestor = SQLiteEvidenceIngestor(evidence_db)
        raw = "甲使用工具处理乙".encode("utf-8")
        self.assertTrue(ingestor.ingest("doc-1", "fixture.txt", io.BytesIO(raw), chunk_bytes=128).complete)
        chunk = ingestor.get_chunks("doc-1")[0]
        self.resolver = SQLiteEvidenceRefResolver(evidence_db)
        self.reference = self.resolver.make_reference("doc-1", chunk.chunk_id)
        self.memory = ZPCMMemory(memory_db)
        self.writer = PersistentM2SemanticUnitStore(self.memory, self.resolver, scope="project-a")

    def tearDown(self):
        self.memory.close()

    def candidate(self, rid):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1", record_id=rid,
                record_kind="SemanticUnitCandidate", producer="test",
                producer_version="1", recorded_at="2026-11-12T00:00:00Z",
                scope="project-a", source_refs=(self.reference,),
                derivation_refs=("obs-1",),
            ),
            kind=UnitKind.EVENT, surface_forms=(rid,),
            typed_attributes=(TypedAttribute("agent", "entity_ref", "entity:甲",
                                               source_refs=(self.reference,)),),
            role_bindings=(RoleBinding("agent", "entity:甲"),
                           RoleBinding("patient", "entity:乙")),
            grounding_status=GroundingStatus.GROUNDED,
            epistemic_status=EpistemicStatus.ASSERTED,
            truth_status=TruthStatus.UNKNOWN,
        )

    def reader(self):
        return PersistentM2SemanticUnitReader(
            self.memory, self.resolver, scope="project-a", page_size=1,
        )

    def test_trlw_consumes_paged_reader_and_preserves_newest_first_ties(self):
        for rid in ("su-1", "su-2", "su-3"):
            self.writer.record_candidate(self.candidate(rid))
        query = TRLWQuery(
            query_goal="activate current event candidates", scope="project-a",
            max_records=2, byte_budget=10000, required_types=(UnitKind.EVENT,),
            max_scan_events=10,
        )
        packet = build_trlw_working_set_from_store(self.reader(), query)
        self.assertEqual([entry.record.envelope.record_id for entry in packet.entries],
                         ["su-3", "su-2"])
        self.assertEqual(packet.status, PacketStatus.BUDGET_EXHAUSTED)
        self.assertTrue(packet.source_complete)

    def test_trlw_never_reports_not_found_when_source_scan_is_truncated(self):
        for rid in ("su-1", "su-2", "su-3"):
            self.writer.record_candidate(self.candidate(rid))
        query = TRLWQuery(
            query_goal="activate entity candidates", scope="project-a",
            max_records=2, byte_budget=10000, required_types=(UnitKind.ENTITY,),
            max_scan_events=1,
        )
        packet = build_trlw_working_set_from_store(self.reader(), query)
        self.assertEqual(packet.status, PacketStatus.SOURCE_INCOMPLETE)
        self.assertFalse(packet.source_complete)
        self.assertTrue(packet.budget_exhausted)
        self.assertEqual(packet.matched_records_seen, 0)


if __name__ == "__main__":
    unittest.main()
