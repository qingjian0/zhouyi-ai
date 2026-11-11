import unittest

from prototype.yijing_hypergraph_automorphism import exact_hypergraph_automorphism_audit
from prototype.yijing_hypergraph_induction import Entity, Hyperedge, HypergraphState, RoleBinding
from prototype.yijing_hypergraph_role_induction import RelationSymmetry
from prototype.yijing_hypergraph_automorphism_group_bridge import (
    derive_slot_permutation_evidence, group_evidence_by_relation,
)


def make_state(entities, edges):
    return HypergraphState(
        tuple(Entity(i, t) for i, t in entities), tuple(edges), (), 0,
        "snapshot", "synthetic", True,
    )


def make_edge(edge_id, relation, participants, attrs=()):
    return Hyperedge(
        edge_id, relation,
        tuple(RoleBinding(f"slot-{i}", entity) for i, entity in enumerate(participants)),
        (f"evidence-{edge_id}",), attributes=attrs,
    )


class AutomorphismGroupBridgeTests(unittest.TestCase):
    def test_unordered_single_edge_yields_all_slot_permutations(self):
        graph = make_state(
            (("a", "n"), ("b", "n"), ("c", "n")),
            (make_edge("e", "joint", ("a", "b", "c")),),
        )
        policy = (RelationSymmetry("joint", "UNORDERED"),)
        audit = exact_hypergraph_automorphism_audit(graph, policy, include_automorphism_mappings=True)
        induced = derive_slot_permutation_evidence(graph, audit, policy)
        evidence = group_evidence_by_relation(induced)["joint"]
        self.assertEqual(len({item.permutation for item in evidence}), 6)
        self.assertEqual(len({item.evidence_id for item in evidence}), 6)

    def test_ordered_relation_produces_no_nontrivial_slot_evidence(self):
        graph = make_state(
            (("a", "n"), ("b", "n")),
            (make_edge("e", "seq", ("a", "b")),),
        )
        policy = (RelationSymmetry("seq", "ORDERED"),)
        audit = exact_hypergraph_automorphism_audit(graph, policy)
        self.assertEqual(derive_slot_permutation_evidence(graph, audit, policy), ())

    def test_repeated_participants_are_skipped_as_ambiguous(self):
        graph = make_state(
            (("a", "n"),),
            (make_edge("e", "joint", ("a", "a")),),
        )
        policy = (RelationSymmetry("joint", "UNORDERED"),)
        audit = exact_hypergraph_automorphism_audit(graph, policy)
        self.assertEqual(derive_slot_permutation_evidence(graph, audit, policy), ())

    def test_edge_context_and_attributes_gate_matching(self):
        graph = make_state(
            (("a", "n"), ("b", "n")),
            (
                make_edge("e1", "joint", ("a", "b"), (("context", "x"),)),
                make_edge("e2", "joint", ("b", "a"), (("context", "y"),)),
            ),
        )
        policy = (RelationSymmetry("joint", "UNORDERED"),)
        audit = exact_hypergraph_automorphism_audit(graph, policy)
        induced = derive_slot_permutation_evidence(graph, audit, policy)
        self.assertTrue(all(
            item.source_edge_id == item.target_edge_id for item in induced
        ))


if __name__ == "__main__":
    unittest.main()
