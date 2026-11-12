import unittest

from prototype.n12_parameter_matched_baselines import (
    evaluate_mlp,
    fit_mlp,
    run_seed,
)


class N12ParameterMatchedBaselineTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            ((1.0, 0.0, 1.0, 0.0, 1.0, 0.0), 1),
            ((0.0, 1.0, 1.0, 0.0, 0.0, 1.0), 0),
            ((-1.0, 0.0, 0.0, -1.0, 1.0, 0.0), 0),
            ((0.0, -1.0, 0.0, 1.0, -1.0, 0.0), 1),
        ]

    def test_parameter_counts_bracket_srok_budget(self):
        for hidden, expected in ((4, 33), (5, 41), (12, 97)):
            params = fit_mlp(self.rows, hidden=hidden, seed=7, epochs=2)
            self.assertEqual(len(params), expected)

    def test_fit_is_deterministic_for_fixed_seed(self):
        first = fit_mlp(self.rows, hidden=4, seed=19, epochs=3)
        second = fit_mlp(self.rows, hidden=4, seed=19, epochs=3)
        self.assertEqual(first, second)

    def test_invalid_hidden_size_and_empty_data_are_rejected(self):
        with self.assertRaises(ValueError):
            fit_mlp(self.rows, hidden=0, seed=1)
        with self.assertRaises(ValueError):
            fit_mlp([], hidden=4, seed=1)

    def test_evaluation_reports_balanced_metrics(self):
        params = fit_mlp(self.rows, hidden=4, seed=7, epochs=3)
        result = evaluate_mlp(params, self.rows, hidden=4)
        self.assertIn("accuracy", result)
        self.assertIn("balanced_accuracy", result)
        self.assertIn("mean_bce", result)

    def test_seed_run_reports_srok_and_all_mlp_budgets(self):
        result = run_seed(
            7, train_count=120, validation_count=60,
            test_count=60, epochs=2,
        )
        self.assertEqual(result["srok"]["parameter_count"], 35)
        self.assertEqual(
            {key: value["parameter_count"] for key, value in result["mlp"].items()},
            {"4": 33, "5": 41, "12": 97},
        )
        self.assertIn("test", result["mlp"]["4"])


if __name__ == "__main__":
    unittest.main()
