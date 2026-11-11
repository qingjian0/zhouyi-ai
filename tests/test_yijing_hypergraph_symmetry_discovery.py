import unittest

from prototype.yijing_hypergraph_induction import (
    Entity, Hyperedge, HypergraphState, RoleBinding,
)
from prototype.yijing_hypergraph_role_induction import (
    HypergraphRoleObservation, RelationSymmetry,
)
from prototype.yijing_hypergraph_symmetry_discovery import (
    SymmetryDiscoveryError, discover_relation_symmetry,
)


def make_observation(index, *, distinguished=False, names=("p", "q", "r")):
    ids = ("a", "b", "c", "d")
    entities = tuple(Entity(item, "node") for item in ids)
    target = Hyperedge(
        f"target-{index}", "target",
        tuple(RoleBinding(name, entity) for name, entity in zip(names, ids[:3])),
        (f"target-evidence-{index}",),
    )
    edges = [target]
    if distinguished:
        edges.append(Hyperedge(
            f"context-{index}", "context_link",
            (RoleBinding("from", "a"), RoleBinding("to", "d")),
            (f"context-evidence-{index}",),
        ))
    state = HypergraphState(
        entities, tuple(edges), (), index, f"snapshot-{index}", "test", True
    )
    return HypergraphRoleObservation(state, f"obs-{index}", "test-domain")


class RelationSymmetryDiscoveryTests(unittest.TestCase):
    def test_uncontextualized_same_type_slots_remain_exchangeable(self):
        report = discover_relation_symmetry(
            (make_observation(0), make_observation(1)),
            "target", (), min_support=2,
        )
        hypothesis = report.hypotheses[0]
        transposition = next(
            item for item in hypothesis.permutation_evidence
            if item.permutation == (1, 0, 2)
        )
        self.assertEqual(transposition.status, "STRUCTURALLY_COMPATIBLE")
        self.assertEqual(hypothesis.slot_equivalence_classes[0].positions, (0, 1, 2))
        self.assertEqual(hypothesis.semantic_status, "NOT_ESTABLISHED")

    def test_external_context_breaks_only_distinguished_slot_symmetry(self):
        report = discover_relation_symmetry(
            (make_observation(0, distinguished=True),
             make_observation(1, distinguished=True)),
            "target", (RelationSymmetry("context_link", "ORDERED"),),
            min_support=2,
        )
        hypothesis = report.hypotheses[0]
        by_perm = {item.permutation: item for item in hypothesis.permutation_evidence}
        self.assertEqual(by_perm[(1, 0, 2)].status, "CONTRADICTED")
        self.assertEqual(by_perm[(0, 2, 1)].status, "STRUCTURALLY_COMPATIBLE")
        self.assertIn((1, 2), [item.positions for item in hypothesis.slot_equivalence_classes])

    def test_single_observation_does_not_confirm_min_support_two(self):
        report = discover_relation_symmetry(
            (make_observation(0),), "target", (), min_support=2,
        )
        self.assertTrue(all(
            item.status in {"UNRESOLVED", "STRUCTURALLY_COMPATIBLE"}
            for item in report.hypotheses[0].permutation_evidence
        ))
        self.assertEqual(
            next(item for item in report.hypotheses[0].permutation_evidence
                 if item.permutation == (1, 0, 2)).status,
            "UNRESOLVED",
        )

    def test_role_names_and_entity_ids_do_not_change_permutation_status(self):
        left = discover_relation_symmetry(
            (make_observation(0, distinguished=True),),
            "target", (RelationSymmetry("context_link", "ORDERED"),),
            min_support=1,
        )
        right = discover_relation_symmetry(
            (make_observation(2, distinguished=True, names=("x", "y", "z")),),
            "target", (RelationSymmetry("context_link", "ORDERED"),),
            min_support=1,
        )
        a = [(x.permutation, x.status) for x in left.hypotheses[0].permutation_evidence]
        b = [(x.permutation, x.status) for x in right.hypotheses[0].permutation_evidence]
        self.assertEqual(a, b)

    def test_missing_context_policy_fails_closed(self):
        with self.assertRaises(SymmetryDiscoveryError):
            discover_relation_symmetry(
                (make_observation(0, distinguished=True),), "target", (), min_support=1
            )

    def test_target_policy_cannot_leak_into_external_context(self):
        with self.assertRaises(SymmetryDiscoveryError):
            discover_relation_symmetry(
                (make_observation(0),), "target",
                (RelationSymmetry("target", "UNORDERED"),), min_support=1,
            )

    def test_duplicate_observation_evidence_is_rejected(self):
        first = make_observation(0)
        second = HypergraphRoleObservation(first.state, first.evidence_id, first.domain)
        with self.assertRaises(SymmetryDiscoveryError):
            discover_relation_symmetry((first, second), "target", ())

    def test_permutation_budget_fails_closed(self):
        with self.assertRaises(SymmetryDiscoveryError):
            discover_relation_symmetry(
                (make_observation(0),), "target", (), max_permutations=5
            )


if __name__ == "__main__":
    unittest.main()
