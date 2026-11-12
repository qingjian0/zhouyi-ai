import unittest

from prototype.cpg_ei_adam_optimizer_comparison import run_comparison


class TestAdamOptimizerComparison(unittest.TestCase):
    def test_small_comparison_is_train_only_and_reports_both_optimizers(self):
        report = run_comparison(
            seeds=(11,),
            epochs=2,
            sgd_rates=(0.35,),
            adam_rates=(0.01,),
        )
        self.assertEqual(len(report["records"]), 3 * 2 * 2)
        self.assertEqual(len(report["summary"]), 4)
        self.assertEqual(report["selection_metric"], "mean_final_train_bce_only")
        self.assertFalse(report["locked_and_full_metrics_used_for_selection"])
        self.assertEqual(
            {row["optimizer"] for row in report["records"]},
            {"sgd", "adam"},
        )
        self.assertTrue(all(row["support_source"] == "oracle_known_support"
                            for row in report["records"]))
        self.assertTrue(all(row["gradient_data"] == "train_40_only"
                            for row in report["records"]))
        self.assertIn("best_train_config", report)
        self.assertNotIn("best_locked_config", report)


if __name__ == "__main__":
    unittest.main()
