import unittest

from prototype.cpg_ei_mvp import (
    CpgEiTransitionModel,
    FEATURE_NAMES,
    encode_state,
    evaluate,
    make_dataset,
)


class TestCpgEiMvp(unittest.TestCase):
    def test_encoding_contains_pair_and_triple_hyperedges(self):
        self.assertEqual(len(FEATURE_NAMES), 42)
        self.assertEqual(len(encode_state((1, 0, 1, 0, 1, 0))), 42)
        with self.assertRaises(ValueError):
            encode_state((1, 0, 2, 0, 1, 0))

    def test_training_reduces_loss_and_generalizes_on_seeded_task(self):
        train = make_dataset(1024, seed=7)
        test = make_dataset(256, seed=8)
        model = CpgEiTransitionModel.create()
        losses = model.train(train, epochs=120)
        metrics = evaluate(model, test)
        self.assertLess(losses[-1], losses[0])
        self.assertGreater(metrics["bit_accuracy"], 0.85)

    def test_dataset_is_reproducible(self):
        self.assertEqual(make_dataset(10, seed=11), make_dataset(10, seed=11))


if __name__ == "__main__":
    unittest.main()
