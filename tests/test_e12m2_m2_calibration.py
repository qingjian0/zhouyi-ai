import unittest

from prototype.e12m2_m2_calibration import (
    _margins,
    _pair_count,
    make_fixed_margin_dataset,
    plant_pair,
    run_calibration,
)


class E12M2CalibrationTests(unittest.TestCase):
    def test_generator_has_exact_balanced_margins(self):
        rows = make_fixed_margin_dataset(rows=24, items=6, row_size=3,
                                         seed=4, mixing_swaps_per_edge=8)
        row_degrees, item_degrees = _margins(rows)
        self.assertEqual(row_degrees, (3,) * 24)
        self.assertEqual(dict(item_degrees), {f"item_{i}": 12 for i in range(6)})

    def test_planted_pair_increases_joint_count_and_preserves_margins(self):
        rows = make_fixed_margin_dataset(rows=24, items=6, row_size=3,
                                         seed=11, mixing_swaps_per_edge=10)
        planted, applied = plant_pair(rows, ("item_0", "item_1"),
                                      injections=3, seed=12)
        self.assertEqual(_margins(rows), _margins(planted))
        self.assertEqual(applied, 3)
        self.assertEqual(_pair_count(planted, ("item_0", "item_1")),
                         _pair_count(rows, ("item_0", "item_1")) + 3)

    def test_calibration_is_deterministic_and_reports_both_conditions(self):
        kwargs = dict(seeds=2, permutations=7, swaps_per_edge=2,
                      injections=2, seed_start=40)
        first = run_calibration(**kwargs)
        second = run_calibration(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(len(first["null"]["p_values"]), 2)
        self.assertEqual(len(first["planted"]["p_values"]), 2)
        self.assertEqual(first["planted"]["observed_pair_count_gain"], [2, 2])
        for key in (
            "candidate_rejection_rate_wilson_95",
            "max_statistic_rejection_rate_wilson_95",
        ):
            low, high = first["null"][key]
            self.assertLessEqual(0.0, low)
            self.assertLessEqual(low, high)
            self.assertLessEqual(high, 1.0)
        for key in (
            "candidate_detection_rate_wilson_95",
            "max_statistic_detection_rate_wilson_95",
        ):
            low, high = first["planted"][key]
            self.assertLessEqual(0.0, low)
            self.assertLessEqual(low, high)
            self.assertLessEqual(high, 1.0)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            make_fixed_margin_dataset(rows=10, items=6, row_size=2)
        with self.assertRaises(ValueError):
            run_calibration(seeds=0)


if __name__ == "__main__":
    unittest.main()
