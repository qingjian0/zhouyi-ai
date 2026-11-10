import unittest

from prototype.e12a2_active_measurement_selector import (
    expected_information_gain,
    select_measurement,
    update_weights,
)


class ActiveMeasurementSelectorTests(unittest.TestCase):
    def setUp(self):
        self.weights = {"h1": 0.5, "h2": 0.5}
        self.split = {
            "h1": {"yes": 1.0, "no": 0.0},
            "h2": {"yes": 0.0, "no": 1.0},
        }
        self.same = {
            "h1": {"yes": 1.0, "no": 0.0},
            "h2": {"yes": 1.0, "no": 0.0},
        }

    def test_equal_split_has_one_bit_information_gain(self):
        self.assertAlmostEqual(expected_information_gain(self.weights, self.split), 1.0)

    def test_agreement_has_zero_information_gain(self):
        self.assertAlmostEqual(expected_information_gain(self.weights, self.same), 0.0)

    def test_selects_positive_information_action(self):
        result = select_measurement(
            self.weights,
            {"uninformative": self.same, "split": self.split},
            {"uninformative": 0.1, "split": 1.0},
            1.0,
        )
        self.assertEqual(result["status"], "SELECTED")
        self.assertEqual(result["selected_action"], "split")

    def test_cost_normalization_changes_choice(self):
        three_way = {
            "cheap": self.split,
            "expensive": {
                "h1": {"a": 0.5, "b": 0.5, "c": 0.0, "d": 0.0},
                "h2": {"a": 0.0, "b": 0.0, "c": 0.5, "d": 0.5},
            },
        }
        result = select_measurement(
            self.weights, three_way, {"cheap": 1.0, "expensive": 4.0}, 4.0
        )
        self.assertEqual(result["selected_action"], "cheap")

    def test_no_discriminating_action(self):
        result = select_measurement(
            self.weights, {"same": self.same}, {"same": 1.0}, 1.0
        )
        self.assertEqual(result["status"], "NO_DISCRIMINATING_ACTION")

    def test_budget_exhausted_when_no_action_fits(self):
        result = select_measurement(
            self.weights, {"split": self.split}, {"split": 2.0}, 1.0
        )
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")

    def test_deterministic_tie_break_uses_cost_then_id(self):
        result = select_measurement(
            self.weights,
            {"z_action": self.split, "a_action": self.split},
            {"z_action": 1.0, "a_action": 1.0},
            1.0,
        )
        self.assertEqual(result["selected_action"], "a_action")

    def test_bayesian_update_after_revealed_outcome(self):
        posterior = update_weights(self.weights, self.split, "yes")
        self.assertEqual(posterior, {"h1": 1.0, "h2": 0.0})

    def test_impossible_observation_is_rejected(self):
        with self.assertRaises(ValueError):
            update_weights(self.weights, self.split, "unknown")

    def test_invalid_probability_mass_is_rejected(self):
        bad = {
            "h1": {"yes": 0.2, "no": 0.2},
            "h2": {"yes": 0.0, "no": 1.0},
        }
        with self.assertRaises(ValueError):
            expected_information_gain(self.weights, bad)


if __name__ == "__main__":
    unittest.main()
