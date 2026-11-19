"""Finite-difference checks for the manual recurrent-model BPTT updates."""
import math
import unittest

from prototype.diagonal_gated_rnn import DiagonalGatedRNN
from prototype.diagonal_linear_rnn import DiagonalLinearRNN


def mean_next_symbol_loss(model, symbols):
    probabilities, _ = model.predict_chunk(symbols[:-1])
    total = 0.0
    for probability, target in zip(probabilities, symbols[1:]):
        p = min(max(probability, 1e-12), 1.0 - 1e-12)
        total -= target * math.log(p) + (1 - target) * math.log(1 - p)
    return total / len(probabilities)


class RecurrentBPTTGradientTests(unittest.TestCase):
    def _check_model(self, factory, parameter_names, symbols):
        learning_rate = 1e-7
        epsilon = 1e-6
        baseline = factory()
        original = {
            name: list(getattr(baseline, name)) if isinstance(getattr(baseline, name), list)
            else getattr(baseline, name)
            for name in parameter_names
        }
        before_loss = mean_next_symbol_loss(baseline, symbols)
        baseline.train_sequence(symbols, learning_rate=learning_rate, clip_norm=1e12)
        steps = len(symbols) - 1
        checked = 0
        for name in parameter_names:
            values = original[name]
            indices = range(len(values)) if isinstance(values, list) else (None,)
            for index in indices:
                plus, minus = factory(), factory()
                if index is None:
                    setattr(plus, name, original[name] + epsilon)
                    setattr(minus, name, original[name] - epsilon)
                else:
                    getattr(plus, name)[index] = original[name][index] + epsilon
                    getattr(minus, name)[index] = original[name][index] - epsilon
                numeric = (
                    mean_next_symbol_loss(plus, symbols)
                    - mean_next_symbol_loss(minus, symbols)
                ) / (2 * epsilon)
                updated = getattr(baseline, name)
                updated_value = updated if index is None else updated[index]
                original_value = original[name] if index is None else original[name][index]
                analytic = (original_value - updated_value) / (learning_rate * steps)
                self.assertAlmostEqual(analytic, numeric, delta=2e-5,
                                       msg=f"{name}[{index}] gradient mismatch")
                checked += 1
        self.assertGreater(checked, 0)
        self.assertTrue(math.isfinite(before_loss))

    def test_gated_rnn_manual_bptt_matches_finite_differences(self):
        self._check_model(
            lambda: DiagonalGatedRNN(hidden_size=2, seed=31),
            ("wx", "wh", "b", "ux", "uh", "c", "v", "d"),
            [0, 1, 1, 0, 1, 0],
        )

    def test_linear_rnn_manual_bptt_matches_finite_differences(self):
        self._check_model(
            lambda: DiagonalLinearRNN(hidden_size=2, seed=37),
            ("raw_recurrence", "input_weight", "bias", "output_weight", "output_bias"),
            [0, 1, 1, 0, 1, 0],
        )

    def _check_final_target(self, factory, parameter_names, context, target):
        learning_rate = 1e-7
        epsilon = 1e-6
        baseline = factory()
        original = {
            name: list(getattr(baseline, name)) if isinstance(getattr(baseline, name), list)
            else getattr(baseline, name)
            for name in parameter_names
        }
        baseline.train_final_target(context, target, learning_rate=learning_rate, clip_norm=1e12)
        for name in parameter_names:
            values = original[name]
            indices = range(len(values)) if isinstance(values, list) else (None,)
            for index in indices:
                plus, minus = factory(), factory()
                if index is None:
                    setattr(plus, name, original[name] + epsilon)
                    setattr(minus, name, original[name] - epsilon)
                else:
                    getattr(plus, name)[index] = original[name][index] + epsilon
                    getattr(minus, name)[index] = original[name][index] - epsilon
                def loss(model):
                    probabilities, _ = model.predict_chunk(context)
                    p = min(max(probabilities[-1], 1e-12), 1.0 - 1e-12)
                    return -target * math.log(p) - (1 - target) * math.log(1 - p)
                numeric = (loss(plus) - loss(minus)) / (2 * epsilon)
                updated = getattr(baseline, name)
                updated_value = updated if index is None else updated[index]
                original_value = original[name] if index is None else original[name][index]
                analytic = (original_value - updated_value) / learning_rate
                self.assertAlmostEqual(analytic, numeric, delta=2e-5,
                                       msg=f"final-target {name}[{index}] gradient mismatch")

    def test_gated_final_target_bptt_matches_finite_differences(self):
        self._check_final_target(
            lambda: DiagonalGatedRNN(hidden_size=2, seed=41),
            ("wx", "wh", "b", "ux", "uh", "c", "v", "d"),
            [1, 0, 1, 1, 0], 1,
        )

    def test_linear_final_target_bptt_matches_finite_differences(self):
        self._check_final_target(
            lambda: DiagonalLinearRNN(hidden_size=2, seed=43),
            ("raw_recurrence", "input_weight", "bias", "output_weight", "output_bias"),
            [1, 0, 1, 1, 0], 1,
        )


if __name__ == "__main__":
    unittest.main()
