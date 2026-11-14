import unittest

from prototype.yixiang_experiments_m55 import (
    METHODS, SCENARIOS, generate_scenario, run_paired_suite,
)


class M55PairedExperimentTests(unittest.TestCase):
    def test_generators_are_deterministic_and_truth_is_explicit(self):
        for scenario in SCENARIOS:
            first = generate_scenario(scenario, n=100, seed=71)
            second = generate_scenario(scenario, n=100, seed=71)
            self.assertEqual(first, second)
            rows, parents = first
            self.assertEqual(len(rows), 100)
            self.assertIn(parents, ((), ("x",)))

    def test_suite_emits_complete_paired_method_cells(self):
        records = run_paired_suite(seeds=(3, 7), n=100,
                                   scenarios=("linear_gaussian", "latent_common_cause"))
        self.assertEqual(len(records), 2 * 2 * len(METHODS))
        for scenario in ("linear_gaussian", "latent_common_cause"):
            for seed in (3, 7):
                methods = {row["method"] for row in records
                           if row["scenario"] == scenario and row["seed"] == seed}
                self.assertEqual(methods, set(METHODS))
        self.assertTrue(all(not row["budget_violation"] for row in records))
        self.assertTrue(all(not row["invalid_proposal"] for row in records))

    def test_rejects_unknown_scenario_and_small_sample(self):
        with self.assertRaisesRegex(ValueError, "unknown_scenario"):
            generate_scenario("invented", n=100)
        with self.assertRaisesRegex(ValueError, "n_must_be_integer_at_least_80"):
            generate_scenario("linear_gaussian", n=20)


if __name__ == "__main__":
    unittest.main()
