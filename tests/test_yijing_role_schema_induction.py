import unittest

from prototype.yijing_operator_induction import Node, Relation, RelationalState
from prototype.yijing_role_schema_induction import (
    RoleSchemaInductionError, RoleSchemaObservation, StructuralSchemaInducer,
    evaluate_schema_stability, infer_structural_roles,
)


def graph(prefix="a", reverse=False, role_prefix="manual"):
    nodes = (
        Node(prefix + "1", "agent", role_prefix + "_actor"),
        Node(prefix + "2", "resource", role_prefix + "_target"),
        Node(prefix + "3", "environment", role_prefix + "_context"),
    )
    edges = (
        Relation(nodes[0].entity_id, nodes[1].entity_id, "supports"),
        Relation(nodes[1].entity_id, nodes[2].entity_id, "constrains"),
    )
    if reverse:
        edges = tuple(Relation(e.target, e.source, e.relation_type, e.attributes) for e in edges)
    return RelationalState(nodes, tuple(sorted(edges)), (("phase", "growth"),))


class StructuralRoleInductionTests(unittest.TestCase):
    def test_role_inference_ignores_entity_ids_and_manual_role_names(self):
        left = infer_structural_roles(graph("a", role_prefix="left"))
        right = infer_structural_roles(graph("z", role_prefix="unrelated"))
        self.assertEqual(
            {item.role_id for item in left.assignments},
            {item.role_id for item in right.assignments},
        )

    def test_direction_changes_structural_roles(self):
        forward = infer_structural_roles(graph("a"))
        reverse = infer_structural_roles(graph("a", reverse=True))
        self.assertNotEqual(
            {item.entity_id: item.role_id for item in forward.assignments},
            {item.entity_id: item.role_id for item in reverse.assignments},
        )

    def test_isomorphic_node_renaming_preserves_schema_ids(self):
        rows = [
            RoleSchemaObservation(graph("a"), "e1", "domain-a"),
            RoleSchemaObservation(graph("x", role_prefix="different"), "e2", "domain-b"),
        ]
        report = StructuralSchemaInducer(min_support=2).discover(rows)
        self.assertEqual(len(report.hypotheses), 2)
        self.assertEqual(
            len({item.schema_id for item in report.hypotheses}),
            2,
        )
        self.assertEqual(
            {item.support_evidence_ids for item in report.hypotheses},
            {("e1", "e2")},
        )

    def test_role_classes_can_merge_structurally_indistinguishable_nodes(self):
        state = RelationalState(
            (
                Node("a", "agent", "human_a"),
                Node("b", "agent", "human_b"),
            ),
            (),
            (),
        )
        result = infer_structural_roles(state)
        self.assertEqual(result.role_count, 1)
        self.assertEqual(result.assignments[0].role_id, result.assignments[1].role_id)

    def test_relation_direction_is_preserved_in_schema(self):
        rows = [RoleSchemaObservation(graph(), "e1", "d1")]
        report = StructuralSchemaInducer(min_support=1).discover(rows)
        pairs = {(item.source_role_id, item.target_role_id) for item in report.hypotheses}
        self.assertEqual(len(pairs), 2)

    def test_support_counts_distinct_observations_not_duplicate_edges(self):
        one = graph()
        # Support is counted by distinct evidence IDs, not edge multiplicity.
        report = StructuralSchemaInducer(min_support=2).discover([
            RoleSchemaObservation(one, "e1", "d1"),
            RoleSchemaObservation(graph("x"), "e2", "d1"),
        ])
        self.assertTrue(all(len(item.support_evidence_ids) == 2 for item in report.hypotheses))

    def test_min_support_filters_single_observation_schemas(self):
        report = StructuralSchemaInducer(min_support=2).discover([
            RoleSchemaObservation(graph(), "e1", "d1")
        ])
        self.assertEqual(report.hypotheses, ())

    def test_heldout_structural_stability_is_reported_separately(self):
        train = [RoleSchemaObservation(graph(), "train", "d1")]
        candidates = StructuralSchemaInducer(min_support=1).discover(train).hypotheses
        heldout = [RoleSchemaObservation(graph("held"), "heldout", "d2")]
        result = evaluate_schema_stability(candidates, heldout)
        self.assertEqual(result.precision, 1.0)
        self.assertEqual(result.recall, 1.0)
        self.assertEqual(result.relation_coverage, 1.0)

    def test_heldout_unseen_relation_is_not_claimed_as_covered(self):
        candidates = StructuralSchemaInducer(min_support=1).discover([
            RoleSchemaObservation(graph(), "train", "d1")
        ]).hypotheses
        unseen = graph("held")
        changed = RelationalState(
            unseen.nodes,
            tuple(sorted((
                Relation("held1", "held2", "unknown_link"),
                unseen.relations[1],
            ))),
            unseen.context,
        )
        result = evaluate_schema_stability(
            candidates, [RoleSchemaObservation(changed, "heldout", "d2")]
        )
        self.assertLess(result.relation_coverage, 1.0)

    def test_search_budget_is_explicit(self):
        rows = [RoleSchemaObservation(graph(), "e1", "d1")]
        report = StructuralSchemaInducer(
            min_support=1, max_hypotheses=1
        ).discover(rows)
        self.assertTrue(report.budget_exhausted)

    def test_invalid_round_budget_is_rejected(self):
        with self.assertRaises(RoleSchemaInductionError):
            infer_structural_roles(graph(), max_rounds=99)

    def test_duplicate_evidence_ids_are_rejected(self):
        row = RoleSchemaObservation(graph(), "same", "d1")
        with self.assertRaises(RoleSchemaInductionError):
            StructuralSchemaInducer(min_support=1).discover((row, row))


if __name__ == "__main__":
    unittest.main()
