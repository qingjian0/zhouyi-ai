import unittest

from prototype.cpg_ei_mixed_operator_multiseed import (
    run_multiseed_benchmark,
)


class TestMixedOperatorMultiseed(unittest.TestCase):
    def test_independent_seeds_produce_reproducible_aggregate(self):
        kwargs = dict(
            seeds=(31, 47), family_count=5, input_dim=3,
            output_dim=2, epochs=3, learning_rate=0.1,
        )
        first = run_multiseed_benchmark(**kwargs)
        second = run_multiseed_benchmark(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["dataset_summary"]["independent_seeds"], 2)
        self.assertEqual(first["dataset_summary"]["total_independent_teacher_families"], 10)
        self.assertEqual(first["dataset_summary"]["total_rows_across_seeds"], 80)
        self.assertIn("sample_std_across_seeds",
                      first["locked_aggregation_report_only"]["mean_bit_accuracy"])
        self.assertEqual(len(first["seed_results"]), 2)

    def test_duplicate_or_single_seed_is_rejected(self):
        with self.assertRaises(ValueError):
            run_multiseed_benchmark(
                seeds=(7,), family_count=5, input_dim=3, output_dim=2, epochs=2
            )
        with self.assertRaises(ValueError):
            run_multiseed_benchmark(
                seeds=(7, 7), family_count=5, input_dim=3, output_dim=2, epochs=2
            )


if __name__ == "__main__":
    unittest.main()
