import unittest

from prototype.yijing_hypergraph_induction import (
    Entity, Hyperedge, HypergraphState, RoleBinding,
)
from prototype.yijing_hypergraph_role_induction import (
    HypergraphRoleObservation, RelationSymmetry,
)
from prototype.yijing_hypergraph_automorphism import exact_hypergraph_automorphism_audit
from prototype.yijing_hypergraph_slot_group_induction import (
    ExactSlotGroupInductionError,
    induce_exact_slot_permutation_groups,
)


def make_edge(edge_id, relation, participants, roles=None, attributes=()):
    roles = roles or tuple(f"slot-{i}" for i in range(len(participants)))
    return Hyperedge(
        edge_id, relation,
        tuple(RoleBinding(role, entity) for role, entity in zip(roles, participants)),
        (f"evidence-{edge_id}",), attributes=attributes,
    )


def observation(evidence_id, entities, edges, coverage_complete=True, step=0, domain="synthetic"):
    state = HypergraphState(
        tuple(Entity(entity_id, entity_type) for entity_id, entity_type in entities),
        tuple(edges), (), step, evidence_id, domain, coverage_complete,
    )
    return HypergraphRoleObservation(state, evidence_id, domain)


class ExactSlotGroupInductionTests(unittest.TestCase):
    def test_oracle_mapping_witnesses_are_opt_in(self):
        graph = observation(
            "obs-1",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (make_edge("target", "joint", ("a", "b", "c")),),
        )
        policy = (RelationSymmetry("joint", "UNORDERED"),)
        default = exact_hypergraph_automorphism_audit(graph.state, policy)
        detailed = exact_hypergraph_automorphism_audit(
            graph.state, policy, include_automorphism_mappings=True
        )
        self.assertEqual(default.automorphism_mappings, ())
        self.assertEqual(len(detailed.automorphism_mappings), detailed.automorphism_count)
        self.assertEqual(detailed.automorphism_count, 6)

    def test_snapshot_step_and_domain_are_preserved(self):
        row = observation(
            "obs-temporal",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (make_edge("target", "joint", ("a", "b", "c")),),
            step=7,
            domain="temporal-test",
        )
        report = induce_exact_slot_permutation_groups(
            (row,), (RelationSymmetry("joint", "UNORDERED"),)
        )
        self.assertEqual(report.observation_groups[0].step, 7)
        self.assertEqual(report.observation_groups[0].domain, "temporal-test")

    def test_unconstrained_unordered_edge_induces_s3(self):
        row = observation(
            "obs-1",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (make_edge("target", "joint", ("a", "b", "c")),),
        )
        report = induce_exact_slot_permutation_groups(
            (row,), (RelationSymmetry("joint", "UNORDERED"),)
        )
        hypothesis = report.hypotheses[0]
        self.assertEqual(len(hypothesis.group.generated_group), 6)
        self.assertEqual(len(report.automorphism_audits[0].automorphism_mappings), 6)

    def test_external_context_restricts_slot_group_to_c2(self):
        row = observation(
            "obs-1",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (
                make_edge("target", "joint", ("a", "b", "c")),
                make_edge("ac", "link", ("a", "c")),
                make_edge("bc", "link", ("b", "c")),
            ),
        )
        report = induce_exact_slot_permutation_groups(
            (row,), (
                RelationSymmetry("joint", "UNORDERED"),
                RelationSymmetry("link", "ORDERED"),
            )
        )
        group = report.hypotheses[0].group.generated_group
        self.assertEqual(group, ((0, 1, 2), (1, 0, 2)))

    def test_asymmetric_context_restricts_slot_group_to_identity(self):
        row = observation(
            "obs-1",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (
                make_edge("target", "joint", ("a", "b", "c")),
                make_edge("ac", "link", ("a", "c")),
                make_edge("bc", "link", ("b", "c")),
                make_edge("mark", "marked", ("a", "c")),
            ),
        )
        report = induce_exact_slot_permutation_groups(
            (row,), (
                RelationSymmetry("joint", "UNORDERED"),
                RelationSymmetry("link", "ORDERED"),
                RelationSymmetry("marked", "ORDERED"),
            )
        )
        self.assertEqual(
            report.hypotheses[0].group.generated_group, ((0, 1, 2),)
        )

    def test_new_context_evidence_confirms_c2_to_identity_break(self):
        symmetric = observation(
            "before",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (
                make_edge("target", "joint", ("a", "b", "c")),
                make_edge("ac", "link", ("a", "c")),
                make_edge("bc", "link", ("b", "c")),
            ),
        )
        broken = observation(
            "after",
            (("a2", "node"), ("b2", "node"), ("c2", "node")),
            (
                make_edge("target2", "joint", ("a2", "b2", "c2")),
                make_edge("ac2", "link", ("a2", "c2")),
                make_edge("bc2", "link", ("b2", "c2")),
                make_edge("mark2", "marked", ("a2", "c2")),
            ),
        )
        report = induce_exact_slot_permutation_groups(
            (symmetric, broken), (
                RelationSymmetry("joint", "UNORDERED"),
                RelationSymmetry("link", "ORDERED"),
                RelationSymmetry("marked", "ORDERED"),
            ),
            min_support=1,
        )
        group = report.hypotheses[0].group
        self.assertEqual(group.generated_group, ((0, 1, 2),))
        target_groups = [
            item for item in report.observation_groups
            if item.relation_type == "joint"
        ]
        target_transitions = [
            item for item in report.transitions
            if item.relation_type == "joint"
        ]
        self.assertEqual(len(target_groups), 2)
        self.assertEqual(
            target_groups[0].exact_group,
            ((0, 1, 2), (1, 0, 2)),
        )
        self.assertEqual(
            target_groups[1].exact_group,
            ((0, 1, 2),),
        )
        self.assertEqual(len(target_transitions), 1)
        self.assertEqual(
            target_transitions[0].transition.relation, "SYMMETRY_BROKEN"
        )
        swap01 = next(item for item in group.support if item.permutation == (1, 0, 2))
        self.assertEqual(swap01.status, "CONTRADICTED")
        self.assertEqual(swap01.compatible_evidence_ids, ("before",))
        self.assertEqual(swap01.conflicting_evidence_ids, ("after",))

    def test_repeated_entity_slots_fail_closed(self):
        row = observation(
            "obs-1",
            (("a", "node"), ("b", "node")),
            (make_edge("target", "joint", ("a", "a", "b")),),
        )
        with self.assertRaises(ExactSlotGroupInductionError):
            induce_exact_slot_permutation_groups(
                (row,), (RelationSymmetry("joint", "UNORDERED"),)
            )

    def test_slot_frames_are_not_silently_merged(self):
        left = observation(
            "left",
            (("a", "node"), ("b", "node"), ("c", "node")),
            (make_edge("target", "joint", ("a", "b", "c"), ("x", "y", "z")),),
        )
        right = observation(
            "right",
            (("u", "node"), ("v", "node"), ("w", "node")),
            (make_edge("target2", "joint", ("u", "v", "w"), ("p", "q", "r")),),
        )
        report = induce_exact_slot_permutation_groups(
            (left, right), (RelationSymmetry("joint", "UNORDERED"),), min_support=2
        )
        self.assertEqual(len(report.hypotheses), 2)
        self.assertTrue(all(item.group.generated_group for item in report.hypotheses))


if __name__ == "__main__":
    unittest.main()
