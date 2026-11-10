import inspect
import unittest

from prototype.e12a2_active_measurement import (
    Hypothesis,
    HypothesisPrediction,
    MeasurementAction,
    OutcomeLikelihood,
    entropy_bits,
    select_measurement,
    update_after_observation,
)


def binary_action(action_id, cost, predictions):
    return MeasurementAction(
        action_id,
        cost,
        tuple(
            HypothesisPrediction(
                hypothesis_id,
                (
                    OutcomeLikelihood("0", float(1 - value)),
                    OutcomeLikelihood("1", float(value)),
                ),
            )
            for hypothesis_id, value in sorted(predictions.items())
        ),
    )


class E12A2ActiveMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.hypotheses = (
            Hypothesis("p_ge_2", 0.5),
            Hypothesis("p_eq_2", 0.5),
        )

    def test_entropy_is_exactly_one_bit_for_two_equal_hypotheses(self):
        self.assertAlmostEqual(entropy_bits([0.5, 0.5]), 1.0)

    def test_selector_chooses_measurement_that_splits_candidates(self):
        actions = (
            binary_action("x0", 1.0, {"p_ge_2": 0, "p_eq_2": 0}),
            binary_action("x2", 1.0, {"p_ge_2": 1, "p_eq_2": 1}),
            binary_action("x3", 1.0, {"p_ge_2": 1, "p_eq_2": 0}),
        )
        result = select_measurement(self.hypotheses, actions, 1.0)
        self.assertEqual(result.status, "SELECTED")
        self.assertEqual(result.selected_action_id, "x3")
        self.assertAlmostEqual(result.information_gain_bits, 1.0)

    def test_all_equivalent_actions_return_explicit_no_discrimination(self):
        actions = (
            binary_action("x0", 1.0, {"p_ge_2": 0, "p_eq_2": 0}),
            binary_action("x2", 1.0, {"p_ge_2": 1, "p_eq_2": 1}),
        )
        result = select_measurement(self.hypotheses, actions, 2.0)
        self.assertEqual(result.status, "NO_DISCRIMINATING_ACTION")
        self.assertIsNone(result.selected_action_id)

    def test_cost_normalization_can_prefer_lower_cost_partial_information(self):
        costly_perfect = binary_action("perfect_cost_2", 2.0, {"p_ge_2": 1, "p_eq_2": 0})
        cheap_partial = MeasurementAction(
            "cheap_partial",
            0.5,
            (
                HypothesisPrediction("p_ge_2", (
                    OutcomeLikelihood("1", 0.75), OutcomeLikelihood("0", 0.25))),
                HypothesisPrediction("p_eq_2", (
                    OutcomeLikelihood("1", 0.25), OutcomeLikelihood("0", 0.75))),
            ),
        )
        result = select_measurement(self.hypotheses, (costly_perfect, cheap_partial), 2.0)
        self.assertEqual(result.selected_action_id, "cheap_partial")

    def test_tie_breaks_by_lower_cost_then_canonical_id(self):
        actions = (
            binary_action("z_action", 2.0, {"p_ge_2": 1, "p_eq_2": 0}),
            binary_action("b_action", 1.0, {"p_ge_2": 1, "p_eq_2": 0}),
            binary_action("a_action", 1.0, {"p_ge_2": 1, "p_eq_2": 0}),
        )
        result = select_measurement(self.hypotheses, actions, 2.0)
        self.assertEqual(result.selected_action_id, "a_action")

    def test_budget_exhaustion_is_explicit(self):
        actions = (binary_action("probe", 1.0, {"p_ge_2": 1, "p_eq_2": 0}),)
        result = select_measurement(self.hypotheses, actions, 0.5)
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")

    def test_impossible_observation_does_not_silently_expand_candidates(self):
        action = binary_action("probe", 1.0, {"p_ge_2": 1, "p_eq_2": 0})
        result = update_after_observation(self.hypotheses, action, "unknown")
        self.assertEqual(result.status, "INCONSISTENT")
        self.assertEqual(result.weights, ())

    def test_observation_updates_only_candidate_weights(self):
        action = binary_action("probe", 1.0, {"p_ge_2": 1, "p_eq_2": 0})
        result = update_after_observation(self.hypotheses, action, "1")
        self.assertEqual(result.status, "UPDATED")
        self.assertEqual(result.weights, (("p_eq_2", 0.0), ("p_ge_2", 1.0)))

    def test_invalid_prior_normalization_is_rejected(self):
        bad = (Hypothesis("h1", 0.4), Hypothesis("h2", 0.4))
        action = binary_action("probe", 1.0, {"h1": 1, "h2": 0})
        result = select_measurement(bad, (action,), 1.0)
        self.assertEqual(result.status, "INVALID_ACTION_SET")

    def test_invalid_likelihood_normalization_is_rejected(self):
        action = MeasurementAction(
            "bad",
            1.0,
            (
                HypothesisPrediction("p_ge_2", (OutcomeLikelihood("1", 0.8),)),
                HypothesisPrediction("p_eq_2", (OutcomeLikelihood("0", 1.0),)),
            ),
        )
        result = select_measurement(self.hypotheses, (action,), 1.0)
        self.assertEqual(result.status, "INVALID_ACTION_SET")

    def test_zero_cost_and_duplicate_actions_are_rejected(self):
        zero_cost = binary_action("zero", 0.0, {"p_ge_2": 1, "p_eq_2": 0})
        result = select_measurement(self.hypotheses, (zero_cost,), 1.0)
        self.assertEqual(result.status, "INVALID_ACTION_SET")
        duplicated = binary_action("same", 1.0, {"p_ge_2": 1, "p_eq_2": 0})
        result = select_measurement(self.hypotheses, (duplicated, duplicated), 1.0)
        self.assertEqual(result.status, "INVALID_ACTION_SET")

    def test_empty_action_set_is_invalid_not_budget_exhausted(self):
        result = select_measurement(self.hypotheses, (), 1.0)
        self.assertEqual(result.status, "INVALID_ACTION_SET")

    def test_learner_api_has_no_evaluator_truth_parameter(self):
        self.assertEqual(
            list(inspect.signature(select_measurement).parameters),
            ["hypotheses", "actions", "remaining_budget", "epsilon", "tie_tolerance"],
        )
        self.assertEqual(
            list(inspect.signature(update_after_observation).parameters),
            ["hypotheses", "action", "observed_outcome"],
        )

    def test_prediction_order_does_not_change_selection(self):
        a = binary_action("a", 1.0, {"p_ge_2": 1, "p_eq_2": 0})
        b = binary_action("b", 1.0, {"p_ge_2": 0, "p_eq_2": 1})
        first = select_measurement(self.hypotheses, (a, b), 1.0)
        second = select_measurement(tuple(reversed(self.hypotheses)), (b, a), 1.0)
        self.assertEqual(first.selected_action_id, second.selected_action_id)
        self.assertAlmostEqual(first.information_gain_bits, second.information_gain_bits)


if __name__ == "__main__":
    unittest.main()
