import unittest
from collections import Counter

from prototype.e12m2_mixing_sensitivity import (
    make_heterogeneous_dataset,
    run_mixing_sensitivity,
    _gini,
)


class E12M2MixingSensitivityTests(unittest.TestCase):
    def test_heterogeneous_generator_is_deterministic_and_has_skewed_margins(self):
        first = make_heterogeneous_dataset(
            rows=36, items=8, min_row_size=1, max_row_size=4,
            popularity_exponent=1.4, seed=23, mixing_swaps_per_edge=5,
        )
        second = make_heterogeneous_dataset(
            rows=36, items=8, min_row_size=1, max_row_size=4,
            popularity_exponent=1.4, seed=23, mixing_swaps_per_edge=5,
        )
        self.assertEqual(first, second)
        row_degrees = [len(row) for row in first]
        item_degrees = Counter(item for row in first for item in row)
        self.assertGreater(len(set(row_degrees)), 1)
        self.assertEqual(len(item_degrees), 8)
        self.assertGreater(max(item_degrees.values()), min(item_degrees.values()))

    def test_generator_preserves_each_row_size_after_mixing(self):
        rows = make_heterogeneous_dataset(
            rows=40, items=9, min_row_size=2, max_row_size=5,
            seed=7, mixing_swaps_per_edge=8,
        )
        self.assertEqual(len(rows), 40)
        self.assertTrue(all(2 <= len(row) <= 5 for row in rows))

    def test_sensitivity_grid_is_reproducible_and_complete(self):
        kwargs = dict(
            dataset_seeds=2, chains=2, samples_per_chain=8,
            burn_in_grid=(0, 2), thinning_grid=(1, 3), seed_start=90,
        )
        first = run_mixing_sensitivity(**kwargs)
        second = run_mixing_sensitivity(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(len(first["configurations"]), 4)
        for row in first["configurations"]:
            self.assertGreaterEqual(row["mean_ess_fraction"], 0.0)
            self.assertLessEqual(row["mean_ess_fraction"], 1.0)
            self.assertGreaterEqual(row["mean_acceptance_rate"], 0.0)
            self.assertLessEqual(row["mean_acceptance_rate"], 1.0)

    def test_gini_bounds_and_uniformity(self):
        self.assertEqual(_gini([4, 4, 4]), 0.0)
        self.assertGreater(_gini([1, 2, 8]), 0.0)
        self.assertGreaterEqual(_gini([1, 2, 8]), 0.0)
        self.assertLess(_gini([1, 2, 8]), 1.0)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            make_heterogeneous_dataset(rows=5, items=6)
        with self.assertRaises(ValueError):
            make_heterogeneous_dataset(min_row_size=0)
        with self.assertRaises(ValueError):
            make_heterogeneous_dataset(popularity_exponent=-1)
        with self.assertRaises(ValueError):
            run_mixing_sensitivity(burn_in_grid=())


if __name__ == "__main__":
    unittest.main()
