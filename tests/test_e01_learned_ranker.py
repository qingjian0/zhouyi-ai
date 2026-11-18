import unittest

from prototype.e01_learned_ranker import (
    make_dataset,
    predict_indices,
    run_experiment,
    train_ranker,
)


class LearnedCompositionTests(unittest.TestCase):
    def test_dataset_is_reproducible(self):
        self.assertEqual(make_dataset(4, 19), make_dataset(4, 19))

    def test_target_cardinality_is_fixed(self):
        for example in make_dataset(20, 3):
            self.assertEqual(len(example.targets), 3)
            self.assertEqual(len(set(example.targets)), 3)

    def test_ranker_returns_sparse_non_adjacent_capable_selection(self):
        train = make_dataset(500, 11)
        weights = train_ranker(train, feature_dim=6, epochs=120)
        example = make_dataset(1, 12)[0]
        prediction = predict_indices(example, weights, k=3)
        self.assertEqual(len(prediction), 3)
        self.assertEqual(tuple(sorted(prediction)), prediction)

    def test_experiment_reports_baselines(self):
        result = run_experiment(seed=5, train_count=80, test_count=30)
        self.assertIn("learned_ranker", result["metrics"])
        self.assertIn("random_baseline", result["metrics"])
        self.assertIn("adjacent_prefix_baseline", result["metrics"])


if __name__ == "__main__":
    unittest.main()
