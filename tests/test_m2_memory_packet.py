import unittest

from prototype.m2_memory_packet import (
    MemoryPacketError, MemoryQuery, PacketCompleteness, build_memory_packet,
)
from prototype.observation_contract import (
    EvidenceRef, GroundingStatus, RecordEnvelope, RoleBinding,
    SemanticUnitCandidate, TruthStatus, UnitKind, canonical_json,
)


class MemoryPacketTests(unittest.TestCase):
    def setUp(self):
        self.ref = EvidenceRef("doc", "chunk", "a" * 64, 0, 12, "manifest-sha256:" + "b" * 64)

    def candidate(self, rid, *, scope="s1", kind=UnitKind.EVENT, start=None, end=None):
        return SemanticUnitCandidate(
            envelope=RecordEnvelope(
                schema_version="m2-record-v1", record_id=rid,
                record_kind="SemanticUnitCandidate", producer="test",
                producer_version="1", recorded_at="2026-11-12T00:00:00Z",
                scope=scope, source_refs=(self.ref,),
                valid_time_start=start, valid_time_end=end,
            ),
            kind=kind, surface_forms=("ignored source surface",),
            role_bindings=(RoleBinding("agent", "entity:a"), RoleBinding("patient", "entity:b")),
            grounding_status=GroundingStatus.GROUNDED,
            truth_status=TruthStatus.UNKNOWN,
        )

    def query(self, **kwargs):
        values = dict(query_goal="answer relation query", scope="s1",
                      required_types=(UnitKind.EVENT,), max_records=10,
                      byte_budget=10000, ranking_policy="caller-ranked-v1")
        values.update(kwargs)
        return MemoryQuery(**values)

    def test_packet_is_bounded_and_preserves_provenance_and_role_order(self):
        packet = build_memory_packet(
            [self.candidate("e1"), self.candidate("e2")], self.query(max_records=1))
        self.assertEqual(len(packet.items), 1)
        self.assertEqual(packet.items[0].record_id, "e1")
        self.assertEqual(packet.items[0].role_bindings,
                         (("agent", "entity:a"), ("patient", "entity:b")))
        self.assertEqual(packet.items[0].source_refs, (self.ref,))
        self.assertLessEqual(packet.serialized_bytes, packet.byte_budget)
        self.assertEqual(packet.completeness, PacketCompleteness.BUDGET_EXHAUSTED)

    def test_byte_budget_is_hard_limit_and_does_not_emit_partial_item(self):
        candidate = self.candidate("large-record-id")
        empty = build_memory_packet([], self.query())
        budget = empty.serialized_bytes + 20
        packet = build_memory_packet([candidate], self.query(byte_budget=budget))
        self.assertEqual(packet.items, ())
        self.assertEqual(packet.completeness, PacketCompleteness.BUDGET_EXHAUSTED)
        self.assertLessEqual(packet.serialized_bytes, budget)

    def test_scope_type_and_temporal_filters(self):
        rows = [
            self.candidate("wrong-scope", scope="s2"),
            self.candidate("wrong-type", kind=UnitKind.ENTITY),
            self.candidate("no-time"),
            self.candidate("in-window", start="2026-01-01", end="2026-12-31"),
        ]
        packet = build_memory_packet(rows, self.query(
            valid_time_start="2026-06-01", valid_time_end="2026-06-30"))
        self.assertEqual([x.record_id for x in packet.items], ["in-window"])

    def test_empty_result_is_not_found(self):
        packet = build_memory_packet([], self.query())
        self.assertEqual(packet.items, ())
        self.assertEqual(packet.completeness, PacketCompleteness.NOT_FOUND)

    def test_invalid_query_limits_are_rejected(self):
        with self.assertRaises(MemoryPacketError):
            self.query(max_records=0)
        with self.assertRaises(MemoryPacketError):
            self.query(byte_budget=0)
        with self.assertRaises(MemoryPacketError):
            self.query(required_types=())

    def test_temporal_window_requires_valid_ordered_iso_values(self):
        with self.assertRaises(MemoryPacketError):
            self.query(valid_time_start="2026-07-01", valid_time_end="2026-06-01")
        with self.assertRaises(MemoryPacketError):
            self.query(valid_time_start="not-a-date", valid_time_end="2026-06-01")
        with self.assertRaises(MemoryPacketError):
            self.query(valid_time_start="2026-06-01T00:00:00Z",
                       valid_time_end="2026-06-02")

    def test_malformed_candidate_temporal_interval_fails_closed(self):
        candidate = self.candidate("bad-time", start="2026-12-31", end="2026-01-01")
        with self.assertRaises(MemoryPacketError):
            build_memory_packet([candidate], self.query(
                valid_time_start="2026-01-01", valid_time_end="2026-12-31"))


if __name__ == "__main__":
    unittest.main()
