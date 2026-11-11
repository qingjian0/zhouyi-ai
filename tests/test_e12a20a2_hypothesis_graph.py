import unittest

from prototype.e12a20a2_hypothesis_graph import (
    EvidenceNode, HypothesisNode, build_hypothesis_graph,
)


class HypothesisGraphTests(unittest.TestCase):
    def test_evidence_support_is_explicit_and_scope_bound(self):
        evidence = EvidenceNode("e1", "receipt://e1", "q1", "scope-a",
                                "MEASUREMENT_RECEIPT", "digest-1")
        hypothesis = HypothesisNode("h1", "q1", "scope-a", (("x", "1"),),
                                    evidence_ids=("e1",))
        graph = build_hypothesis_graph((hypothesis,), (evidence,))
        self.assertEqual([(e.kind, e.source_id, e.target_id) for e in graph.edges],
                         [("SUPPORTS", "e1", "h1")])

    def test_contradiction_and_alternative_are_distinct_relations(self):
        left = HypothesisNode("h-a", "q1", "s1", (("x", "0"),),
                              competition_set_id="set-1")
        right = HypothesisNode("h-b", "q1", "s1", (("x", "1"),),
                               competition_set_id="set-1")
        graph = build_hypothesis_graph((right, left), ())
        self.assertEqual(
            {(edge.kind, edge.source_id, edge.target_id) for edge in graph.edges},
            {("CONTRADICTS", "h-a", "h-b"), ("ALTERNATIVE", "h-a", "h-b")},
        )

    def test_refinement_points_from_specific_to_general(self):
        general = HypothesisNode("h-general", "q", "s", (("x", "0"),))
        specific = HypothesisNode("h-specific", "q", "s",
                                  (("x", "0"), ("y", "1")))
        graph = build_hypothesis_graph((general, specific), ())
        self.assertIn(("REFINES", "h-specific", "h-general"),
                      {(e.kind, e.source_id, e.target_id) for e in graph.edges})

    def test_derived_from_keeps_lineage(self):
        parent = HypothesisNode("parent", "q", "s", (("x", "0"),))
        child = HypothesisNode("child", "q", "s", (("x", "0"), ("y", "1")),
                               parent_ids=("parent",))
        graph = build_hypothesis_graph((child, parent), ())
        self.assertIn(("DERIVED_FROM", "child", "parent"),
                      {(e.kind, e.source_id, e.target_id) for e in graph.edges})

    def test_cross_scope_evidence_and_parent_transfer_rejected(self):
        evidence = EvidenceNode("e1", "receipt://e1", "q", "scope-a", "OBSERVATION")
        hypothesis = HypothesisNode("h1", "q", "scope-b", (("x", "0"),),
                                    evidence_ids=("e1",))
        with self.assertRaisesRegex(ValueError, "scope/query mismatch"):
            build_hypothesis_graph((hypothesis,), (evidence,))
        parent = HypothesisNode("parent", "q", "scope-a", (("x", "0"),))
        child = HypothesisNode("child", "q", "scope-b", (("x", "0"), ("y", "1")),
                               parent_ids=("parent",))
        with self.assertRaisesRegex(ValueError, "parent scope/query mismatch"):
            build_hypothesis_graph((parent, child), ())

    def test_unknown_refs_and_lineage_cycles_rejected(self):
        missing = HypothesisNode("h", "q", "s", (("x", "0"),), evidence_ids=("missing",))
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            build_hypothesis_graph((missing,), ())
        a = HypothesisNode("a", "q", "s", (("x", "0"),), parent_ids=("b",))
        b = HypothesisNode("b", "q", "s", (("y", "0"),), parent_ids=("a",))
        with self.assertRaisesRegex(ValueError, "acyclic"):
            build_hypothesis_graph((a, b), ())

    def test_duplicate_ids_and_malformed_assignments_rejected(self):
        item = HypothesisNode("h", "q", "s", (("x", "0"),))
        with self.assertRaisesRegex(ValueError, "duplicate hypothesis"):
            build_hypothesis_graph((item, item), ())
        with self.assertRaisesRegex(ValueError, "duplicate variable"):
            HypothesisNode("bad", "q", "s", (("x", "0"), ("x", "1")))

    def test_input_order_does_not_change_graph(self):
        e1 = EvidenceNode("e1", "r1", "q", "s", "OBSERVATION")
        e2 = EvidenceNode("e2", "r2", "q", "s", "OBSERVATION")
        h1 = HypothesisNode("h1", "q", "s", (("x", "0"),), evidence_ids=("e1",))
        h2 = HypothesisNode("h2", "q", "s", (("x", "1"),), evidence_ids=("e2",))
        a = build_hypothesis_graph((h1, h2), (e1, e2))
        b = build_hypothesis_graph((h2, h1), (e2, e1))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
