import unittest

from prototype.znca_core import Evidence, Entity, ObservationEvent, Relation, RoleBinding

from prototype.znca_dynamics import (
    DynamicsError, InfluenceTerm, RelationalDynamicsModel, SourceSlot,
    StateSnapshot, TransitionExample, influence_term_from_relation,
)


def snapshot(**values):
    return StateSnapshot.from_mapping(values)


class RelationalDynamicsTests(unittest.TestCase):
    def test_higher_order_term_learns_joint_activation(self):
        rows = []
        for x in (0.0, 1.0):
            for y in (0.0, 1.0):
                target = 1.0 if x == 1.0 and y == 1.0 else 0.0
                rows.append(TransitionExample(
                    snapshot(x=x, y=y, z=0.0),
                    snapshot(x=x, y=y, z=target),
                    f"synthetic:{int(x)}:{int(y)}",
                ))
        term = InfluenceTerm(
            "joint-xy", "joint_enables",
            (SourceSlot("condition_a", "x"), SourceSlot("condition_b", "y")),
            "z", 1, 0.5,
        )
        model = RelationalDynamicsModel((term,), biases={"z": -1.0})
        report = model.fit(rows, epochs=2500, learning_rate=0.5)
        self.assertLess(report.final_loss, report.initial_loss * 0.2)
        self.assertGreater(model.predict(snapshot(x=1, y=1, z=0)).as_dict()["z"], 0.8)
        for x, y in ((0, 0), (0, 1), (1, 0)):
            self.assertLess(model.predict(snapshot(x=x, y=y, z=0)).as_dict()["z"], 0.2)

    def test_pairwise_paths_add_synchronous_influence(self):
        terms = (
            InfluenceTerm("a-to-c", "supports", (SourceSlot("cause", "a"),), "c", 1, 2.0),
            InfluenceTerm("b-to-c", "supports", (SourceSlot("cause", "b"),), "c", 1, 2.0),
        )
        model = RelationalDynamicsModel(terms, biases={"c": -2.0})
        result = model.predict(snapshot(a=1, b=1, c=0)).as_dict()
        self.assertGreater(result["c"], 0.8)
        self.assertEqual(model.predict(snapshot(a=1, b=1, c=0)).as_dict(), result)

    def test_inhibitory_relation_reduces_target_activation(self):
        positive = InfluenceTerm("positive", "promotes", (SourceSlot("agent", "a"),), "z", 1, 2.0)
        negative = InfluenceTerm("negative", "inhibits", (SourceSlot("agent", "a"),), "z", -1, 2.0)
        pos_model = RelationalDynamicsModel((positive,), biases={"z": 0.0})
        neg_model = RelationalDynamicsModel((negative,), biases={"z": 0.0})
        state = snapshot(a=1, z=0)
        self.assertGreater(pos_model.predict(state).as_dict()["z"], 0.5)
        self.assertLess(neg_model.predict(state).as_dict()["z"], 0.5)

    def test_rollout_uses_previous_state(self):
        term = InfluenceTerm("self", "persists", (SourceSlot("prior", "x"),), "x", 1, 1.0)
        model = RelationalDynamicsModel((term,), biases={"x": -1.0})
        states = model.rollout(snapshot(x=0.9), 3)
        self.assertEqual(len(states), 4)
        self.assertNotEqual(states[0], states[1])

    def test_missing_source_is_rejected(self):
        term = InfluenceTerm("bad", "r", (SourceSlot("cause", "missing"),), "z")
        model = RelationalDynamicsModel((term,), biases={"z": 0})
        with self.assertRaises(DynamicsError):
            model.predict(snapshot(x=0, z=0))

    def test_invalid_duplicate_roles_are_rejected(self):
        with self.assertRaises(DynamicsError):
            InfluenceTerm("bad", "r", (
                SourceSlot("same", "a"), SourceSlot("same", "b")
            ), "z")

    def test_n1_relation_compiles_to_role_preserving_operator(self):
        relation = Relation(
            "assertion-1", "enables",
            (RoleBinding("agent", "a"), RoleBinding("target", "z"),
             RoleBinding("condition", "b")),
            ("evidence-1",), 1,
        )
        term = influence_term_from_relation(relation, target_role="target")
        self.assertEqual(term.target, "z")
        self.assertEqual(
            {(slot.role, slot.state_key) for slot in term.sources},
            {("agent", "a"), ("condition", "b")},
        )
        self.assertEqual(term.evidence_refs, ("evidence-1",))

    def test_unknown_target_role_rejected_by_adapter(self):
        relation = Relation(
            "assertion-2", "enables",
            (RoleBinding("agent", "a"), RoleBinding("target", "z")),
            ("evidence-1",), 1,
        )
        with self.assertRaises(DynamicsError):
            influence_term_from_relation(relation, target_role="missing")

    def test_complemented_source_slot_supports_negation(self):
        term = InfluenceTerm(
            "not-a", "absence_enables",
            (SourceSlot("condition", "a", True),), "z", 1, 4.0
        )
        model = RelationalDynamicsModel((term,), biases={"z": -2.0})
        result = model.predict(snapshot(a=0, z=0)).as_dict()["z"]
        self.assertGreater(result, 0.8)

    def test_state_values_are_bounded(self):
        with self.assertRaises(DynamicsError):
            snapshot(x=1.2)

    def test_fit_requires_consistent_state_schema(self):
        term = InfluenceTerm("x", "r", (SourceSlot("cause", "x"),), "z")
        model = RelationalDynamicsModel((term,), biases={"z": 0})
        rows = [TransitionExample(snapshot(x=0, z=0), snapshot(x=0, z=1), "ev1"),
                TransitionExample(snapshot(x=0, y=0, z=0), snapshot(x=0, y=0, z=1), "ev2")]
        with self.assertRaises(DynamicsError):
            model.fit(rows)


if __name__ == "__main__":
    unittest.main()
