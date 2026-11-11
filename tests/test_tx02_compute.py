import unittest
from prototype.tx02_compute import (
    apply_abstention, apply_episode_abstention, choose_abstention_threshold,
    choose_episode_abstention_threshold, choose_hidden_size_for_compute_budget,
    estimate_forward_macs, probability_metrics, risk_coverage_curve, select_representation,\n    wilson_upper_bound,
)
class TX02ComputeAndCalibrationTests(unittest.TestCase):
    def test_forward_mac_formula_and_scaling(self):
        base = estimate_forward_macs("ONE_HOT", 3, 4, 2, 2)
        self.assertEqual(base, 2 * 2 * 3 * 4 * (6 * 3 + 1))
        self.assertEqual(estimate_forward_macs("ONE_HOT", 3, 8, 2, 2), 2 * base)
    def test_compute_budget(self):
        unit = estimate_forward_macs("TERNARY", 3, 1, 4, 2)
        self.assertEqual(choose_hidden_size_for_compute_budget(
            "TERNARY", 3, unit * 7 + 2, 4, 2), (7, unit * 7))
    def test_budget_below_minimum_rejected(self):
        with self.assertRaises(ValueError):
            choose_hidden_size_for_compute_budget("BINARY", 3, 1, 4, 2)
    def test_probability_metrics(self):
        result = probability_metrics(((0.8, 0.2), (0.4, 0.6)), (0, 0), bins=5)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertGreater(result["nll"], 0)
        self.assertGreater(result["brier_multiclass"], 0)
        with self.assertRaises(ValueError):
            probability_metrics(((0.2, 0.2),), (0,))
    def test_risk_coverage_curve_groups_equal_confidence(self):
        curve = risk_coverage_curve(
            ((0.9, 0.1), (0.9, 0.1), (0.6, 0.4)),
            (0, 1, 0),
        )
        self.assertEqual(curve[1]["accepted"], 2)
        self.assertEqual(curve[1]["coverage"], 2 / 3)
        self.assertEqual(curve[1]["selective_risk"], 0.5)
    def test_wilson_upper_bound_and_validation_threshold(self):
        self.assertGreater(wilson_upper_bound(0, 1), 0.7)
        self.assertLess(wilson_upper_bound(0, 40), 0.1)
        probs = tuple((0.95, 0.05) for _ in range(40)) + tuple(
            (0.55, 0.45) for _ in range(40)
        )
        targets = (0,) * 40 + (1,) * 40
        chosen = choose_abstention_threshold(probs, targets, 0.1)
        self.assertEqual(chosen["accepted"], 40)
        self.assertLessEqual(chosen["risk_upper_bound"], 0.1)
        decisions = apply_abstention(probs, chosen["threshold"])
        self.assertEqual(sum(value is not None for value in decisions), 40)
    def test_episode_level_calibration_uses_episode_correctness_for_k3(self):
        correct = ((0.4, 0.35, 0.25), (0.4, 0.35, 0.25))
        incorrect = ((0.34, 0.33, 0.33), (0.34, 0.33, 0.33))
        probability_episodes = tuple(correct for _ in range(40)) + tuple(
            incorrect for _ in range(40)
        )
        targets = tuple((0, 0) for _ in range(40)) + tuple(
            (0, 1) for _ in range(40)
        )
        chosen = choose_episode_abstention_threshold(
            probability_episodes, targets, 0.1
        )
        self.assertEqual(chosen["accepted"], 40)
        # All confidence ties are deliberately indivisible: no query-level leakage.
        decisions = apply_episode_abstention(
            probability_episodes, chosen["threshold"]
        )
        self.assertEqual(sum(value is not None for value in decisions), 40)
    def test_validation_only_representation_selector(self):
        result = select_representation({
            "TERNARY": {"accuracy": 0.8, "nll": 0.6, "forward_macs": 900, "parameter_count": 100},
            "ONE_HOT": {"accuracy": 0.8, "nll": 0.5, "forward_macs": 1100, "parameter_count": 120},
            "BINARY": {"accuracy": 0.7, "nll": 0.4, "forward_macs": 500, "parameter_count": 80},
        })
        self.assertEqual(result["selected_family"], "ONE_HOT")
        self.assertEqual(result["selection_source"], "validation_only")
        with self.assertRaises(ValueError):
            select_representation({})
    def test_invalid_risk_rejected(self):
        with self.assertRaises(ValueError):
            choose_abstention_threshold(((0.5, 0.5),), (0,), 1.1)
if __name__ == "__main__":
    unittest.main()
