import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.evidence_ref_resolver import EvidenceResolutionError, SQLiteEvidenceRefResolver
from prototype.m2_memory_packet import (
    MemoryQuery, PacketCompleteness, build_memory_packet_from_store,
)
from prototype.m2_semantic_unit_reader import PersistentM2SemanticUnitReader
from prototype.m2_semantic_unit_store import PersistentM2SemanticUnitStore
from prototype.observation_contract import (
    EpistemicStatus, GroundingStatus, RecordEnvelope, RoleBinding,
    SemanticUnitCandidate, TruthStatus, TypedAttribute, UnitKind,
)
from prototype.streaming_evidence_ingest import SQLiteEvidenceIngestor
from prototype.zpcm_memory import ZPCMMemory


class PersistentM2SemanticUnitReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.evidence_db, self.memory_db = root / "evidence.sqlite3", root / "zpcm.sqlite3"
        ingestor = SQLiteEvidenceIngestor(self.evidence_db)
        raw = "甲使用工具处理乙".encode("utf-8")
        self.assertTrue(ingestor.ingest("doc-1", "fixture.txt", io.BytesIO(raw), chunk_bytes=128).complete)
        chunk = ingestor.get_chunks("doc-1")[0]
        self.resolver = SQLiteEvidenceRefResolver(self.evidence_db)
        self.reference = self.resolver.make_reference("doc-1", chunk.chunk_id)
        self.memory = ZPCMMemory(self.memory_db)
        self.writer = PersistentM2SemanticUnitStore(self.memory, self.resolver, scope="project-a")

    def tearDown(self):
        self.memory.close()
        self.temp.cleanup()

    def candidate(self, rid, *, predecessor=None, surface="使用工具"):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1", record_id=rid,
                record_kind="SemanticUnitCandidate", producer="test",
                producer_version="1", recorded_at="2026-11-12T00:00:00Z",
                scope="project-a", source_refs=(self.reference,),
                derivation_refs=("obs-1",) + ((predecessor,) if predecessor else ()),
            ),
            kind=UnitKind.EVENT, surface_forms=(surface,),
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

    def test_reader_yields_latest_version_and_omits_retracted_root(self):
        first = self.candidate("su-1")
        other = self.candidate("su-2", surface="另一个事件")
        revised = self.candidate("su-1-r1", predecessor="su-1", surface="修订后的事件")
        self.writer.record_candidate(first)
        self.writer.record_candidate(other)
        self.writer.revise_candidate("su-1", revised)
        reader = self.reader()
        self.assertEqual(list(reader.iter_current_candidates()), [revised, other])
        self.writer.retract_candidate("su-2", reason="contradicted")
        self.assertEqual(list(reader.iter_current_candidates()), [revised])

    def test_reader_uses_reverse_paged_stream_not_full_restore(self):
        self.writer.record_candidate(self.candidate("su-1"))
        original = self.memory.replay_domain_events
        self.memory.replay_domain_events = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("reader must not materialize the event stream")
        )
        try:
            self.assertEqual(len(list(self.reader().iter_current_candidates())), 1)
        finally:
            self.memory.replay_domain_events = original

    def test_memory_packet_reads_directly_from_bounded_store_stream(self):
        for rid in ("su-1", "su-2", "su-3"):
            self.writer.record_candidate(self.candidate(rid))
        query = MemoryQuery(
            query_goal="retrieve recent event relations", scope="project-a",
            required_types=(UnitKind.EVENT,), max_records=2, byte_budget=10000,
            ranking_policy="latest-lifecycle-event-desc-v1", max_scan_events=10,
        )
        packet = build_memory_packet_from_store(self.reader(), query)
        self.assertEqual([x.record_id for x in packet.items], ["su-3", "su-2"])
        self.assertEqual(packet.completeness, PacketCompleteness.BUDGET_EXHAUSTED)
        self.assertLessEqual(packet.serialized_bytes, packet.byte_budget)

    def test_scan_budget_exhaustion_is_not_reported_as_not_found(self):
        for rid in ("su-1", "su-2", "su-3"):
            self.writer.record_candidate(self.candidate(rid))
        query = MemoryQuery(
            query_goal="retrieve recent event relations", scope="project-a",
            required_types=(UnitKind.ENTITY,), max_records=2, byte_budget=10000,
            ranking_policy="latest-lifecycle-event-desc-v1", max_scan_events=1,
        )
        packet = build_memory_packet_from_store(self.reader(), query)
        self.assertEqual(packet.items, ())
        self.assertEqual(packet.completeness, PacketCompleteness.BUDGET_EXHAUSTED)
        self.assertEqual(packet.records_scanned, 1)

    def test_reader_revalidates_source_evidence_on_demand(self):
        self.writer.record_candidate(self.candidate("su-1"))
        with sqlite3.connect(self.evidence_db) as db:
            db.execute("UPDATE evidence_chunks SET text_utf8=? WHERE chunk_id=?",
                       (b"tampered", self.reference.chunk_id))
        with self.assertRaises(EvidenceResolutionError):
            list(self.reader().iter_current_candidates())


if __name__ == "__main__":
    unittest.main()
