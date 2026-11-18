import importlib.util
import itertools
import unittest

from prototype.cpg_ei_early_stopping import fit_with_early_stopping
from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample,
)
from prototype.cpg_ei_numpy_learner import fit_with_early_stopping_numpy


@unittest.skipUnless(importlib.util.find_spec("numpy"), "optional NumPy dependency not installed")
class TestNumpyRelationLearner(unittest.TestCase):
    def setUp(self):
        self.rows = [
            TransitionExample(
                state,
                (state[0] ^ state[1], state[0] & state[2]),
            )
            for state in itertools.product((0, 1), repeat=3)
        ]

    def test_one_epoch_matches_reference_python_gradient(self):
        supports = tuple(
            support
            for size in range(1, 4)
            for support in itertools.combinations(range(3), size)
        )
        reference = RelationalTransitionModel(
            3, 2, supports, [[0.0] * (len(supports) + 1) for _ in range(2)]
        )
        accelerated = RelationalTransitionModel(
            3, 2, supports, [[0.0] * (len(supports) + 1) for _ in range(2)]
        )
        reference.train(self.rows, epochs=1, learning_rate=0.1, l2=1e-4)
        fit = fit_with_early_stopping_numpy(
            accelerated, self.rows, self.rows,
            max_epochs=1, patience=1, min_delta=0.0,
            learning_rate=0.1, l2=1e-4,
        )
        self.assertEqual(fit["best_epoch"], 1)
        for left, right in zip(reference.weights, accelerated.weights):
            for a, b in zip(left, right):
                self.assertAlmostEqual(a, b, places=12)

    def test_numpy_and_python_early_stopping_match_predictions(self):
        supports = tuple(
            support
            for size in range(1, 4)
            for support in itertools.combinations(range(3), size)
        )
        python_model = RelationalTransitionModel(
            3, 2, supports, [[0.0] * (len(supports) + 1) for _ in range(2)]
        )
        numpy_model = RelationalTransitionModel(
            3, 2, supports, [[0.0] * (len(supports) + 1) for _ in range(2)]
        )
        python_fit = fit_with_early_stopping(
            python_model, self.rows[:6], self.rows[6:],
            max_epochs=40, patience=8, min_delta=1e-7,
            learning_rate=0.1, l2=1e-4,
        )
        numpy_fit = fit_with_early_stopping_numpy(
            numpy_model, self.rows[:6], self.rows[6:],
            max_epochs=40, patience=8, min_delta=1e-7,
            learning_rate=0.1, l2=1e-4,
        )
        self.assertEqual(python_fit["best_epoch"], numpy_fit["best_epoch"])
        self.assertEqual(
            [numpy_model.predict(row.state) for row in self.rows],
            [python_model.predict(row.state) for row in self.rows],
        )

    def test_feature_matrices_are_encoded_once_per_split(self):
        model = RelationalTransitionModel.create(3, 2, min_arity=1, max_arity=3)
        report = fit_with_early_stopping_numpy(
            model, self.rows[:6], self.rows[6:],
            max_epochs=3, patience=3,
        )
        self.assertEqual(report["training_feature_rows_encoded"], 6)
        self.assertEqual(report["development_feature_rows_encoded"], 2)
        self.assertEqual(report["optimizer_backend"], "numpy-float64-cached-full-batch")

    def test_invalid_optimizer_configuration_is_rejected(self):
        model = RelationalTransitionModel.create(3, 2, min_arity=1, max_arity=2)
        with self.assertRaises(ValueError):
            fit_with_early_stopping_numpy(
                model, self.rows[:6], self.rows[6:], max_epochs=0
            )


if __name__ == "__main__":
    unittest.main()
