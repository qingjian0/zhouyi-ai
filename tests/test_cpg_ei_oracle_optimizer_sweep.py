import math
import unittest

from prototype.cpg_ei_oracle_optimizer_sweep import run_optimizer_sweep


class TestOracleOptimizerSweep(unittest.TestCase):
    def test_small_sweep_reports_train_locked_and_full_domain_separately(self):
        report = run_optimizer_sweep(
            seeds=(11,), learning_rates=(0.1, 0.35), epochs=2
        )
        self.assertEqual(len(report["records"]), 3 * 2 * 2)
        self.assertEqual(len(report["summary"]), 4)
        self.assertEqual(report["train_examples"], 40)
        self.assertEqual(report["locked_test_examples"], 12)
        self.assertEqual(report["selection_metric"], "mean_final_train_bce_only")
        self.assertFalse(report["locked_and_full_metrics_used_for_selection"])
        self.assertIn("best_train_config", report)
        self.assertNotIn("best_locked_config", report)
        self.assertNotIn("best_full_64_state_config", report)
        for row in report["records"]:
            self.assertEqual(row["support_source"], "oracle_known_support")
            self.assertEqual(row["gradient_data"], "train_40_only")
            for key in (
                "train_bit_accuracy", "locked_bit_accuracy",
                "full_64_state_bit_accuracy", "final_train_bce",
            ):
                self.assertTrue(math.isfinite(row[key]))

    def test_rejects_invalid_schedules(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_optimizer_sweep(seeds=(), learning_rates=(0.1,), epochs=1)
        with self.assertRaisesRegex(ValueError, "positive"):
            run_optimizer_sweep(seeds=(1,), learning_rates=(0.0,), epochs=1)
        with self.assertRaisesRegex(ValueError, "unique"):
            run_optimizer_sweep(seeds=(1,), learning_rates=(0.1, 0.1), epochs=1)


if __name__ == "__main__":
    unittest.main()
