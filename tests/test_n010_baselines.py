import copy
import unittest

from prototype.n09_learnable_srok import Node, RelationClassificationExample
from prototype.n010_baselines import (
    BaselineConfig, ParameterMatchedLowRankTensor, ParameterMatchedMLP,
    low_rank_tensor_parameter_count, match_mlp_hidden_dim, match_tensor_rank,
    mlp_parameter_count, xiang_parameter_count,
)


class N010BaselineTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        for a in (-1, 1):
            for b in (-1, 1):
                for c in (-1, 1):
                    nodes = tuple(
                        Node(f"{role}-{a}-{b}-{c}", role, (float(sign), float(index + 1)),
                             frozenset({"candidate"}))
                        for index, (role, sign) in enumerate(zip(("r0", "r1", "r2"), (a, b, c)))
                    )
                    self.rows.append(RelationClassificationExample(
                        nodes, 1 if a * b * c == 1 else -1
                    ))

    def test_parameter_matching_within_five_percent(self):
        target = xiang_parameter_count(3, 4, 8)
        self.assertEqual(target, 96)
        hidden = match_mlp_hidden_dim(3, 4, target, tolerance=0.05)
        rank = match_tensor_rank(3, 4, target, tolerance=0.05)
        self.assertEqual(hidden, 7)
        self.assertEqual(rank, 8)
        self.assertEqual(mlp_parameter_count(3, 4, hidden), 99)
        self.assertEqual(low_rank_tensor_parameter_count(3, 4, rank), 97)

    def test_mlp_training_is_deterministic_and_finite(self):
        left = ParameterMatchedMLP(3, 2, 4, BaselineConfig(13))
        right = ParameterMatchedMLP(3, 2, 4, BaselineConfig(13))
        left.fit(self.rows, epochs=4, learning_rate=0.05)
        right.fit(self.rows, epochs=4, learning_rate=0.05)
        self.assertEqual(left.weights, right.weights)
        self.assertEqual(left.readout, right.readout)
        self.assertEqual(left.training_steps, 4)
        self.assertTrue(all(0.0 < left.predict_probability(row.assignment) < 1.0
                            for row in self.rows))

    def test_tensor_training_is_deterministic_and_finite(self):
        left = ParameterMatchedLowRankTensor(3, 2, 4, BaselineConfig(19))
        right = ParameterMatchedLowRankTensor(3, 2, 4, BaselineConfig(19))
        left.fit(self.rows, epochs=4, learning_rate=0.02)
        right.fit(self.rows, epochs=4, learning_rate=0.02)
        self.assertEqual(left.factors, right.factors)
        self.assertEqual(left.coefficients, right.coefficients)
        self.assertEqual(left.training_steps, 4)
        self.assertTrue(all(0.0 < left.predict_probability(row.assignment) < 1.0
                            for row in self.rows))

    def test_epoch_training_matches_sequential_updates(self):
        for cls, args in (
            (ParameterMatchedMLP, (3, 2, 4, BaselineConfig(23))),
            (ParameterMatchedLowRankTensor, (3, 2, 4, BaselineConfig(23))),
        ):
            together, sequential = cls(*args), cls(*args)
            together.fit(self.rows, epochs=2, learning_rate=0.03)
            sequential.fit(self.rows, epochs=1, learning_rate=0.03)
            sequential.fit(self.rows, epochs=1, learning_rate=0.03)
            if cls is ParameterMatchedMLP:
                self.assertEqual(together.weights, sequential.weights)
                self.assertEqual(together.readout, sequential.readout)
            else:
                self.assertEqual(together.factors, sequential.factors)
                self.assertEqual(together.coefficients, sequential.coefficients)

    def test_invalid_parameter_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            xiang_parameter_count(0, 4, 8)
        with self.assertRaises(ValueError):
            match_mlp_hidden_dim(3, 4, 96, tolerance=-0.1)


if __name__ == "__main__":
    unittest.main()
