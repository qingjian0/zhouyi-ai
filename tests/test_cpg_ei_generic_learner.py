import itertools
import unittest

from prototype.cpg_ei_generic_learner import (
    RelationalTransitionModel, TransitionExample, encode_relations,
    evaluate, relation_supports,
)


class GenericRelationalLearnerTests(unittest.TestCase):
    def test_support_count_scales_with_dimension_and_arity(self):
        self.assertEqual(len(relation_supports(8, 1, 6)), 246)
        self.assertEqual(len(relation_supports(8, 2, 6)), 238)

    def test_encoding_contains_high_order_interactions(self):
        supports = relation_supports(4, 1, 4)
        encoded = encode_relations((1, 1, 1, 1), supports)
        self.assertEqual(len(encoded), 16)
        self.assertEqual(encoded[0], 1.0)
        self.assertEqual(encoded[-1], 1.0)

    def test_rejects_dimension_mismatch(self):
        model = RelationalTransitionModel.create(8, 8, 1, 6)
        with self.assertRaises(ValueError):
            model.predict((0, 1, 0, 1, 0, 1))
        with self.assertRaises(ValueError):
            model.train([TransitionExample((0,) * 8, (1,) * 6)])

    def test_learns_four_input_parity_and_evaluates(self):
        support = (0, 1, 2, 3)
        rows = [
            TransitionExample(state, (sum(state[i] for i in support) % 2,))
            for state in itertools.product((0, 1), repeat=4)
        ]
        model = RelationalTransitionModel.create(4, 1, 1, 4)
        losses = model.train(rows, epochs=1200, learning_rate=0.25, l2=1e-6)
        metrics = evaluate(model, rows)
        self.assertLess(losses[-1], losses[0])
        self.assertEqual(metrics["exact_state_accuracy"], 1.0)

    def test_eight_by_eight_model_contract(self):
        model = RelationalTransitionModel.create(8, 8, 1, 6)
        self.assertEqual(model.input_dim, 8)
        self.assertEqual(model.output_dim, 8)
        self.assertEqual(len(model.weights), 8)
        self.assertEqual(len(model.weights[0]), 247)


if __name__ == "__main__":
    unittest.main()
