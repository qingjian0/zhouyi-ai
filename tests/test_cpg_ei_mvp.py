import math
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

    def test_relation_gates_are_trainable_and_bounded(self):
        train = make_dataset(1024, seed=17)
        model = CpgEiTransitionModel.create()
        before = model.relation_gate_probabilities()
        self.assertEqual(len(before), 35)
        model.train(train, epochs=80, gate_l1=1e-4)
        after = model.relation_gate_probabilities()
        self.assertEqual(len(after), 35)
        self.assertTrue(all(0.0 < value < 1.0 for value in after))
        self.assertTrue(any(abs(a - b) > 1e-8 for a, b in zip(before, after)))

    def test_group_sparse_training_recovers_sparse_relation_support(self):
        train = make_dataset(1024, seed=7, sparse_teacher=True)
        test = make_dataset(256, seed=8, sparse_teacher=True)
        model = CpgEiTransitionModel.create()
        losses = model.train(
            train, epochs=120, gate_l1=0.01, edge_group_l1=0.03
        )
        metrics = evaluate(model, test)
        active_groups = sum(
            math.sqrt(sum(model.weights[h][j] ** 2 for h in range(6))) > 1e-5
            for j in range(7, len(FEATURE_NAMES))
        )
        self.assertLess(losses[-1], losses[0])
        self.assertGreater(metrics["bit_accuracy"], 0.90)
        self.assertLess(active_groups, 20)

    def test_dataset_is_reproducible(self):
        self.assertEqual(make_dataset(10, seed=11), make_dataset(10, seed=11))


if __name__ == "__main__":
    unittest.main()
