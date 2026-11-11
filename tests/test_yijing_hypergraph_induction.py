import unittest

from prototype.yijing_hypergraph_induction import (
    DynamicHypergraphEvolution, Entity, Hyperedge, HypergraphError,
    HypergraphState, RoleBinding, structural_signature,
)


def edge(edge_id="h", actors=("a", "b", "c"), relation="joint"):
    return Hyperedge(
        edge_id, relation,
        tuple(RoleBinding(role, entity) for role, entity in zip(
            ("initiator", "mediator", "outcome"), actors
        )),
        ("edge-evidence",), (("phase", "active"),),
    )


def state(step, edge_rows, *, entities=("a", "b", "c"), complete=False, evidence=None):
    return HypergraphState(
        tuple(Entity(x, "agent") for x in entities), tuple(edge_rows),
        (("environment", "lab"),), step, evidence or f"snapshot-{step}",
        "synthetic", complete,
    )


class TypedHypergraphTests(unittest.TestCase):
    def test_nary_edge_is_atomic_and_retains_all_role_bindings(self):
        item = edge()
        self.assertEqual(len(item.bindings), 3)
        self.assertEqual(tuple(x.role for x in item.bindings),
                         ("initiator", "mediator", "outcome"))

    def test_rejects_binary_projection_style_missing_role(self):
        with self.assertRaises(HypergraphError):
            Hyperedge("h", "joint", (RoleBinding("a", "x"),),
                      ("ev",))

    def test_role_order_is_semantically_significant(self):
        left = HypergraphState(
            (Entity("a", "agent"), Entity("b", "resource"), Entity("c", "context")),
            (Hyperedge("h", "joint", (
                RoleBinding("initiator", "a"), RoleBinding("mediator", "b"),
                RoleBinding("outcome", "c")), ("ev1",), (("phase", "active"),)),),
            (), 0, "s0", "typed",
        )
        swapped = Hyperedge(
            "other", "joint",
            (RoleBinding("initiator", "b"), RoleBinding("mediator", "a"),
             RoleBinding("outcome", "c")),
            ("ev2",), (("phase", "active"),),
        )
        right = HypergraphState(left.entities, (swapped,), (), 1, "s1", "typed")
        self.assertNotEqual(structural_signature(left.hyperedges[0], left),
                            structural_signature(right.hyperedges[0], right))

    def test_entity_renaming_does_not_change_signature(self):
        left = state(0, [edge()], entities=("a", "b", "c"))
        renamed = state(1, [edge("renamed", ("x", "y", "z"))],
                        entities=("x", "y", "z"))
        self.assertEqual(structural_signature(left.hyperedges[0], left),
                         structural_signature(renamed.hyperedges[0], renamed))

    def test_unknown_entity_is_rejected(self):
        with self.assertRaises(HypergraphError):
            state(0, [edge()], entities=("a", "b"))

    def test_duplicate_context_keys_are_rejected(self):
        with self.assertRaises(HypergraphError):
            Hyperedge("h", "joint", edge().bindings, ("ev",),
                      (("phase", "one"), ("phase", "two")))

    def test_duplicate_snapshot_context_keys_are_rejected(self):
        with self.assertRaises(HypergraphError):
            HypergraphState(
                (Entity("a", "agent"),), (), (("world", "one"), ("world", "two")),
                0, "ev", "test",
            )

    def test_duplicate_snapshot_evidence_is_rejected(self):
        with self.assertRaises(HypergraphError):
            DynamicHypergraphEvolution().analyze([
                state(0, [edge()], evidence="same"),
                state(1, [edge()], evidence="same"),
            ])

    def test_persistent_hyperedge_is_confirmed_over_adjacent_transitions(self):
        rows = [state(i, [edge()]) for i in range(3)]
        result = DynamicHypergraphEvolution().analyze(rows)
        persist = [x for x in result.events if x.kind == "PERSIST"]
        self.assertEqual(len(persist), 2)
        self.assertTrue(all(x.status == "CONFIRMED" for x in persist))

    def test_relation_change_is_transform_not_pairwise_edges(self):
        changed = edge(relation="joint-v2")
        result = DynamicHypergraphEvolution(min_consecutive_transitions=1).analyze([
            state(0, [edge()]), state(1, [changed])
        ])
        self.assertIn("TRANSFORM", {x.kind for x in result.events})

    def test_role_rebinding_is_temporal_transform_even_for_same_entity_types(self):
        before = edge()
        after = Hyperedge(
            "h", "joint",
            (RoleBinding("initiator", "b"), RoleBinding("mediator", "a"),
             RoleBinding("outcome", "c")),
            ("edge-evidence-2",), (("phase", "active"),),
        )
        result = DynamicHypergraphEvolution(min_consecutive_transitions=1).analyze([
            state(0, [before]), state(1, [after])
        ])
        self.assertIn("TRANSFORM", {x.kind for x in result.events})

    def test_incomplete_absence_never_dissolves(self):
        result = DynamicHypergraphEvolution(min_consecutive_transitions=1).analyze([
            state(0, [edge()]), state(1, [], entities=("x", "y", "z"), complete=False)
        ])
        self.assertNotIn("DISSOLVE", {x.kind for x in result.events})
        self.assertEqual(result.incomplete_absence_checks, 1)

    def test_complete_absence_can_propose_dissolution(self):
        result = DynamicHypergraphEvolution(min_consecutive_transitions=1).analyze([
            state(0, [edge()]), state(1, [], entities=("a", "b", "c"), complete=True)
        ])
        self.assertIn("DISSOLVE", {x.kind for x in result.events})

    def test_relation_can_dissolve_while_entities_remain(self):
        result = DynamicHypergraphEvolution(min_consecutive_transitions=1).analyze([
            state(0, [edge()]), state(1, [], entities=("a", "b", "c"), complete=True)
        ])
        dissolve = [x for x in result.events if x.kind == "DISSOLVE"]
        self.assertEqual(len(dissolve), 1)
        self.assertEqual(dissolve[0].status, "CONFIRMED")

    def test_relation_reappearance_breaks_dissolution_hysteresis(self):
        result = DynamicHypergraphEvolution(min_consecutive_transitions=2).analyze([
            state(0, [edge()]),
            state(1, [], entities=("a", "b", "c"), complete=True),
            state(2, [edge()], entities=("a", "b", "c"), complete=True),
        ])
        dissolve = [x for x in result.events if x.kind == "DISSOLVE"]
        self.assertEqual(len(dissolve), 1)
        self.assertEqual(dissolve[0].status, "CANDIDATE")

    def test_multiple_relations_are_not_flattened(self):
        second = Hyperedge("h2", "joint-2",
            (RoleBinding("cause", "a"), RoleBinding("effect", "b"),
             RoleBinding("context", "c")), ("ev2",))
        snapshot = state(0, [edge(), second])
        self.assertEqual(len(snapshot.hyperedges), 2)
        self.assertEqual(sum(len(x.bindings) for x in snapshot.hyperedges), 6)


if __name__ == "__main__":
    unittest.main()
