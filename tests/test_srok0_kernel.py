import unittest

from prototype.srok0_kernel import (
    Node, OperatorSpec, RoleSpec, SparseRoleComposer, SROKValidationError,
)


class SROK0KernelTests(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            Node("a", "A", frozenset({"left"}), 0.96, ("ev-a",)),
            Node("b", "B", frozenset({"middle"}), 0.91, ("ev-b",)),
            Node("c", "C", frozenset({"middle"}), 0.87, ("ev-c",)),
            Node("d", "D", frozenset({"noise"}), 0.12, ("ev-d",)),
            Node("e", "E", frozenset({"right"}), 0.83, ("ev-e",)),
        ]
        self.spec = OperatorSpec(
            name="compose-example",
            relation_type="composed",
            roles=(
                RoleSpec("r1", frozenset({"A"})),
                RoleSpec("r2", frozenset({"B"})),
                RoleSpec("r3", frozenset({"C"})),
                RoleSpec("r4", frozenset({"E"})),
            ),
            max_candidates_per_role=8,
            max_expansions=100,
        )

    def test_role_composition_can_skip_unrelated_nodes(self):
        report = SparseRoleComposer(self.nodes).compose(self.spec)
        self.assertEqual(len(report.candidates), 1)
        self.assertEqual(report.candidates[0].member_ids, ("a", "b", "c", "e"))
        self.assertEqual(report.candidates[0].evidence_ids,
                         ("ev-a", "ev-b", "ev-c", "ev-e"))

    def test_required_tags_are_intersected(self):
        spec = OperatorSpec(
            "tagged", "tagged_relation",
            (RoleSpec("source", frozenset({"A"}), frozenset({"left"})),
             RoleSpec("target", frozenset({"E"}), frozenset({"right"}))),
        )
        report = SparseRoleComposer(self.nodes).compose(spec)
        self.assertEqual(report.candidates[0].member_ids, ("a", "e"))

    def test_hard_constraint_rejects_complete_assignment(self):
        report = SparseRoleComposer(self.nodes).compose(
            self.spec, hard_constraint=lambda selected: selected[0].node_id != "a"
        )
        self.assertEqual(report.candidates, ())
        self.assertEqual(report.valid_assignments, 0)

    def test_joint_score_ranks_complete_structures(self):
        extra = Node("a2", "A", frozenset({"left"}), 0.1, ("ev-a2",))
        composer = SparseRoleComposer([*self.nodes, extra])
        report = composer.compose(
            self.spec,
            joint_scorer=lambda selected: 2.0 if selected[0].node_id == "a2" else 0.0,
            limit=2,
        )
        self.assertEqual(report.candidates[0].member_ids[0], "a2")

    def test_expansion_budget_is_reported(self):
        nodes = [
            Node(f"a{i}", "A", score=10-i) for i in range(5)
        ] + [
            Node(f"b{i}", "B", score=10-i) for i in range(5)
        ]
        spec = OperatorSpec(
            "budget", "pair",
            (RoleSpec("left", frozenset({"A"})),
             RoleSpec("right", frozenset({"B"}))),
            max_candidates_per_role=5,
            max_expansions=1,
        )
        report = SparseRoleComposer(nodes).compose(spec)
        self.assertEqual(report.expanded_assignments, 1)
        self.assertTrue(report.budget_exhausted)

    def test_duplicate_node_ids_are_rejected(self):
        with self.assertRaises(SROKValidationError):
            SparseRoleComposer([Node("x", "A"), Node("x", "B")])

    def test_invalid_budget_is_rejected(self):
        spec = OperatorSpec(
            "bad", "bad",
            (RoleSpec("one"), RoleSpec("two")),
            max_expansions=0,
        )
        with self.assertRaises(SROKValidationError):
            SparseRoleComposer(self.nodes).compose(spec)


if __name__ == "__main__":
    unittest.main()
