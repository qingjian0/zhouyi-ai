import unittest

from prototype.yijing_hypergraph_induction import (
    Entity, Hyperedge, HypergraphState, RoleBinding,
)
from prototype.yijing_hypergraph_role_induction import (
    HypergraphRoleInductionError, HypergraphRoleObservation,
    HypergraphSchemaInducer, RelationSymmetry, infer_hypergraph_roles,
)


def make_state(step, participants=("a", "b", "c"), *, role_names=("x", "y", "z"),
               relation="joint", types=("agent", "agent", "agent"), evidence=None):
    entities = tuple(Entity(entity_id, entity_type)
                     for entity_id, entity_type in zip(participants, types))
    edge = Hyperedge(
        f"edge-{step}", relation,
        tuple(RoleBinding(role, entity) for role, entity in zip(role_names, participants)),
        (f"edge-evidence-{step}",),
    )
    return HypergraphState(
        entities, (edge,), (), step, evidence or f"snapshot-{step}", "synthetic", True
    )


class HigherOrderRoleInductionTests(unittest.TestCase):
    def test_ordered_roles_ignore_caller_supplied_role_names(self):
        left = make_state(0, role_names=("actor", "tool", "result"))
        right = make_state(1, role_names=("foo", "bar", "baz"))
        policy = (RelationSymmetry("joint", "ORDERED"),)
        a = infer_hypergraph_roles(left, policy)
        b = infer_hypergraph_roles(right, policy)
        self.assertEqual(
            tuple(x.structural_signature for x in a.assignments),
            tuple(x.structural_signature for x in b.assignments),
        )

    def test_entity_renaming_preserves_alpha_invariant_role_signatures(self):
        left = make_state(0, ("a", "b", "c"))
        right = make_state(1, ("u", "v", "w"))
        policy = (RelationSymmetry("joint", "ORDERED"),)
        a = sorted(x.structural_signature for x in infer_hypergraph_roles(left, policy).assignments)
        b = sorted(x.structural_signature for x in infer_hypergraph_roles(right, policy).assignments)
        self.assertEqual(a, b)

    def test_unordered_relation_is_invariant_to_participant_permutation(self):
        left = make_state(0, ("a", "b", "c"))
        right = make_state(1, ("c", "a", "b"))
        policy = (RelationSymmetry("joint", "UNORDERED"),)
        a = sorted(x.structural_signature for x in infer_hypergraph_roles(left, policy).assignments)
        b = sorted(x.structural_signature for x in infer_hypergraph_roles(right, policy).assignments)
        self.assertEqual(a, b)

    def test_symmetric_participants_remain_one_equivalence_class(self):
        state = make_state(0)
        result = infer_hypergraph_roles(state, (RelationSymmetry("joint", "UNORDERED"),))
        self.assertEqual(len(result.equivalence_classes), 1)
        self.assertEqual(result.equivalence_classes[0].members, ("a", "b", "c"))

    def test_ordered_positions_can_distinguish_same_typed_participants(self):
        state = make_state(0)
        result = infer_hypergraph_roles(state, (RelationSymmetry("joint", "ORDERED"),))
        self.assertEqual(len(result.equivalence_classes), 3)

    def test_relation_arity_is_part_of_higher_order_neighborhood(self):
        triple = make_state(0)
        quadruple_entities = tuple(Entity(x, "agent") for x in ("a", "b", "c", "d"))
        quadruple = HypergraphState(
            quadruple_entities,
            (Hyperedge("h4", "joint", tuple(
                RoleBinding(role, entity) for role, entity in zip(
                    ("r1", "r2", "r3", "r4"), ("a", "b", "c", "d")
                )), ("ev4",)),),
            (), 0, "s4", "synthetic", True,
        )
        policy = (RelationSymmetry("joint", "ORDERED"),)
        self.assertNotEqual(
            infer_hypergraph_roles(triple, policy).assignments[0].structural_signature,
            infer_hypergraph_roles(quadruple, policy).assignments[0].structural_signature,
        )

    def test_missing_symmetry_policy_fails_closed(self):
        with self.assertRaises(HypergraphRoleInductionError):
            infer_hypergraph_roles(make_state(0), ())

    def test_duplicate_symmetry_policy_fails_closed(self):
        with self.assertRaises(HypergraphRoleInductionError):
            infer_hypergraph_roles(
                make_state(0),
                (RelationSymmetry("joint", "ORDERED"), RelationSymmetry("joint", "UNORDERED")),
            )

    def test_schema_induction_does_not_reuse_supplied_role_names(self):
        rows = [
            HypergraphRoleObservation(
                make_state(i, role_names=names), f"obs-{i}", "domain-a"
            )
            for i, names in enumerate((
                ("actor", "tool", "outcome"), ("source", "middle", "target")
            ))
        ]
        report = HypergraphSchemaInducer(min_support=2).discover(
            rows, (RelationSymmetry("joint", "ORDERED"),)
        )
        self.assertEqual(len(report.hypotheses), 1)
        self.assertEqual(report.hypotheses[0].support_evidence_ids, ("obs-0", "obs-1"))

    def test_unordered_schema_pattern_is_canonicalized(self):
        rows = [
            HypergraphRoleObservation(make_state(0), "obs-0", "domain-a"),
            HypergraphRoleObservation(
                make_state(1, ("c", "a", "b")), "obs-1", "domain-a"
            ),
        ]
        report = HypergraphSchemaInducer(min_support=2).discover(
            rows, (RelationSymmetry("joint", "UNORDERED"),)
        )
        self.assertEqual(len(report.hypotheses), 1)
        self.assertEqual(report.hypotheses[0].semantics, "UNORDERED")

    def test_evidence_support_counts_observations_not_duplicate_edges(self):
        state = make_state(0)
        row = HypergraphRoleObservation(state, "obs-0", "domain-a")
        report = HypergraphSchemaInducer(min_support=1).discover(
            (row,), (RelationSymmetry("joint", "ORDERED"),)
        )
        self.assertEqual(report.hypotheses[0].support_evidence_ids, ("obs-0",))

    def test_invalid_refinement_budget_is_rejected(self):
        with self.assertRaises(HypergraphRoleInductionError):
            infer_hypergraph_roles(
                make_state(0), (RelationSymmetry("joint", "ORDERED"),), max_rounds=99
            )


if __name__ == "__main__":
    unittest.main()
