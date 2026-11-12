import math
import unittest

from prototype.n14_learnable_cyclic_operator import (
    evaluate_operator,
    fit_operator,
    run_seed,
    tensor_features,
)


class N14LearnableCyclicOperatorTests(unittest.TestCase):
    def test_analytic_frequency_derivative_matches_finite_difference(self):
        angles = (0.41, 1.23, 2.17)
        omega = 0.93
        features, derivatives = tensor_features(angles, omega)
        epsilon = 1e-6
        plus, _ = tensor_features(angles, omega + epsilon)
        minus, _ = tensor_features(angles, omega - epsilon)
        for index in range(4):
            numerical = (plus[index] - minus[index]) / (2.0 * epsilon)
            self.assertAlmostEqual(derivatives[index], numerical, places=7)
        self.assertEqual(len(features), 4)

    def test_fit_is_deterministic(self):
        rows = [
            ((0.2, 0.4, 0.6), 1),
            ((1.4, 2.1, 0.3), 0),
            ((2.4, 0.7, 1.8), 0),
            ((4.2, 2.3, 5.1), 1),
        ]
        self.assertEqual(
            fit_operator(rows, epochs=5),
            fit_operator(rows, epochs=5),
        )

    def test_invalid_frequency_and_empty_training_data_are_rejected(self):
        with self.assertRaises(ValueError):
            tensor_features((0.1, 0.2, 0.3), 0.0)
        with self.assertRaises(ValueError):
            fit_operator([], epochs=2)

    def test_learnable_frequency_transfers_to_held_out_region(self):
        result = run_seed(
            7, train_count=1200, validation_count=300,
            test_count=600, epochs=120,
        )
        self.assertEqual(result["operator"]["parameter_count"], 6)
        self.assertGreater(result["operator"]["test"]["accuracy"], 0.95)
        self.assertAlmostEqual(
            result["operator"]["learned_omega"], 1.0, delta=0.05
        )
        self.assertEqual(result["srok"]["parameter_count"], 35)

    def test_operator_evaluation_reports_metrics(self):
        rows = [((0.2, 0.3, 0.4), 1), ((2.0, 1.0, 0.4), 0)]
        parameters = fit_operator(rows, epochs=2)
        result = evaluate_operator(parameters, rows)
        self.assertIn("accuracy", result)
        self.assertIn("balanced_accuracy", result)
        self.assertIn("mean_bce", result)


if __name__ == "__main__":
    unittest.main()
