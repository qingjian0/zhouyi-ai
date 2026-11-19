import unittest

from prototype.recurrent_benchmark import BenchmarkConfig, run_benchmark


class RecurrentBenchmarkRunnerTests(unittest.TestCase):
    def test_runner_emits_parameter_matched_models_and_required_metrics(self):
        report = run_benchmark(
            BenchmarkConfig(
                task="delayed_copy", train_examples=8, eval_examples=6,
                epochs=1, seed=23, payload_length=3, gap_length=4,
            ),
            seeds=(23,),
        )
        self.assertEqual(report["scope"], "synthetic_binary_recurrent_mechanism_benchmark")
        self.assertEqual(len(report["results"]), 3)
        by_model = {row["model"]: row for row in report["results"]}
        self.assertEqual(by_model["gated_rnn"]["parameter_count"], 29)
        self.assertEqual(by_model["linear_rnn"]["parameter_count"], 29)
        self.assertEqual(by_model["selective_diagonal_ssm"]["parameter_count"], 29)
        for row in report["results"]:
            self.assertTrue(row["chunk_state_parity"])
            self.assertGreaterEqual(row["accuracy"], 0.0)
            self.assertLessEqual(row["accuracy"], 1.0)
            self.assertGreater(row["binary_cross_entropy"], 0.0)
            self.assertGreater(row["peak_traced_python_bytes"], 0)
            self.assertIn(row["train_rss_measurement_source"],
                          ("sampled_process_rss", "unavailable"))
            if row["train_rss_measurement_source"] == "sampled_process_rss":
                self.assertGreater(row["train_sampled_peak_rss_bytes"], 0)
                self.assertGreaterEqual(row["train_rss_peak_increment_bytes"], 0)

    def test_runner_supports_held_out_evaluation_gap_length(self):
        report = run_benchmark(
            BenchmarkConfig(
                task="delayed_copy", train_examples=4, eval_examples=3,
                epochs=1, seed=29, payload_length=2, gap_length=4,
                eval_gap_length=12,
            ),
            seeds=(29,),
        )
        for row in report["results"]:
            self.assertEqual(row["train_context_symbols_per_epoch"], 4 * 15)
            self.assertEqual(row["evaluation_context_symbols"], 3 * 23)

    def test_runner_rejects_non_positive_evaluation_gap_length(self):
        with self.assertRaises(ValueError):
            run_benchmark(
                BenchmarkConfig(eval_gap_length=0),
                seeds=(1,),
            )

    def test_runner_rejects_empty_dataset(self):
        with self.assertRaises(ValueError):
            run_benchmark(BenchmarkConfig(train_examples=0), seeds=(1,))


if __name__ == "__main__":
    unittest.main()
