import unittest

from prototype.e12a17_typed_relation_graph_discovery import (
    DirectedEdge, GraphDiscoveryConfig, GraphObservation, Node,
    discover_relation_motifs,
)


def make_graph_rows():
    rows = []
    for i in range(48):
        positive = i % 2 == 0
        nodes = (Node("x", "agent"), Node("y", "object"), Node("z", "state"))
        edges = ((DirectedEdge("x", "supports", "y"),
                  DirectedEdge("y", "transforms", "z")) if positive else
                 (DirectedEdge("x", "blocks", "y"),))
        rows.append(GraphObservation(f"obs-{i:03}", nodes if positive else nodes[:2],
                                     edges, "effect" if positive else "none"))
    return rows


class TypedRelationGraphDiscoveryTests(unittest.TestCase):
    def test_discovers_composed_directed_typed_path(self):
        result = discover_relation_motifs(make_graph_rows(),
            parent_refs=("primitive:root@1",),
            config=GraphDiscoveryConfig(max_path_length=2, min_train_support=3,
                min_validation_support=2, max_candidates=100,
                max_complexity_bits=30, validation_fraction=0.25))
        target = (("agent", "supports", "object"),
                  ("object", "transforms", "state"))
        self.assertIn(target, [motif.path for motif in result.motifs])
        found = next(m for m in result.motifs if m.path == target)
        self.assertGreater(found.mdl_gain_bits, 0)
        self.assertEqual(found.parent_refs, ("primitive:root@1",))

    def test_direction_and_relation_type_are_not_erased(self):
        rows = make_graph_rows()
        result = discover_relation_motifs(rows, config=GraphDiscoveryConfig(
            max_path_length=2, min_train_support=3, min_validation_support=2,
            max_candidates=100, max_complexity_bits=30, validation_fraction=0.25))
        paths = [m.path for m in result.motifs]
        self.assertIn((("agent", "supports", "object"),), paths)
        self.assertNotIn((("object", "supports", "agent"),), paths)

    def test_uninformative_graphs_are_not_admitted(self):
        rows = []
        for i in range(32):
            nodes = (Node("a", "A"), Node("b", "B"))
            rows.append(GraphObservation(f"u-{i:03}", nodes,
                (DirectedEdge("a", "r", "b"),), "yes" if i % 2 else "no"))
        result = discover_relation_motifs(rows, config=GraphDiscoveryConfig(
            max_path_length=1, min_train_support=3, min_validation_support=2,
            max_candidates=20, max_complexity_bits=20, validation_fraction=0.25))
        self.assertEqual(result.motifs, ())

    def test_candidate_budget_is_bounded_and_deterministic(self):
        config = GraphDiscoveryConfig(max_path_length=2, max_candidates=1,
            validation_fraction=0.25)
        first = discover_relation_motifs(make_graph_rows(), config=config)
        second = discover_relation_motifs(make_graph_rows(), config=config)
        self.assertEqual(first.generated_candidate_count, 1)
        self.assertTrue(first.truncated)
        self.assertEqual(first, second)

    def test_invalid_graph_references_are_rejected(self):
        with self.assertRaises(ValueError):
            GraphObservation("bad", (Node("a", "A"),),
                (DirectedEdge("a", "r", "missing"),), "x")
        with self.assertRaises(ValueError):
            GraphObservation("dup", (Node("a", "A"), Node("a", "B")), (), "x")

    def test_duplicate_observation_ids_are_rejected(self):
        row = make_graph_rows()[0]
        with self.assertRaises(ValueError):
            discover_relation_motifs([row, row, *make_graph_rows()[1:3]])

    def test_complexity_budget_blocks_motifs(self):
        result = discover_relation_motifs(make_graph_rows(), config=GraphDiscoveryConfig(
            max_path_length=2, min_train_support=3, min_validation_support=2,
            max_candidates=100, max_complexity_bits=1, validation_fraction=0.25))
        self.assertEqual(result.motifs, ())


if __name__ == "__main__":
    unittest.main()
