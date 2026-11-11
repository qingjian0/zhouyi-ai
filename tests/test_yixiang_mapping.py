import unittest
from prototype.yixiang_analogy import MappingKind, Node, Relation, RelationalGraph, BridgeStatus
from prototype.yixiang_mapping import enumerate_candidate_bridges

def make_graphs():
    source = RelationalGraph("source",
        tuple(sorted((Node("a", "actor"), Node("b", "system")))),
        (Relation("acts_on", ("a", "b")),))
    target = RelationalGraph("target",
        tuple(sorted((Node("x", "controller"), Node("y", "system"), Node("z", "controller")))),
        tuple(sorted((Relation("controls", ("x", "y")), Relation("controls", ("z", "y"))))))
    return source, target

class XSL2CandidateMappingTests(unittest.TestCase):
    def setUp(self):
        self.source, self.target = make_graphs()
        self.kwargs = dict(
            mapping_kind=MappingKind.RELATION,
            node_type_mapping=(("actor", "controller"), ("system", "system")),
            relation_mapping=(("acts_on", "controls"),))

    def test_enumerates_competing_preserved_candidates(self):
        result = enumerate_candidate_bridges(self.source, self.target, **self.kwargs)
        self.assertTrue(result.search_complete)
        self.assertEqual(result.candidate_count, 2)
        self.assertEqual(len(result.candidates), 2)
        self.assertFalse(result.results_truncated)
        self.assertTrue(all(c.validation.status == BridgeStatus.STRUCTURALLY_PRESERVED for c in result.candidates))
        self.assertEqual({c.bridge.node_mapping for c in result.candidates},
            {(("a", "x"), ("b", "y")), (("a", "z"), ("b", "y"))})

    def test_candidate_order_is_deterministic(self):
        first = enumerate_candidate_bridges(self.source, self.target, **self.kwargs)
        second = enumerate_candidate_bridges(self.source, self.target, **self.kwargs)
        self.assertEqual([c.bridge.bridge_id for c in first.candidates],
                         [c.bridge.bridge_id for c in second.candidates])

    def test_budget_exhaustion_is_explicit(self):
        result = enumerate_candidate_bridges(self.source, self.target, max_search_states=2, **self.kwargs)
        self.assertFalse(result.search_complete)
        self.assertLessEqual(result.states_visited, 2)

    def test_result_cap_is_distinct_from_search_truncation(self):
        result = enumerate_candidate_bridges(self.source, self.target, max_candidates=1, **self.kwargs)
        self.assertTrue(result.search_complete)
        self.assertEqual(result.candidate_count, 2)
        self.assertEqual(len(result.candidates), 1)
        self.assertTrue(result.results_truncated)

    def test_rejects_boolean_budget(self):
        with self.assertRaisesRegex(ValueError, "max_search_states"):
            enumerate_candidate_bridges(self.source, self.target, max_search_states=True, **self.kwargs)

    def test_distinct_source_types_may_share_target_supertype(self):
        source = RelationalGraph("source-shared-type",
            tuple(sorted((Node("a", "actor"), Node("b", "system")))),
            (Relation("acts_on", ("a", "b")),))
        target = RelationalGraph("target-shared-type",
            tuple(sorted((Node("x", "agent"), Node("y", "agent")))),
            (Relation("controls", ("x", "y")),))
        result = enumerate_candidate_bridges(source, target,
            mapping_kind=MappingKind.RELATION,
            node_type_mapping=(("actor", "agent"), ("system", "agent")),
            relation_mapping=(("acts_on", "controls"),))
        self.assertTrue(result.search_complete)
        self.assertEqual(len(result.candidates), 2)
        statuses = {candidate.validation.status for candidate in result.candidates}
        self.assertEqual(statuses, {BridgeStatus.STRUCTURALLY_PRESERVED, BridgeStatus.COUNTEREXAMPLE})


if __name__ == "__main__":
    unittest.main()
