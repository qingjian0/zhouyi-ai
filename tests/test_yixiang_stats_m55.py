import unittest

from prototype.yixiang_stats_m55 import (
    benjamini_hochberg_adjust,
    holm_adjust,
    paired_bootstrap_interval,
    paired_comparison,
    power_estimate,
    wilson_interval,
)


class M55StatisticsTests(unittest.TestCase):
    def test_wilson_interval_bounds_observed_rate(self):
        low, high = wilson_interval(5, 100)
        self.assertLessEqual(low, 0.05)
        self.assertGreaterEqual(high, 0.05)
        self.assertLessEqual(0.0, low)
        self.assertLessEqual(high, 1.0)

    def test_holm_adjustment_is_monotone_in_sorted_order(self):
        adjusted = holm_adjust((0.04, 0.001, 0.03))
        self.assertEqual(adjusted, (0.06, 0.003, 0.06))

    def test_bh_adjustment_preserves_original_order(self):
        adjusted = benjamini_hochberg_adjust((0.04, 0.001, 0.03))
        self.assertEqual(adjusted, (0.04, 0.003, 0.04))

    def test_paired_bootstrap_is_reproducible(self):
        first = paired_bootstrap_interval((1, 2, 3, 4), repetitions=1000, seed=19)
        second = paired_bootstrap_interval((1, 2, 3, 4), repetitions=1000, seed=19)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first["mean_difference"], 2.5)

    def test_comparison_requires_matched_seeds(self):
        records = [
            {"scenario": "gaussian", "seed": 1, "method": "A", "f1": 0.8},
            {"scenario": "gaussian", "seed": 1, "method": "B", "f1": 0.6},
            {"scenario": "gaussian", "seed": 2, "method": "A", "f1": 0.7},
            {"scenario": "gaussian", "seed": 2, "method": "B", "f1": 0.5},
        ]
        result = paired_comparison(records, method_a="A", method_b="B",
                                   metric="f1", repetitions=500, seed=2)
        self.assertAlmostEqual(result["mean_difference"], 0.2)
        self.assertEqual(result["paired_units"], 2)

    def test_comparison_rejects_unpaired_seeds(self):
        records = [
            {"scenario": "s", "seed": 1, "method": "A", "f1": 0.8},
            {"scenario": "s", "seed": 2, "method": "B", "f1": 0.5},
        ]
        with self.assertRaisesRegex(ValueError, "unpaired_seed_cells"):
            paired_comparison(records, method_a="A", method_b="B", metric="f1")

    def test_power_reports_uncertainty(self):
        result = power_estimate(80, 100)
        self.assertEqual(result["power"], 0.8)
        self.assertLess(result["wilson_95"][0], 0.8)
        self.assertGreater(result["wilson_95"][1], 0.8)

    def test_invalid_p_values_rejected(self):
        with self.assertRaises(ValueError):
            holm_adjust((0.2, 1.1))


if __name__ == "__main__":
    unittest.main()
