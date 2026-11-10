import unittest

from prototype.e02_higher_order import (
    accuracy, features, make_dataset, run_seed,
)


class E02HigherOrderTests(unittest.TestCase):
    def test_feature_order(self):
        self.assertEqual(len(features((1, -1, 1), 2)), 7)
        self.assertEqual(len(features((1, -1, 1), 3)), 8)
        self.assertEqual(features((1, -1, 1), 3)[-1], -1.)

    def test_hard_negatives(self):
        for ex in make_dataset(40, 19):
            self.assertEqual(len(ex.candidates), 4)
            self.assertEqual(len(set(ex.candidates)), 4)
            self.assertEqual(
                ex.candidates[ex.target][0]
                * ex.candidates[ex.target][1]
                * ex.candidates[ex.target][2], 1)
            for i, x in enumerate(ex.candidates):
                if i != ex.target:
                    self.assertEqual(x[0] * x[1] * x[2], -1)

    def test_first_and_second_order_marginals_are_balanced(self):
        data = make_dataset(40, 23)
        positive = [features(ex.candidates[ex.target], 2) for ex in data]
        negative = [
            features(x, 2)
            for ex in data
            for i, x in enumerate(ex.candidates)
            if i != ex.target
        ]
        for j in range(1, 7):
            self.assertAlmostEqual(sum(x[j] for x in positive), 0.0)
            self.assertAlmostEqual(sum(x[j] for x in negative), 0.0)

    def test_data_seed_changes_query_target_pairings(self):
        a = make_dataset(40, 101)
        b = make_dataset(40, 202)
        self.assertNotEqual(a, b)

    def test_reproducible_for_same_data_seed(self):
        self.assertEqual(make_dataset(40, 77), make_dataset(40, 77))

    def test_requires_complete_balance_blocks(self):
        with self.assertRaises(ValueError):
            make_dataset(10, 1)

    def test_metrics_bounded(self):
        r = run_seed(7, 200, 60, 80)
        for k in ("pairwise_test_accuracy", "static_order3_test_accuracy",
                  "dynamic_test_accuracy"):
            self.assertGreaterEqual(r[k], 0.)
            self.assertLessEqual(r[k], 1.)

    def test_empty_accuracy_rejected(self):
        with self.assertRaises(ValueError):
            accuracy([], [0.] * 7, 2)


if __name__ == "__main__":
    unittest.main()
