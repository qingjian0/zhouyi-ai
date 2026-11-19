import unittest

from prototype.diagonal_gated_rnn import DiagonalGatedRNN


class DiagonalGatedRNNTests(unittest.TestCase):
    def test_chunked_inference_matches_single_pass(self):
        model = DiagonalGatedRNN(hidden_size=5, seed=2)
        sequence = [0, 1, 1, 0, 1, 0]
        full, full_state = model.predict_chunk(sequence)
        first, state = model.predict_chunk(sequence[:3])
        second, chunk_state = model.predict_chunk(sequence[3:], state)
        self.assertEqual(full, first + second)
        self.assertEqual(full_state.hidden, chunk_state.hidden)

    def test_training_updates_parameters_and_returns_finite_loss(self):
        model = DiagonalGatedRNN(hidden_size=4, seed=3)
        before = list(model.wx)
        sequence = [0, 1] * 12
        losses = [model.train_sequence(sequence) for _ in range(25)]
        self.assertNotEqual(before, model.wx)
        self.assertTrue(all(loss >= 0 for loss in losses))
        self.assertLess(losses[-1], losses[0])

    def test_fit_reports_updates(self):
        model = DiagonalGatedRNN(hidden_size=3)
        metrics = model.fit([[0, 1] * 5, [1, 0] * 5], epochs=2)
        self.assertEqual(metrics.examples, 2)
        self.assertEqual(metrics.updates, 4)
        self.assertGreaterEqual(metrics.mean_loss, 0)

    def test_rejects_invalid_inputs(self):
        model = DiagonalGatedRNN()
        with self.assertRaises(ValueError):
            model.predict_chunk([0, 2])
        with self.assertRaises(ValueError):
            model.train_sequence([0])
        with self.assertRaises(ValueError):
            DiagonalGatedRNN(hidden_size=0)


if __name__ == "__main__":
    unittest.main()
