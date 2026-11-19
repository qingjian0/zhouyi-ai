import unittest

from prototype.diagonal_linear_rnn import DiagonalLinearRNN


class DiagonalLinearRNNTests(unittest.TestCase):
    def test_chunked_inference_matches_single_pass(self):
        model = DiagonalLinearRNN(hidden_size=5, seed=2)
        sequence = [0, 1, 1, 0, 1, 0]
        full, full_state = model.predict_chunk(sequence)
        first, state = model.predict_chunk(sequence[:3])
        second, chunk_state = model.predict_chunk(sequence[3:], state)
        self.assertEqual(full, first + second)
        self.assertEqual(full_state.hidden, chunk_state.hidden)

    def test_training_updates_parameters_and_finite_loss(self):
        model = DiagonalLinearRNN(hidden_size=5, seed=3)
        before = list(model.input_weight)
        losses = [model.train_sequence([0, 1] * 12) for _ in range(20)]
        self.assertNotEqual(before, model.input_weight)
        self.assertTrue(all(loss >= 0 for loss in losses))

    def test_parameter_count_is_explicit(self):
        self.assertEqual(DiagonalLinearRNN(hidden_size=9).parameter_count, 37)

    def test_rejects_invalid_input(self):
        model = DiagonalLinearRNN()
        with self.assertRaises(ValueError):
            model.predict_chunk([0, 2])
        with self.assertRaises(ValueError):
            model.train_sequence([0])


if __name__ == "__main__":
    unittest.main()
