import unittest

from prototype.e02_ternary_learners import (
    accuracy, feature_vector, fit, make_dataset, run_seed,
)


class E02TernaryLearnerTests(unittest.TestCase):
    def test_feature_dimensions(self):
        self.assertEqual(len(feature_vector((0, 1, 2), 2)), 36)
        self.assertEqual(len(feature_vector((0, 1, 2), 3)), 63)

    def test_role_features_are_one_hot(self):
        x = feature_vector((2, 1, 0), 3)
        self.assertEqual(sum(x[0:3]), 1.0)
        self.assertEqual(sum(x[3:6]), 1.0)
        self.assertEqual(sum(x[6:9]), 1.0)
        self.assertEqual(sum(x[9:18]), 1.0)
        self.assertEqual(sum(x[18:27]), 1.0)
        self.assertEqual(sum(x[27:36]), 1.0)
        self.assertEqual(sum(x[36:63]), 1.0)

    def test_training_rejects_empty_data(self):
        with self.assertRaises(ValueError):
            fit([], 2)

    def test_accuracy_rejects_empty_data(self):
        with self.assertRaises(ValueError):
            accuracy([], [0.0] * 36, 2)

    def test_seeded_experiment_reports_comparable_models(self):
        result = run_seed(7, 90, 36, 36)
        self.assertEqual(result["pairwise_parameters"], 36)
        self.assertEqual(result["third_order_parameters"], 63)
        for key in ("pairwise_test_accuracy", "third_order_test_accuracy",
                    "gated_test_accuracy"):
            self.assertGreaterEqual(result[key], 0.0)
            self.assertLessEqual(result[key], 1.0)


if __name__ == "__main__":
    unittest.main()
