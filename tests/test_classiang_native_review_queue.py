from __future__ import annotations

import unittest

from prototype.classiang_native import EvidenceRef, Relation, Symbol, SymbolGraph
from prototype.classiang_native_review_queue import build_native_relation_review_queue


def _graph(*, include_unreviewed: bool = False) -> SymbolGraph:
    evidence = (
        EvidenceRef("e1", "src-a", "family-a", "ch1:1-4", "license-a", True),
        EvidenceRef("e2", "src-a", "family-a", "ch1:5-8", "license-a", True),
        EvidenceRef("e3", "src-b", "family-b", "ch2:1-4", "license-b", True),
    )
    if include_unreviewed:
        evidence += (
            EvidenceRef("e4", "src-c", "family-c", "ch3:1-4", "license-c", False),
        )
    symbols = (
        Symbol("s1", "domain-a", "thing", (), ("e1",)),
        Symbol("s2", "domain-a", "thing", (), ("e1",)),
        Symbol("s3", "domain-a", "thing", (), ("e2",)),
        Symbol("s4", "domain-b", "thing", (), ("e3",)),
        Symbol("s5", "domain-b", "thing", (), ("e3",)),
    )
    relations = (
        Relation("r1", "structural", (("left", "s1"), ("right", "s2")), ("e1",)),
        Relation("r2", "functional", (("agent", "s2"), ("patient", "s3")), ("e2",)),
        Relation("r3", "temporal", (("before", "s4"), ("after", "s5")), ("e3",)),
    )
    if include_unreviewed:
        symbols += (Symbol("s6", "domain-c", "thing", (), ("e4",)),)
        symbols += (Symbol("s7", "domain-c", "thing", (), ("e4",)),)
        relations += (
            Relation("r4", "symbolic", (("source", "s6"), ("target", "s7")), ("e4",)),
        )
    return SymbolGraph(evidence=evidence, symbols=symbols, relations=relations)


class NativeRelationReviewQueueTests(unittest.TestCase):
    def test_queue_generates_only_same_source_family_relation_pairs(self) -> None:
        queue = build_native_relation_review_queue(_graph())

        self.assertEqual(queue["candidate_count"], 1)
        self.assertEqual(queue["selected_count"], 1)
        item = queue["items"][0]
        self.assertEqual(item["relation_ids"], ["r1", "r2"])
        self.assertEqual(item["evidence_ids"], ["e1", "e2"])
        self.assertEqual(item["source_family"], "family-a")
        self.assertIsNone(item["annotation"]["decision"])
        self.assertEqual(item["gold_status"], "not_gold")
        self.assertTrue(queue["selection_policy"]["label_agnostic"])

    def test_queue_is_deterministic_and_respects_relation_caps(self) -> None:
        graph = _graph()
        first = build_native_relation_review_queue(graph, max_per_relation=1)
        second = build_native_relation_review_queue(graph, max_per_relation=1)

        self.assertEqual(first, second)
        self.assertEqual(first["queue_sha256"], second["queue_sha256"])
        self.assertEqual(first["selected_count"], 1)

    def test_queue_skips_unreviewed_evidence_without_promoting_it(self) -> None:
        queue = build_native_relation_review_queue(_graph(include_unreviewed=True))

        self.assertEqual(queue["candidate_count"], 1)
        self.assertEqual(queue["selected_count"], 1)
        self.assertIn(
            {"relation_id": "r4", "reason": "unreviewed_evidence"},
            queue["skipped_relations"],
        )

    def test_queue_rejects_invalid_limits_and_candidate_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_items must be a positive integer"):
            build_native_relation_review_queue(_graph(), max_items=0)


if __name__ == "__main__":
    unittest.main()
