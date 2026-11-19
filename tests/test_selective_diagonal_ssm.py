import unittest

from prototype.selective_diagonal_ssm import SelectiveDiagonalSSM


class SelectiveDiagonalSSMTests(unittest.TestCase):
    def test_parameter_count_matches_existing_29_parameter_baselines(self):
        self.assertEqual(SelectiveDiagonalSSM(hidden_size=7).parameter_count, 29)

    def test_chunked_state_matches_whole_sequence(self):
        model = SelectiveDiagonalSSM(hidden_size=7, seed=31)
        symbols = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0]
        whole, whole_state = model.predict_chunk(symbols)
        state = None
        chunked = []
        for part in (symbols[:1], symbols[1:5], symbols[5:8], symbols[8:]):
            output, state = model.predict_chunk(part, state)
            chunked.extend(output)
        self.assertEqual(len(whole), len(chunked))
        for left, right in zip(whole, chunked):
            self.assertAlmostEqual(left, right, places=14)
        for left, right in zip(whole_state.hidden, state.hidden):
            self.assertAlmostEqual(left, right, places=14)

    def test_final_target_training_updates_all_parameter_groups(self):
        model = SelectiveDiagonalSSM(hidden_size=3, seed=5)
        before = {
            name: tuple(getattr(model, name))
            for name in ("a_log", "delta_bias", "input_weight", "output_weight")
        }
        model.train_final_target([1, 0, 1, 1, 0, 1], 1)
        for name, values in before.items():
            self.assertNotEqual(values, tuple(getattr(model, name)), name)

    def test_finite_difference_gradient_for_selective_rate(self):
        model = SelectiveDiagonalSSM(hidden_size=2, seed=13)
        context, target = [1, 0, 1, 1], 0
        parameter_index = 0
        original = model.a_log[parameter_index]
        epsilon = 1e-6

        def loss_at(value):
            model.a_log[parameter_index] = value
            hidden = [0.0] * model.hidden_size
            for symbol in context:
                hidden, _, _, _, _ = model._step(float(symbol), hidden)
            probability = 1.0 / (1.0 + __import__("math").exp(-(
                model.output_bias + sum(a * b for a, b in zip(model.output_weight, hidden))
            )))
            p = min(max(probability, 1e-12), 1 - 1e-12)
            return -target * __import__("math").log(p) - (1-target) * __import__("math").log(1-p)

        numeric = (loss_at(original + epsilon) - loss_at(original - epsilon)) / (2 * epsilon)
        loss_at(original)
        # Recover analytic gradient via one tiny SGD step (before clipping is inactive).
        lr = 1e-7
        model.train_final_target(context, target, learning_rate=lr, clip_norm=1e9)
        analytic = (original - model.a_log[parameter_index]) / lr
        self.assertAlmostEqual(analytic, numeric, delta=2e-5)

    def test_rejects_invalid_symbols_and_state(self):
        model = SelectiveDiagonalSSM(hidden_size=2)
        with self.assertRaises(ValueError):
            model.predict_chunk([0, 2])
        with self.assertRaises(ValueError):
            model.predict_chunk([1], type("State", (), {"hidden": [float("nan"), 0.0]})())


if __name__ == "__main__":
    unittest.main()
