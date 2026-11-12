import math
import unittest

from prototype.cpg_ei_mvp import (
    CpgEiTransitionModel,
    Example,
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
        print(
            f"CPGEI_SPARSE_SUPPORT bit_accuracy={metrics['bit_accuracy']:.6f} "
            f"active_relation_groups={active_groups}/35"
        )
        self.assertLess(losses[-1], losses[0])
        self.assertGreater(metrics["bit_accuracy"], 0.90)
        self.assertLess(active_groups, 20)


    def test_output_weight_gradient_matches_mean_bce_objective(self):
        examples = [
            Example((1, 1, 0, 0, 0, 0), (1, 0, 1, 0, 1, 0)),
            Example((0, 1, 1, 0, 0, 0), (0, 1, 0, 1, 0, 1)),
        ]
        model = CpgEiTransitionModel.create(active_relation_indices={7})
        model.weights[0][7] = 0.3
        epsilon = 1e-5
        learning_rate = 1e-6

        def objective():
            total = 0.0
            for row in examples:
                for probability, label in zip(
                    model.predict_proba(row.state), row.target
                ):
                    p = min(max(probability, 1e-12), 1.0 - 1e-12)
                    total += -(label * math.log(p) + (1 - label) * math.log(1 - p))
            return total / (len(examples) * 6.0)

        original = model.weights[0][7]
        model.weights[0][7] = original + epsilon
        plus = objective()
        model.weights[0][7] = original - epsilon
        minus = objective()
        model.weights[0][7] = original
        expected_gradient = (plus - minus) / (2.0 * epsilon)

        model.train(
            examples, epochs=1, learning_rate=learning_rate,
            l2=0.0, gate_l1=0.0, edge_group_l1=0.0,
        )
        observed_gradient = (original - model.weights[0][7]) / learning_rate
        self.assertAlmostEqual(observed_gradient, expected_gradient, delta=2e-5)

    def test_shared_gate_gradient_matches_mean_bce_objective(self):
        examples = [
            Example((1, 1, 0, 0, 0, 0), (1, 0, 1, 0, 1, 0)),
            Example((0, 1, 1, 0, 0, 0), (0, 1, 0, 1, 0, 1)),
        ]
        model = CpgEiTransitionModel.create(active_relation_indices={7})
        model.gate_logits[0] = -0.4
        for head in range(6):
            model.weights[head][7] = 0.15 * (head + 1)
        epsilon = 1e-5
        learning_rate = 1e-6

        def objective():
            total = 0.0
            for row in examples:
                for probability, label in zip(
                    model.predict_proba(row.state), row.target
                ):
                    p = min(max(probability, 1e-12), 1.0 - 1e-12)
                    total += -(label * math.log(p) + (1 - label) * math.log(1 - p))
            gate_sum = sum(model.relation_gate_probabilities())
            return total / (len(examples) * 6.0) + 0.03 * gate_sum / 6.0

        original = model.gate_logits[0]
        model.gate_logits[0] = original + epsilon
        plus = objective()
        model.gate_logits[0] = original - epsilon
        minus = objective()
        model.gate_logits[0] = original
        expected_gradient = (plus - minus) / (2.0 * epsilon)

        model.train(examples, epochs=1, learning_rate=learning_rate,
                    l2=0.0, gate_l1=0.03, edge_group_l1=0.0)
        observed_gradient = (original - model.gate_logits[0]) / learning_rate
        self.assertAlmostEqual(observed_gradient, expected_gradient, delta=2e-5)

    def test_dataset_is_reproducible(self):
        self.assertEqual(make_dataset(10, seed=11), make_dataset(10, seed=11))


if __name__ == "__main__":
    unittest.main()
