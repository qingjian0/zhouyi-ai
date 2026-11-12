import hashlib
import unittest

from prototype.observation_contract import (
    EpistemicStatus,
    EvidenceRef,
    GroundingStatus,
    RecordEnvelope,
    SemanticUnitCandidate,
    Score,
    TruthStatus,
    UnitKind,
    canonical_json,
)
from prototype.trlw_working_set import (
    PacketStatus,
    TRLWError,
    TRLWQuery,
    build_trlw_working_set,
)


def candidate(record_id, *, scope="scope:a", kind=UnitKind.ENTITY,
              grounding=GroundingStatus.GROUNDED, valid_start=None, valid_end=None):
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
    source = EvidenceRef(
        document_id="doc:" + record_id,
        chunk_id="chunk:" + record_id,
        content_sha256=digest,
        byte_start=0,
        byte_end=1,
        source_version="m1:v1",
    )
    envelope = RecordEnvelope(
        schema_version="m2-record-v1",
        record_id=record_id,
        record_kind="SemanticUnitCandidate",
        producer="test",
        producer_version="1",
        recorded_at="2026-11-12T00:00:00Z",
        scope=scope,
        source_refs=(source,),
        valid_time_start=valid_start,
        valid_time_end=valid_end,
    )
    return SemanticUnitCandidate(
        envelope=envelope,
        kind=kind,
        surface_forms=(record_id,),
        grounding_status=grounding,
        epistemic_status=EpistemicStatus.ASSERTED,
        truth_status=TruthStatus.UNKNOWN,
    )


class TRLWWorkingSetTests(unittest.TestCase):
    def query(self, **changes):
        values = dict(
            query_goal="test retrieval",
            scope="scope:a",
            max_records=10,
            byte_budget=100_000,
        )
        values.update(changes)
        return TRLWQuery(**values)

    def test_returns_ranked_bounded_packet(self):
        rows = [candidate("low"), candidate("high"), candidate("middle")]
        scores = {"low": 0.1, "high": 0.9, "middle": 0.5}
        packet = build_trlw_working_set(
            rows, self.query(max_records=2),
            ranker=lambda record, query: Score(scores[record.envelope.record_id], "trlw-ranking"),
            source_complete=True,
        )
        self.assertEqual(
            [entry.record.envelope.record_id for entry in packet.entries],
            ["high", "middle"],
        )
        self.assertEqual(packet.status, PacketStatus.BUDGET_EXHAUSTED)
        self.assertTrue(packet.budget_exhausted)
        self.assertLessEqual(packet.serialized_bytes, packet.byte_budget)
        self.assertEqual(packet.returned_records, 2)

    def test_filters_scope_type_and_grounding(self):
        rows = [
            candidate("entity", kind=UnitKind.ENTITY),
            candidate("event", kind=UnitKind.EVENT),
            candidate("other-scope", scope="scope:b"),
            candidate("unresolved", grounding=GroundingStatus.UNRESOLVED),
        ]
        packet = build_trlw_working_set(
            rows,
            self.query(required_types=(UnitKind.EVENT,)),
            source_complete=True,
        )
        self.assertEqual(
            [entry.record.envelope.record_id for entry in packet.entries],
            ["event"],
        )
        self.assertEqual(packet.matched_records_seen, 1)

    def test_byte_budget_never_exceeds_declared_serialized_budget(self):
        row = candidate("large-record")
        size = len(canonical_json(row).encode("utf-8"))
        packet = build_trlw_working_set(
            [row], self.query(byte_budget=size - 1), source_complete=True,
        )
        self.assertEqual(packet.status, PacketStatus.BUDGET_EXHAUSTED)
        self.assertTrue(packet.budget_exhausted)
        self.assertEqual(packet.entries, ())
        self.assertEqual(packet.serialized_bytes, 0)

    def test_incomplete_source_is_distinct_from_budget_exhaustion(self):
        packet = build_trlw_working_set(
            [candidate("one")], self.query(), source_complete=False,
        )
        self.assertEqual(packet.status, PacketStatus.SOURCE_INCOMPLETE)
        self.assertFalse(packet.complete)
        self.assertFalse(packet.budget_exhausted)
        self.assertFalse(packet.source_complete)

    def test_incomplete_source_and_budget_exhaustion_are_both_reported(self):
        row = candidate("large-record")
        size = len(canonical_json(row).encode("utf-8"))
        packet = build_trlw_working_set(
            [row], self.query(byte_budget=size - 1), source_complete=False,
        )
        self.assertEqual(packet.status, PacketStatus.SOURCE_INCOMPLETE)
        self.assertTrue(packet.budget_exhausted)

    def test_empty_complete_source_reports_not_found(self):
        packet = build_trlw_working_set([], self.query(), source_complete=True)
        self.assertEqual(packet.status, PacketStatus.NOT_FOUND)

    def test_valid_time_uses_half_open_interval_overlap(self):
        row = candidate(
            "timed", valid_start="2026-11-12T10:00:00Z",
            valid_end="2026-11-12T11:00:00Z",
        )
        packet = build_trlw_working_set(
            [row],
            self.query(
                valid_time_start="2026-11-12T10:30:00Z",
                valid_time_end="2026-11-12T11:30:00Z",
            ),
            source_complete=True,
        )
        self.assertEqual(packet.returned_records, 1)

    def test_non_overlapping_valid_time_is_filtered(self):
        row = candidate(
            "timed", valid_start="2026-11-12T10:00:00Z",
            valid_end="2026-11-12T11:00:00Z",
        )
        packet = build_trlw_working_set(
            [row],
            self.query(
                valid_time_start="2026-11-12T11:00:00Z",
                valid_time_end="2026-11-12T12:00:00Z",
            ),
            source_complete=True,
        )
        self.assertEqual(packet.returned_records, 0)
        self.assertEqual(packet.status, PacketStatus.NOT_FOUND)

    def test_ranker_score_semantics_are_enforced(self):
        with self.assertRaises(TRLWError):
            build_trlw_working_set(
                [candidate("one")], self.query(),
                ranker=lambda record, query: Score(0.5, "extractor-confidence"),
                source_complete=True,
            )

    def test_invalid_query_budgets_and_time_are_rejected(self):
        with self.assertRaises(TRLWError):
            self.query(byte_budget=0)
        with self.assertRaises(TRLWError):
            self.query(max_records=True)
        with self.assertRaises(TRLWError):
            self.query(valid_time_start="2026-11-12T10:00:00",
                       valid_time_end="2026-11-12T11:00:00Z")


if __name__ == "__main__":
    unittest.main()
