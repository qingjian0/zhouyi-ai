import unittest

from prototype.recurrent_benchmark_tasks import (
    associative_recall,
    delayed_copy,
    distractor_recall,
    distribution_shift,
    periodic_next_symbol,
    validate_examples,
)


class RecurrentBenchmarkTaskTests(unittest.TestCase):
    def test_generators_are_deterministic_and_binary(self):
        factories = (
            lambda: periodic_next_symbol(count=8, seed=19),
            lambda: delayed_copy(count=8, seed=19),
            lambda: associative_recall(count=8, seed=19),
            lambda: distractor_recall(count=8, seed=19),
        )
        for factory in factories:
            first, second = factory(), factory()
            self.assertEqual(first, second)
            self.assertEqual(len(first), 8)
            self.assertGreater(validate_examples(first), 0)

    def test_delayed_copy_target_is_first_payload_bit(self):
        rows = delayed_copy(count=20, payload_length=7, distractor_length=13)
        for row in rows:
            self.assertEqual(row.context[3], row.target)

    def test_associative_recall_has_unique_key_capacity(self):
        with self.assertRaises(ValueError):
            associative_recall(count=1, pair_count=9, key_bits=3)

    def test_distribution_shift_uses_distinct_periods(self):
        train, evaluation = distribution_shift(count=10, train_period=5, eval_period=11)
        self.assertEqual(len(train), 10)
        self.assertEqual(len(evaluation), 10)
        self.assertEqual(dict(train[0].metadata)["period"], 5)
        self.assertEqual(dict(evaluation[0].metadata)["period"], 11)

    def test_invalid_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            periodic_next_symbol(count=0)
        with self.assertRaises(ValueError):
            delayed_copy(count=1, distractor_length=0)
        with self.assertRaises(ValueError):
            distractor_recall(count=1, payload_length=0)


if __name__ == "__main__":
    unittest.main()
