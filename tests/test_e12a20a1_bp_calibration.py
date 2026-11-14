import unittest

from prototype.e12a20a1_bp_calibration import evaluate, run_calibration


class BeliefPropagationCalibrationTests(unittest.TestCase):
    def test_tree_marginals_match_exact_oracle_across_seeds(self):
        report = run_calibration((3, 7, 11), variable_count=5)
        self.assertEqual(report["tree"]["converged"], 3)
        self.assertLess(report["tree"]["max_abs_error"], 1e-9)

    def test_cycle_metrics_are_reported_without_claiming_exactness(self):
        result = evaluate(19, variable_count=5, cycle=True)
        self.assertEqual(result["topology"], "cycle")
        self.assertIn(result["status"], ("CONVERGED", "ITERATION_LIMIT", "BUDGET_EXHAUSTED", "INCONSISTENT_MESSAGES"))
        self.assertIsNotNone(result["max_marginal_abs_error"])
        self.assertGreaterEqual(result["max_marginal_abs_error"], 0.0)

    def test_calibration_is_deterministic(self):
        first = run_calibration((5, 9), variable_count=4)
        second = run_calibration((5, 9), variable_count=4)
        self.assertEqual(first, second)

    def test_duplicate_seeds_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            run_calibration((1, 1), variable_count=3)


if __name__ == "__main__":
    unittest.main()
