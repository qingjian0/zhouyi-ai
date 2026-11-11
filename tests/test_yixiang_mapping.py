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
        self.assertEqual(len(result.candidates), 2)
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

    def test_rejects_boolean_budget(self):
        with self.assertRaisesRegex(ValueError, "max_search_states"):
            enumerate_candidate_bridges(self.source, self.target, max_search_states=True, **self.kwargs)

    def test_rejects_non_injective_type_map(self):
        with self.assertRaisesRegex(ValueError, "target values must be unique"):
            enumerate_candidate_bridges(self.source, self.target,
                node_type_mapping=(("actor", "controller"), ("system", "controller")),
                relation_mapping=self.kwargs["relation_mapping"],
                mapping_kind=MappingKind.RELATION)

if __name__ == "__main__":
    unittest.main()
