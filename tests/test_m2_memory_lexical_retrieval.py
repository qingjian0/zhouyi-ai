import unittest

from prototype.m2_memory_packet import MemoryQuery, PacketCompleteness
from prototype.m2_memory_lexical_retrieval import (
    LexicalRetrievalError,
    _terms,
    retrieve_lexical_memory,
)
from prototype.observation_contract import (
    EvidenceRef,
    GroundingStatus,
    RecordEnvelope,
    SemanticUnitCandidate,
    TruthStatus,
    UnitKind,
)


class Reader:
    scope = "scope-a"

    def __init__(self, rows):
        self.rows = rows
        self.page_sizes = []
        self.yielded = 0

    def iter_candidates(self, *, page_size):
        self.page_sizes.append(page_size)
        for row in self.rows:
            self.yielded += 1
            yield row


def candidate(record_id, surface, *, scope="scope-a", kind=UnitKind.CONCEPT):
    ref = EvidenceRef("doc", "chunk-" + record_id, "a" * 64, 0, 3, "manifest-sha256:" + "b" * 64)
    return SemanticUnitCandidate(
        envelope=RecordEnvelope(
            schema_version="m2-record-v1", record_id=record_id,
            record_kind="SemanticUnitCandidate", producer="test",
            producer_version="1", recorded_at="2026-11-19T00:00:00Z",
            scope=scope, source_refs=(ref,),
        ),
        kind=kind, surface_forms=(surface,),
        grounding_status=GroundingStatus.GROUNDED,
        truth_status=TruthStatus.UNKNOWN,
    )


def query(**overrides):
    values = dict(
        query_goal="关系 推理", scope="scope-a",
        required_types=(UnitKind.CONCEPT,), max_records=3,
        byte_budget=8192, ranking_policy="lexical-overlap-v1",
        max_scan_events=20,
    )
    values.update(overrides)
    return MemoryQuery(**values)


class LexicalRetrievalTests(unittest.TestCase):
    def test_ranks_by_query_term_coverage_not_append_order(self):
        rows = [
            candidate("z-low", "关系"),
            candidate("b-high", "关系 推理"),
            candidate("a-high", "关系 推理"),
            candidate("no-hit", "天气"),
        ]
        reader = Reader(rows)
        report = retrieve_lexical_memory(reader, query())
        self.assertEqual(
            [item.record_id for item in report.packet.items],
            ["a-high", "b-high", "z-low"],
        )
        self.assertEqual(report.packet.ranking_policy, "lexical-overlap-v1")
        self.assertEqual(report.candidates_scanned, 4)
        self.assertEqual(report.candidates_matched, 4)
        self.assertEqual(reader.page_sizes, [128])

    def test_cjk_bigrams_do_not_cross_whitespace_or_punctuation(self):
        self.assertIn("关系", _terms("关系 推理"))
        self.assertNotIn("系推", _terms("关系 推理"))
        self.assertNotIn("系，推", _terms("关系，推理"))
        self.assertIn("推理", _terms("关系，推理"))

    def test_filters_scope_and_type_before_top_k(self):
        rows = [
            candidate("wrong-scope", "关系 推理", scope="scope-b"),
            candidate("wrong-type", "关系 推理", kind=UnitKind.EVENT),
            candidate("right", "关系"),
        ]
        report = retrieve_lexical_memory(Reader(rows), query(max_records=1))
        self.assertEqual([x.record_id for x in report.packet.items], ["right"])
        self.assertEqual(report.candidates_matched, 1)

    def test_scan_budget_does_not_pull_an_extra_candidate(self):
        rows = [candidate(f"r{i}", "关系 推理") for i in range(5)]
        reader = Reader(rows)
        report = retrieve_lexical_memory(
            reader, query(max_scan_events=2, max_records=2),
        )
        self.assertEqual(report.candidates_scanned, 2)
        self.assertEqual(reader.yielded, 2)
        self.assertTrue(report.scan_budget_exhausted)
        self.assertEqual(report.packet.completeness, PacketCompleteness.BUDGET_EXHAUSTED)

    def test_query_without_searchable_terms_fails_closed(self):
        with self.assertRaises(LexicalRetrievalError):
            retrieve_lexical_memory(Reader([]), query(query_goal="！？..."))

    def test_scope_mismatch_fails_closed(self):
        reader = Reader([])
        reader.scope = "scope-b"
        with self.assertRaises(LexicalRetrievalError):
            retrieve_lexical_memory(reader, query())


if __name__ == "__main__":
    unittest.main()
