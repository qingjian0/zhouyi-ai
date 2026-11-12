"""Tests for the pairwise-preserving third-order parity benchmark."""
import unittest

from prototype.high_order_benchmark import (
    identifiability_report,
    make_dataset,
    run_parity_probe_suite,
    truth_table,
)


class HighOrderBenchmarkTests(unittest.TestCase):
    def test_truth_table_has_balanced_labels_and_all_states(self):
        rows = truth_table()
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(row.label == 1 for row in rows), 4)
        self.assertEqual(sum(row.label == -1 for row in rows), 4)
        self.assertEqual(len({row.bits for row in rows}), 8)

    def test_unary_and_pairwise_marginals_do_not_reveal_label(self):
        report = identifiability_report(make_dataset(repeats=7, seed=41))
        self.assertEqual(report.positive_examples, report.negative_examples)
        self.assertAlmostEqual(report.max_unary_label_correlation, 0.0)
        self.assertAlmostEqual(report.max_pairwise_label_correlation, 0.0)
        self.assertAlmostEqual(report.pairwise_conditional_tv, 0.0)
        self.assertAlmostEqual(report.third_order_label_correlation, 1.0)

    def test_parity_rule_is_invariant_under_role_permutation(self):
        from itertools import permutations
        for row in truth_table():
            for permutation in permutations(row.bits):
                self.assertEqual(
                    row.label,
                    permutation[0] * permutation[1] * permutation[2],
                )

    def test_invalid_label_and_non_integer_bits_are_rejected(self):
        from prototype.high_order_benchmark import ParityExample, interaction_features
        with self.assertRaises(ValueError):
            interaction_features((1.0, 1, -1), 3)
        with self.assertRaises(ValueError):
            identifiability_report((ParityExample((1, 1, 1), -1),))

    def test_pairwise_probe_is_at_chance_but_third_order_probe_solves_task(self):
        unary, pairwise, third_order = run_parity_probe_suite(repeats=16, epochs=500)
        self.assertAlmostEqual(unary.accuracy, 0.5, places=6)
        self.assertAlmostEqual(pairwise.accuracy, 0.5, places=6)
        self.assertGreaterEqual(third_order.accuracy, 0.99)
        self.assertLess(third_order.mean_log_loss, 0.1)

    def test_invalid_dataset_and_feature_orders_are_rejected(self):
        from prototype.high_order_benchmark import interaction_features, parity_label
        with self.assertRaises(ValueError):
            parity_label((1, 0, -1))
        with self.assertRaises(ValueError):
            interaction_features((1, 1, 1), 4)
        with self.assertRaises(ValueError):
            identifiability_report(())


if __name__ == "__main__":
    unittest.main()
