import unittest

from prototype.relation_algebra import (
    Edge, RelationOntology, RelationType, compare_relations,
)


class RelationAlgebraTests(unittest.TestCase):
    def setUp(self):
        self.ontology = RelationOntology({
            "contains": RelationType("contains", inverse_of="inside"),
            "inside": RelationType("inside", inverse_of="contains"),
            "adjacent": RelationType("adjacent", symmetric=True),
            "supports": RelationType("supports"),
        })

    def test_exact_directed_relation_is_preserved(self):
        score = compare_relations(
            source_relations=(Edge("a", "b", "supports"),),
            target_relations=(Edge("x", "y", "supports"),),
            mapping={"a": "x", "b": "y"}, ontology=self.ontology,
        )
        self.assertEqual(score.f1, 1.0)
        self.assertEqual(score.matched, (("x", "y", "supports"),))

    def test_symmetric_relation_allows_endpoint_swap(self):
        score = compare_relations(
            source_relations=(Edge("a", "b", "adjacent"),),
            target_relations=(Edge("y", "x", "adjacent"),),
            mapping={"a": "x", "b": "y"}, ontology=self.ontology,
        )
        self.assertEqual(score.f1, 1.0)

    def test_declared_inverse_allows_semantic_direction_conversion(self):
        score = compare_relations(
            source_relations=(Edge("a", "b", "contains"),),
            target_relations=(Edge("y", "x", "inside"),),
            mapping={"a": "x", "b": "y"}, ontology=self.ontology,
        )
        self.assertEqual(score.f1, 1.0)

    def test_undeclared_reverse_is_not_accepted(self):
        score = compare_relations(
            source_relations=(Edge("a", "b", "supports"),),
            target_relations=(Edge("y", "x", "supports"),),
            mapping={"a": "x", "b": "y"}, ontology=self.ontology,
        )
        self.assertEqual(score.f1, 0.0)
        self.assertEqual(score.missing, (("x", "y", "supports"),))
        self.assertEqual(score.unexpected, (("y", "x", "supports"),))

    def test_unknown_relation_kind_rejected(self):
        with self.assertRaises(ValueError):
            compare_relations(
                source_relations=(Edge("a", "b", "causes"),),
                target_relations=(), mapping={"a": "x", "b": "y"},
                ontology=self.ontology,
            )

    def test_non_reciprocal_inverse_rejected(self):
        with self.assertRaises(ValueError):
            RelationOntology({
                "parent": RelationType("parent", inverse_of="child"),
                "child": RelationType("child"),
            })

    def test_symmetric_and_inverse_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            RelationOntology({
                "near": RelationType("near", symmetric=True, inverse_of="far"),
                "far": RelationType("far", inverse_of="near"),
            })

    def test_duplicate_semantic_edges_rejected(self):
        with self.assertRaises(ValueError):
            compare_relations(
                source_relations=(
                    Edge("a", "b", "contains"), Edge("b", "a", "inside"),
                ),
                target_relations=(Edge("x", "y", "contains"),),
                mapping={"a": "x", "b": "y"}, ontology=self.ontology,
            )

    def test_mapping_must_be_injective_and_complete_for_edges(self):
        with self.assertRaises(ValueError):
            compare_relations(
                source_relations=(Edge("a", "b", "supports"),),
                target_relations=(), mapping={"a": "x", "b": "x"},
                ontology=self.ontology,
            )
        with self.assertRaises(ValueError):
            compare_relations(
                source_relations=(Edge("a", "b", "supports"),),
                target_relations=(), mapping={"a": "x"},
                ontology=self.ontology,
            )

    def test_ontology_has_versioned_identity_and_immutable_types(self):
        self.assertEqual(self.ontology.ontology_id, "relation-ontology")
        self.assertEqual(self.ontology.version, "0.1")
        with self.assertRaises(TypeError):
            self.ontology.types["new"] = RelationType("new")

    def test_rejects_empty_ontology_identity(self):
        with self.assertRaises(ValueError):
            RelationOntology({"r": RelationType("r")}, ontology_id=" ")

    def test_rejects_non_boolean_relation_flags(self):
        with self.assertRaises(ValueError):
            RelationOntology({"adjacent": RelationType("adjacent", symmetric=1)})

    def test_rejects_non_string_edge_endpoints(self):
        with self.assertRaises(ValueError):
            self.ontology.normalize(Edge(1, "b", "supports"))

    def test_reports_missing_and_unexpected_edges(self):
        score = compare_relations(
            source_relations=(Edge("a", "b", "supports"),),
            target_relations=(Edge("x", "z", "supports"),),
            mapping={"a": "x", "b": "y"}, ontology=self.ontology,
        )
        self.assertEqual(score.missing, (("x", "y", "supports"),))
        self.assertEqual(score.unexpected, (("x", "z", "supports"),))
        self.assertEqual(score.precision, 0.0)
        self.assertEqual(score.recall, 0.0)


if __name__ == "__main__":
    unittest.main()
