import unittest

from prototype.cpg_ei_conditional_motif_locked_test import run_locked_test


class TestConditionalMotifLockedTest(unittest.TestCase):
    def test_locked_split_is_used_only_after_dev_selection(self):
        report = run_locked_test(
            seeds=(11,),
            learning_rates=(0.35, 1.05),
            epoch_counts=(300,),
            train_samples=512,
            dev_samples=128,
            locked_samples=128,
        )
        self.assertEqual(
            report["selection_policy"]["hyperparameter_selection"],
            "development split only",
        )
        self.assertEqual(
            report["selection_policy"]["locked_test_access"],
            "final evaluation only",
        )
        self.assertEqual(report["sample_counts"]["locked_test"], 128)
        self.assertEqual(len(report["development_sweep"]), 2)
        row = report["locked_test_records"][0]
        self.assertTrue(row["exact_support_recovery"])
        self.assertEqual(row["support_precision"], 1.0)
        self.assertEqual(row["support_recall"], 1.0)
        self.assertTrue(row["finite_loss"])
        self.assertGreaterEqual(row["bit_accuracy"], 0.0)
        self.assertLessEqual(row["bit_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
