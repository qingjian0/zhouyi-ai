import unittest
from prototype.tx02_compute import (
    apply_abstention, choose_abstention_threshold, choose_hidden_size_for_compute_budget,
    estimate_forward_macs, probability_metrics,
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
    def test_validation_threshold_and_defer(self):
        probs = ((0.95, 0.05), (0.55, 0.45), (0.51, 0.49))
        chosen = choose_abstention_threshold(probs, (0, 1, 0), 0.0)
        self.assertEqual(chosen["accepted"], 1)
        self.assertEqual(apply_abstention(probs, chosen["threshold"]), (0, None, None))
    def test_invalid_risk_rejected(self):
        with self.assertRaises(ValueError):
            choose_abstention_threshold(((0.5, 0.5),), (0,), 1.1)
if __name__ == "__main__":
    unittest.main()
