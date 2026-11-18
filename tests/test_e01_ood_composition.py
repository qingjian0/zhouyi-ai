import unittest

from prototype.e01_ood_composition import make_query_dataset, run_ood_experiment


class CompositionalOODTests(unittest.TestCase):
    def test_training_queries_are_single_primitive(self):
        for row in make_query_dataset(30, 3, query_cardinality=1):
            self.assertEqual(sum(row.query), 1.0)

    def test_ood_queries_combine_seen_primitives(self):
        rows = make_query_dataset(30, 4, query_cardinality=2)
        self.assertTrue(all(sum(row.query) == 2.0 for row in rows))

    def test_target_contains_all_required_attributes(self):
        for row in make_query_dataset(50, 9, query_cardinality=3):
            target_index = row.targets[0]
            target = row.candidates[target_index]
            self.assertTrue(all(
                query_bit == 0.0 or target_bit == 1.0
                for query_bit, target_bit in zip(row.query, target)
            ))

    def test_hard_negatives_miss_a_required_attribute(self):
        for row in make_query_dataset(20, 10, query_cardinality=2):
            target_index = row.targets[0]
            for index, candidate in enumerate(row.candidates):
                if index != target_index:
                    self.assertTrue(any(
                        query_bit == 1.0 and candidate_bit == 0.0
                        for query_bit, candidate_bit in zip(row.query, candidate)
                    ))

    def test_ood_experiment_returns_comparable_metrics(self):
        result = run_ood_experiment(seed=5, train_count=100, test_count=40)
        self.assertEqual(result["train_query_cardinality"], 1)
        self.assertEqual(result["test_query_cardinality"], 2)
        self.assertIn("learned_ranker", result["metrics"])


if __name__ == "__main__":
    unittest.main()
