import unittest

from prototype.n09_learnable_srok import LearnableSROK, LearnableSROKError, RoleSpec
from prototype.n10_higher_order_benchmark import evaluate, make_dataset


class HigherOrderNecessaryBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.roles = tuple(
            RoleSpec(name, frozenset({name}))
            for name in ("r0", "r1", "r2")
        )

    def test_data_is_reproducible_and_balanced(self):
        first = make_dataset(104, 31)
        second = make_dataset(104, 31)
        self.assertEqual(first, second)
        self.assertGreater(sum(row.label for row in first), 30)
        self.assertLess(sum(row.label for row in first), 70)

    def test_third_order_learns_parity_while_pairwise_stays_at_chance(self):
        train = make_dataset(1200, 41)
        test = make_dataset(600, 42)
        results = {}
        models = {}
        for order in (1, 2, 3):
            model = LearnableSROK(self.roles, feature_dim=1)
            history = model.fit_binary(
                train, max_order=order, epochs=120,
                learning_rate=0.15, l2=1e-3,
            )
            if order == 3:
                self.assertLess(history[-1], history[0])
            else:
                self.assertAlmostEqual(history[-1], history[0], places=8)
            models[order] = model
            results[order] = evaluate(model, test, order)["accuracy"]

        self.assertGreater(results[3], 0.95)
        self.assertGreaterEqual(results[1], 0.40)
        self.assertLessEqual(results[1], 0.60)
        self.assertGreaterEqual(results[2], 0.40)
        self.assertLessEqual(results[2], 0.60)

    def test_masking_triple_block_removes_high_order_advantage(self):
        train = make_dataset(1200, 51)
        test = make_dataset(600, 52)
        model = LearnableSROK(self.roles, feature_dim=1)
        model.fit_binary(train, max_order=3, epochs=120)
        full = evaluate(model, test, 3)["accuracy"]
        masked = evaluate(model, test, 2)["accuracy"]
        self.assertGreater(full, 0.95)
        self.assertGreaterEqual(masked, 0.40)
        self.assertLessEqual(masked, 0.60)

    def test_invalid_order_and_label_are_rejected(self):
        model = LearnableSROK(self.roles, feature_dim=1)
        row = make_dataset(8, 61)[0]
        with self.assertRaises(LearnableSROKError):
            model.fit_binary([row], max_order=2.0, epochs=1)
        bad = type(row)(assignment=row.assignment, label=1.0)
        with self.assertRaises(LearnableSROKError):
            model.fit_binary([bad], epochs=1)


if __name__ == "__main__":
    unittest.main()
