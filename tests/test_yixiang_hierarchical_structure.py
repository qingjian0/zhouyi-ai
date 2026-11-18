import unittest

from prototype.yixiang_hierarchical_structure import (
    HierarchicalStructure, RelationKind, StructureEdge, StructureNode,
)


def node(name, level="local"):
    return StructureNode(name, level, name)


def edge(eid, source, target, kind=RelationKind.PART_OF):
    return StructureEdge(eid, source, target, kind, (f"source:{eid}",))


class HierarchicalStructureTests(unittest.TestCase):
    def test_distinguishes_relation_types(self):
        graph = HierarchicalStructure(
            (node("wheel"), node("vehicle", "whole"), node("road")),
            (
                edge("e1", "wheel", "vehicle", RelationKind.PART_OF),
                edge("e2", "wheel", "vehicle", RelationKind.FUNCTIONAL_PARTICIPATION),
                edge("e3", "vehicle", "road", RelationKind.SPATIAL_ADJACENCY),
            ),
        )
        graph.validate()
        self.assertEqual(len(graph.edges_of(RelationKind.PART_OF)), 1)
        self.assertEqual(len(graph.edges_of(RelationKind.FUNCTIONAL_PARTICIPATION)), 1)
        self.assertEqual(graph.neighbors("vehicle", RelationKind.SPATIAL_ADJACENCY),
                         ("road",))

    def test_rejects_part_of_cycle(self):
        graph = HierarchicalStructure(
            (node("a"), node("b")),
            (edge("ab", "a", "b"), edge("ba", "b", "a")),
        )
        with self.assertRaises(ValueError):
            graph.validate()

    def test_rejects_taxonomic_cycle(self):
        graph = HierarchicalStructure(
            (node("species"), node("genus")),
            (
                edge("sg", "species", "genus", RelationKind.TAXONOMIC_MEMBER),
                edge("gs", "genus", "species", RelationKind.TAXONOMIC_MEMBER),
            ),
        )
        with self.assertRaises(ValueError):
            graph.validate()

    def test_causal_feedback_loop_is_preserved(self):
        graph = HierarchicalStructure(
            (node("a"), node("b")),
            (
                edge("ab", "a", "b", RelationKind.CAUSAL_INFLUENCE),
                edge("ba", "b", "a", RelationKind.CAUSAL_INFLUENCE),
            ),
        )
        graph.validate()

    def test_functional_feedback_loop_is_preserved(self):
        graph = HierarchicalStructure(
            (node("a"), node("b")),
            (
                edge("ab", "a", "b", RelationKind.FUNCTIONAL_PARTICIPATION),
                edge("ba", "b", "a", RelationKind.FUNCTIONAL_PARTICIPATION),
            ),
        )
        graph.validate()

    def test_rejects_unknown_endpoint(self):
        graph = HierarchicalStructure((node("a"),), (edge("bad", "a", "missing"),))
        with self.assertRaises(ValueError):
            graph.validate()

    def test_requires_evidence(self):
        graph = HierarchicalStructure(
            (node("a"), node("b")),
            (StructureEdge("e", "a", "b", RelationKind.PART_OF, ()),),
        )
        with self.assertRaises(ValueError):
            graph.validate()

    def test_rejects_duplicate_node_ids(self):
        graph = HierarchicalStructure((node("a"), node("a")), ())
        with self.assertRaises(ValueError):
            graph.validate()


if __name__ == "__main__":
    unittest.main()
