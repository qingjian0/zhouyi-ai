import inspect
import unittest
from prototype.e12a1_typed_predicate_induction import (
    Example, FeatureSpec, LearnerView, Predicate, demo_view, infer,
    propose_predicates, validate_view,
)

class E12A1TypedPredicateTests(unittest.TestCase):
    def test_proposals_are_typed_and_grounded_in_train_values(self):
        ps = propose_predicates(demo_view())
        self.assertTrue(ps)
        self.assertTrue(any(p.feature == "weather" and p.operator == "EQ" for p in ps))
        self.assertTrue(any(p.feature == "temperature" and p.operator == "GE" for p in ps))

    def test_correlated_demo_preserves_structural_ambiguity(self):
        # Temperature, speed, and weather co-vary; the learner must not
        # pretend that the observed data identifies which feature matters.
        result = infer(demo_view())
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertIsNone(result["selected"])
        self.assertGreater(result["gate_consistent_count"], 1)

    def test_parity_predicate_can_be_uniquely_identified(self):
        view = LearnerView(
            schema=(FeatureSpec("x", "numeric"),),
            train=tuple(Example((("x", x),), int(x % 2 == 0)) for x in range(4)),
            gate=(Example((("x", 4),), 1), Example((("x", 5),), 0)),
        )
        result = infer(view)
        self.assertEqual(result["status"], "IDENTIFIABLE")
        self.assertEqual(result["selected"].operator, "PARITY")
        self.assertEqual(result["selected"].threshold, 0)

    def test_budget_is_enforced(self):
        result = infer(demo_view(), candidate_budget=1)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["evaluated_count"], 1)
        self.assertIsNone(result["selected"])

    def test_numeric_predicate_rejects_string(self):
        with self.assertRaises(TypeError):
            Predicate("x", "numeric", "GE", 2).evaluate("two")

    def test_categorical_predicate_rejects_number(self):
        with self.assertRaises(TypeError):
            Predicate("kind", "categorical", "EQ", "rain").evaluate(1)

    def test_schema_mismatch_is_rejected(self):
        view = LearnerView(
            (FeatureSpec("x", "numeric"),),
            (Example((("x", 1), ("extra", 2)), 0),),
            (Example((("x", 2),), 1),),
        )
        with self.assertRaises(ValueError):
            validate_view(view)

    def test_gate_rejects_train_shortcut(self):
        view = LearnerView(
            (FeatureSpec("x", "numeric"), FeatureSpec("kind", "categorical")),
            (
                Example((("kind", "a"), ("x", 0)), 0),
                Example((("kind", "b"), ("x", 1)), 1),
                Example((("kind", "a"), ("x", 2)), 0),
                Example((("kind", "b"), ("x", 3)), 1),
            ),
            (
                Example((("kind", "a"), ("x", 4)), 1),
                Example((("kind", "b"), ("x", 5)), 0),
            ),
        )
        self.assertEqual(infer(view)["status"], "INCONSISTENT")

    def test_order_does_not_change_proposals(self):
        view = demo_view()
        reordered = LearnerView(
            tuple(reversed(view.schema)),
            tuple(reversed(view.train)),
            tuple(reversed(view.gate)),
        )
        self.assertEqual(propose_predicates(view), propose_predicates(reordered))

    def test_gate_changes_do_not_change_proposals(self):
        view = demo_view()
        changed = LearnerView(
            view.schema, view.train,
            tuple(Example(ex.values, 1 - ex.label) for ex in view.gate),
        )
        self.assertEqual(propose_predicates(view), propose_predicates(changed))

    def test_learner_api_has_no_truth_argument(self):
        self.assertEqual(
            list(inspect.signature(infer).parameters),
            ["view", "candidate_budget"],
        )

if __name__ == "__main__":
    unittest.main()
