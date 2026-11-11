import unittest

from orchestrator.agents.experiment_statistics import SeedMetric, compare_paired


class PairedStatisticsTests(unittest.TestCase):
    def test_paired_comparison_is_deterministic(self):
        baseline = [SeedMetric(1, 0.70), SeedMetric(2, 0.72), SeedMetric(3, 0.68)]
        candidate = [SeedMetric(1, 0.75), SeedMetric(2, 0.73), SeedMetric(3, 0.74)]
        first = compare_paired("accuracy", baseline, candidate, bootstrap_samples=1000,
                               bootstrap_seed=42)
        second = compare_paired("accuracy", baseline, candidate, bootstrap_samples=1000,
                                bootstrap_seed=42)
        self.assertEqual(first, second)
        self.assertAlmostEqual(first.mean_difference, 0.04)
        self.assertAlmostEqual(first.improvement_rate, 1.0)
        self.assertEqual(first.sample_count, 3)
        self.assertLessEqual(first.bootstrap_ci_low, first.bootstrap_ci_high)

    def test_lower_is_better_reverses_difference_sign(self):
        result = compare_paired(
            "latency_ms",
            [SeedMetric(1, 20), SeedMetric(2, 18)],
            [SeedMetric(1, 15), SeedMetric(2, 17)],
            direction="lower", bootstrap_samples=200,
        )
        self.assertAlmostEqual(result.mean_difference, 3.0)
        self.assertEqual(result.improvement_rate, 1.0)

    def test_constant_difference_has_undefined_standardized_effect(self):
        result = compare_paired(
            "score", [SeedMetric(1, 1), SeedMetric(2, 2)],
            [SeedMetric(1, 2), SeedMetric(2, 3)], bootstrap_samples=200,
        )
        self.assertIsNone(result.paired_cohens_dz)

    def test_mismatched_seed_sets_rejected(self):
        with self.assertRaisesRegex(ValueError, "match exactly"):
            compare_paired("score", [SeedMetric(1, 1), SeedMetric(2, 2)],
                           [SeedMetric(1, 2), SeedMetric(3, 3)])

    def test_duplicate_seed_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare_paired("score", [SeedMetric(1, 1), SeedMetric(1, 2)],
                           [SeedMetric(1, 2), SeedMetric(1, 3)])

    def test_invalid_values_and_configuration_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            SeedMetric(1, float("nan"))
        with self.assertRaisesRegex(ValueError, "direction"):
            compare_paired("score", [SeedMetric(1, 1), SeedMetric(2, 2)],
                           [SeedMetric(1, 2), SeedMetric(2, 3)], direction="best")
        with self.assertRaisesRegex(ValueError, ">= 100"):
            compare_paired("score", [SeedMetric(1, 1), SeedMetric(2, 2)],
                           [SeedMetric(1, 2), SeedMetric(2, 3)], bootstrap_samples=10)


if __name__ == "__main__":
    unittest.main()
