import unittest

from prototype.cpg_ei_vectorized_optimizer_benchmark import (
    run_optimizer_speed_comparison,
)


class TestVectorizedOptimizerBenchmark(unittest.TestCase):
    def test_scalar_and_vectorized_results_match_on_small_corpus(self):
        report = run_optimizer_speed_comparison(
            family_count=5,
            input_dim=4,
            output_dim=3,
            seed=533,
            max_epochs=24,
            patience=8,
            learning_rate=0.1,
            l2=1e-4,
        )
        self.assertTrue(report["parity"]["passed"])
        self.assertTrue(report["parity"]["best_epoch_matches_for_all_families"])
        self.assertEqual(report["parity"]["max_absolute_metric_delta"], 0.0)
        self.assertLessEqual(
            report["parity"]["max_absolute_best_development_loss_delta"],
            1e-8,
        )
        self.assertGreater(report["performance"]["speedup_scalar_over_vectorized"], 0)


if __name__ == "__main__":
    unittest.main()
