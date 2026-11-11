import unittest

from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal, RoleBinding, RoleRequirement, UnificationConstraints,
    UnificationError, VariableRef, VariableRelation, VariableSpec,
    unify_hyperedges,
)


class TypedHyperedgeUnifierTests(unittest.TestCase):
    def setUp(self):
        self.x = VariableRef("worldline-A", "cause")
        self.y = VariableRef("worldline-A", "effect")
        self.z = VariableRef("worldline-A", "outcome")
        self.variables = (
            VariableSpec(self.x, "Entity"),
            VariableSpec(self.y, "Entity"),
            VariableSpec(self.z, "Entity"),
        )

    def edge(self, edge_id, relation, roles, *, branch="b1", evidence=(),
             start=None, end=None, parent="s0"):
        return HyperedgeProposal(
            edge_id, parent, branch, relation, tuple(roles), tuple(evidence),
            start, end,
        )

    def test_unifies_shared_variable_across_non_adjacent_edges(self):
        result = unify_hyperedges(
            [
                self.edge("e1", "causes", [
                    RoleBinding("source", self.x, "rain", "WeatherEvent"),
                    RoleBinding("target", self.y, "flood", "Event"),
                ], branch="forward", evidence=("ev-a",)),
                self.edge("e2", "amplifies", [
                    RoleBinding("source", self.y, "flood", "Event"),
                    RoleBinding("target", self.z, "damage", "Outcome"),
                ], branch="analogy", evidence=("ev-b",)),
            ],
            self.variables,
            UnificationConstraints(subtype_of=(
                ("WeatherEvent", "Event"),
                ("Outcome", "Entity"),
                ("Event", "Entity"),
            )),
        )
        self.assertEqual(result.edge_ids, ("e1", "e2"))
        self.assertEqual(result.branch_ids, ("analogy", "forward"))
        self.assertEqual(result.evidence_refs, ("ev-a", "ev-b"))
        y = next(item for item in result.variables if self.y in item.refs)
        self.assertEqual(y.member_id, "flood")
        self.assertEqual(y.member_type, "Event")

    def test_equality_constraint_unifies_distinct_variable_names(self):
        other = VariableRef("worldline-A", "same-as-cause")
        result = unify_hyperedges(
            [self.edge("e1", "observes", [
                RoleBinding("subject", self.x, "storm", "Event"),
                RoleBinding("object", other, "storm", "Event"),
            ])],
            (*self.variables, VariableSpec(other, "Entity")),
            UnificationConstraints(equal=(VariableRelation(self.x, other),)),
        )
        merged = next(item for item in result.variables if self.x in item.refs)
        self.assertIn(other, merged.refs)

    def test_equal_variables_with_different_members_are_rejected(self):
        other = VariableRef("worldline-A", "same-as-cause")
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [self.edge("e1", "observes", [
                    RoleBinding("subject", self.x, "storm", "Entity"),
                    RoleBinding("object", other, "rain", "Entity"),
                ])],
                (*self.variables, VariableSpec(other, "Entity")),
                UnificationConstraints(equal=(VariableRelation(self.x, other),)),
            )

    def test_not_equal_variables_must_resolve_to_distinct_members(self):
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [self.edge("e1", "compares", [
                    RoleBinding("left", self.x, "same", "Entity"),
                    RoleBinding("right", self.y, "same", "Entity"),
                ])],
                self.variables,
                UnificationConstraints(not_equal=(VariableRelation(self.x, self.y),)),
            )

    def test_required_role_is_enforced(self):
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [self.edge("e1", "causes", [
                    RoleBinding("source", self.x, "rain", "Entity"),
                ])],
                self.variables,
                UnificationConstraints(role_requirements=(
                    RoleRequirement("causes", "target", required=True),
                )),
            )

    def test_role_member_type_is_checked(self):
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [self.edge("e1", "causes", [
                    RoleBinding("source", self.x, "rain", "Weather"),
                ])],
                self.variables,
            )

    def test_subtype_compatibility_is_transitive(self):
        result = unify_hyperedges(
            [self.edge("e1", "observes", [
                RoleBinding("subject", self.x, "rain", "Thunderstorm"),
            ])],
            self.variables,
            UnificationConstraints(subtype_of=(
                ("Thunderstorm", "Storm"), ("Storm", "Entity"),
            )),
        )
        self.assertEqual(result.variables[0].member_id, "rain")

    def test_different_parent_states_cannot_unify(self):
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [
                    self.edge("e1", "r1", [
                        RoleBinding("a", self.x, "one", "Entity"),
                    ], parent="s0"),
                    self.edge("e2", "r2", [
                        RoleBinding("b", self.y, "two", "Entity"),
                    ], parent="s1"),
                ],
                self.variables,
            )

    def test_temporal_scopes_are_intersected(self):
        result = unify_hyperedges(
            [
                self.edge("e1", "r1", [
                    RoleBinding("a", self.x, "one", "Entity"),
                ], start=10, end=30),
                self.edge("e2", "r2", [
                    RoleBinding("b", self.y, "two", "Entity"),
                ], start=20, end=40),
            ],
            self.variables,
        )
        self.assertEqual((result.active_from, result.active_until), (20, 30))

    def test_disjoint_temporal_scopes_are_rejected(self):
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [
                    self.edge("e1", "r1", [
                        RoleBinding("a", self.x, "one", "Entity"),
                    ], start=0, end=10),
                    self.edge("e2", "r2", [
                        RoleBinding("b", self.y, "two", "Entity"),
                    ], start=10, end=20),
                ],
                self.variables,
            )

    def test_evidence_provenance_is_preserved(self):
        result = unify_hyperedges(
            [
                self.edge("e1", "r1", [
                    RoleBinding("a", self.x, "same", "Entity"),
                ], evidence=("source-a",)),
                self.edge("e2", "r2", [
                    RoleBinding("b", self.y, "same", "Entity"),
                ], evidence=("source-b",)),
            ],
            self.variables,
        )
        self.assertEqual(result.evidence_refs, ("source-a", "source-b"))

    def test_subtype_cycles_are_rejected(self):
        with self.assertRaises(UnificationError):
            unify_hyperedges(
                [self.edge("e1", "r1", [
                    RoleBinding("a", self.x, "one", "Entity"),
                ])],
                self.variables,
                UnificationConstraints(subtype_of=(("A", "B"), ("B", "A"))),
            )


if __name__ == "__main__":
    unittest.main()
