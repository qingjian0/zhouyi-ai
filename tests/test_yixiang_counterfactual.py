import unittest

from prototype.yixiang_counterfactual import (
    ComparisonKind, ConditionIntervention, ConditionOrigin, ConditionValue,
    ConditionalMapping, RelationState, TruthValue, assess_counterfactual,
)


class CounterfactualTests(unittest.TestCase):
    def setUp(self):
        self.rule = ConditionalMapping(
            "rain-growth", "growth relation", ("moisture",), ("frost",)
        )
        self.base = (
            ConditionValue("moisture", TruthValue.TRUE, ConditionOrigin.OBSERVED, "obs:1"),
            ConditionValue("frost", TruthValue.FALSE, ConditionOrigin.OBSERVED, "obs:2"),
        )

    def test_no_change_is_invariant_under_declared_rule(self):
        result = assess_counterfactual(self.rule, self.base, ())
        self.assertEqual(result.baseline_state, RelationState.ACTIVE)
        self.assertEqual(result.counterfactual_state, RelationState.ACTIVE)
        self.assertEqual(result.comparison, ComparisonKind.INVARIANT)

    def test_intervention_can_deactivate_declared_relation(self):
        result = assess_counterfactual(
            self.rule, self.base,
            (ConditionIntervention("moisture", TruthValue.FALSE),),
        )
        self.assertEqual(result.baseline_state, RelationState.ACTIVE)
        self.assertEqual(result.counterfactual_state, RelationState.INACTIVE)
        self.assertEqual(result.comparison, ComparisonKind.CHANGED)
        self.assertTrue(result.intervention_only)

    def test_unknown_is_not_false(self):
        baseline = (
            ConditionValue("moisture", TruthValue.UNKNOWN, ConditionOrigin.INFERRED),
            ConditionValue("frost", TruthValue.FALSE, ConditionOrigin.OBSERVED, "obs:2"),
        )
        result = assess_counterfactual(self.rule, baseline, ())
        self.assertEqual(result.baseline_state, RelationState.UNKNOWN)
        self.assertEqual(result.comparison, ComparisonKind.UNDETERMINED)
        self.assertIn("moisture", result.unknown_conditions)

    def test_intervention_can_resolve_unknown_condition(self):
        baseline = (
            ConditionValue("moisture", TruthValue.UNKNOWN, ConditionOrigin.INFERRED),
            ConditionValue("frost", TruthValue.FALSE, ConditionOrigin.OBSERVED, "obs:2"),
        )
        result = assess_counterfactual(
            self.rule, baseline,
            (ConditionIntervention("moisture", TruthValue.TRUE),),
        )
        self.assertEqual(result.counterfactual_state, RelationState.ACTIVE)
        self.assertEqual(result.comparison, ComparisonKind.UNDETERMINED)

    def test_unchanged_rule_remains_invariant_when_irrelevant_condition_changes(self):
        result = assess_counterfactual(
            self.rule, self.base,
            (ConditionIntervention("wind", TruthValue.TRUE),),
        )
        self.assertEqual(result.comparison, ComparisonKind.INVARIANT)

    def test_duplicate_conditions_and_interventions_are_rejected(self):
        duplicate = self.base + (self.base[0],)
        with self.assertRaises(ValueError):
            assess_counterfactual(self.rule, duplicate, ())
        with self.assertRaises(ValueError):
            assess_counterfactual(
                self.rule, self.base,
                (ConditionIntervention("moisture", TruthValue.TRUE),
                 ConditionIntervention("moisture", TruthValue.FALSE)),
            )

    def test_invalid_rule_and_unknown_intervention_are_rejected(self):
        with self.assertRaises(ValueError):
            ConditionalMapping("bad", "bad", ("x",), ("x",)).validate()
        with self.assertRaises(ValueError):
            assess_counterfactual(
                self.rule, self.base,
                (ConditionIntervention("moisture", TruthValue.UNKNOWN),),
            )

    def test_observed_condition_requires_source(self):
        with self.assertRaises(ValueError):
            ConditionValue("x", TruthValue.TRUE, ConditionOrigin.OBSERVED).validate()


if __name__ == "__main__":
    unittest.main()
