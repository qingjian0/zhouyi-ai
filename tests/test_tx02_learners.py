import unittest

from prototype.tx02_learners import SetConditionedMLPLearner
from prototype.tx02_splits import make_rule_disjoint_splits


class TX02TrainableLearnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = make_rule_disjoint_splits(
            3, episodes_per_rule=1, support_size=4, query_count=2,
            seed=20261111, symbol_mappings=("canonical",),
        )

    def test_predict_returns_candidate_indices(self):
        learner = SetConditionedMLPLearner("ONE_HOT", hidden_size=8, seed=3)
        row = self.bundle.train[0]
        prediction = learner.predict(row.inputs)
        self.assertEqual(len(prediction), len(row.inputs.queries))
        for qi, index in enumerate(prediction):
            self.assertGreaterEqual(index, 0)
            self.assertLess(index, len(row.inputs.candidates[qi]))

    def test_learned_embedding_is_updated_by_training(self):
        learner = SetConditionedMLPLearner(
            "LEARNED", hidden_size=8, embedding_dim=4,
            learning_rate=0.02, seed=11,
        )
        learner._initialize(3)
        before = tuple(tuple(row) for row in learner._embeddings)
        report = learner.fit(self.bundle.train[:8], budget={"epochs": 2})
        after = tuple(tuple(row) for row in learner._embeddings)
        self.assertNotEqual(before, after)
        self.assertGreater(report.updates, 0)
        self.assertEqual(report.parameter_count, learner.parameter_count)
        self.assertTrue(learner.metadata()["trainable_embedding"])

    def test_fixed_representations_have_no_trainable_symbol_table(self):
        for family in ("BINARY", "TERNARY", "HYBRID", "ONE_HOT", "FIXED_RANDOM", "PERMUTED"):
            learner = SetConditionedMLPLearner(family, hidden_size=5, seed=7)
            learner.fit(self.bundle.train[:4], budget={"epochs": 1})
            self.assertFalse(learner.metadata()["trainable_embedding"])
            if family != "FIXED_RANDOM":\n                self.assertIsNone(learner.metadata()["embedding_dim"])

    def test_fixed_random_embedding_is_unchanged_by_training(self):
        learner = SetConditionedMLPLearner(
            "FIXED_RANDOM", hidden_size=8, embedding_dim=4, seed=17
        )
        learner._initialize(3)
        before = tuple(tuple(row) for row in learner._codewords)
        learner.fit(self.bundle.train[:8], budget={"epochs": 2})
        after = tuple(tuple(row) for row in learner._codewords)
        self.assertEqual(before, after)
        self.assertFalse(learner.metadata()["trainable_embedding"])
        self.assertEqual(learner.metadata()["embedding_dim"], 4)

    def test_learned_and_fixed_random_start_from_same_embedding_table(self):
        learned = SetConditionedMLPLearner("LEARNED", hidden_size=4, embedding_dim=5, seed=31)
        fixed = SetConditionedMLPLearner("FIXED_RANDOM", hidden_size=4, embedding_dim=5, seed=31)
        learned._initialize(3)
        fixed._initialize(3)
        self.assertEqual(
            tuple(tuple(row) for row in learned._embeddings),
            fixed._codewords,
        )

    def test_fit_is_reproducible_for_same_seed_and_data(self):
        args = dict(family="TERNARY", hidden_size=6, learning_rate=0.01, seed=19)
        first = SetConditionedMLPLearner(**args)
        second = SetConditionedMLPLearner(**args)
        a = first.fit(self.bundle.train[:6], budget={"epochs": 2})
        b = second.fit(self.bundle.train[:6], budget={"epochs": 2})
        self.assertEqual(a, b)
        self.assertEqual(first.predict(self.bundle.validation[0].inputs),
                         second.predict(self.bundle.validation[0].inputs))

    def test_validation_labels_are_only_used_by_evaluator(self):
        learner = SetConditionedMLPLearner("ONE_HOT", hidden_size=6, seed=23)
        row = self.bundle.validation[0]
        before = learner.predict(row.inputs)
        # Prediction takes LearnerInput only; evaluator targets are a separate field.
        self.assertFalse(hasattr(row.inputs, "targets"))
        self.assertEqual(before, learner.predict(row.inputs))

    def test_rejects_invalid_configuration_and_budget(self):
        with self.assertRaises(ValueError):
            SetConditionedMLPLearner("UNKNOWN")
        with self.assertRaises(ValueError):
            SetConditionedMLPLearner("ONE_HOT", hidden_size=0)
        learner = SetConditionedMLPLearner("ONE_HOT")
        with self.assertRaises(ValueError):
            learner.fit(self.bundle.train[:2], budget={"epochs": 0})


if __name__ == "__main__":
    unittest.main()
