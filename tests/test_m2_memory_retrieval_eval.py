import unittest

from prototype.m2_memory_packet import MemoryQuery
from prototype.m2_memory_retrieval_eval import (
    LexicalRetrievalCase,
    RetrievalEvaluationError,
    evaluate_lexical_retrieval,
)
from prototype.observation_contract import (
    EvidenceRef, GroundingStatus, RecordEnvelope, SemanticUnitCandidate,
    TruthStatus, UnitKind,
)


class Reader:
    scope = "scope-a"

    def __init__(self, rows):
        self.rows = rows

    def iter_candidates(self, *, page_size):
        assert page_size == 128
        yield from self.rows


def candidate(record_id, surface):
    ref = EvidenceRef("doc", "chunk-" + record_id, "a" * 64, 0, 3, "manifest-sha256:" + "b" * 64)
    return SemanticUnitCandidate(
        envelope=RecordEnvelope(
            schema_version="m2-record-v1", record_id=record_id,
            record_kind="SemanticUnitCandidate", producer="eval-fixture",
            producer_version="1", recorded_at="2026-11-19T00:00:00Z",
            scope="scope-a", source_refs=(ref,),
        ),
        kind=UnitKind.CONCEPT, surface_forms=(surface,),
        grounding_status=GroundingStatus.GROUNDED,
        truth_status=TruthStatus.UNKNOWN,
    )


def query():
    return MemoryQuery(
        query_goal="因果 关系", scope="scope-a",
        required_types=(UnitKind.CONCEPT,), max_records=5,
        byte_budget=8192, ranking_policy="lexical-overlap-v1",
        max_scan_events=32,
    )


class LexicalRetrievalEvaluationTests(unittest.TestCase):
    def test_reports_recall_precision_mrr_and_explicit_no_memory_baseline(self):
        case = LexicalRetrievalCase(
            query(), Reader([
                candidate("irrelevant", "天气"),
                candidate("relevant-a", "因果 关系"),
                candidate("relevant-b", "因果"),
            ]),
            ("relevant-a", "relevant-b"),
        )
        result = evaluate_lexical_retrieval([case], k=2)
        self.assertEqual(result.cases, 1)
        self.assertEqual(result.recall_at_k, 1.0)
        self.assertEqual(result.precision_at_k, 1.0)
        self.assertEqual(result.mean_reciprocal_rank, 1.0)
        self.assertEqual(result.hit_rate, 1.0)
        self.assertEqual(result.no_memory_recall_at_k, 0.0)
        self.assertEqual(result.no_memory_mrr, 0.0)
        self.assertEqual(result.metric_schema, "m2-lexical-retrieval-eval-v1")

    def test_rejects_empty_or_ambiguous_relevance_labels(self):
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_lexical_retrieval([])
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_lexical_retrieval([
                LexicalRetrievalCase(query(), Reader([]), ())
            ])
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_lexical_retrieval([
                LexicalRetrievalCase(query(), Reader([]), ("same", "same"))
            ])

    def test_rejects_invalid_k(self):
        case = LexicalRetrievalCase(
            query(), Reader([candidate("relevant", "因果 关系")]), ("relevant",)
        )
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_lexical_retrieval([case], k=0)


if __name__ == "__main__":
    unittest.main()
