import unittest

from prototype.cpg_ei_mixed_operator_multiseed import run_multiseed_benchmark


class TestMixedOperatorMultiseed(unittest.TestCase):
    def test_independent_seeds_and_controls_are_reproducible(self):
        kwargs = dict(
            seeds=(31, 47), family_count=5, input_dim=3,
            output_dim=2, epochs=3, learning_rate=0.1,
        )
        first = run_multiseed_benchmark(**kwargs)
        second = run_multiseed_benchmark(**kwargs)
        self.assertEqual(first, second)
        summary = first["dataset_summary"]
        self.assertEqual(summary["independent_seeds"], 2)
        self.assertEqual(summary["total_independent_teacher_families"], 10)
        self.assertEqual(summary["total_rows_across_seeds"], 80)
        results = first["model_results"]
        self.assertEqual(set(results), {"full_polynomial", "unary_only", "train_majority"})
        self.assertIn(
            "sample_std_across_seeds",
            results["full_polynomial"]["locked_report_only"]["bit_accuracy"],
        )
        self.assertIn("full_minus_unary_only_locked_report_only",
                      first["locked_comparisons_report_only"])
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
