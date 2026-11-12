import math
import unittest

from prototype.cpg_ei_proximal_regularization_sweep import (
    run_proximal_regularization_sweep,
)


class TestProximalRegularizationSweep(unittest.TestCase):
    def test_small_sweep_reports_both_training_paths(self):
        report = run_proximal_regularization_sweep(
            seeds=(7,),
            group_l1_values=(0.005, 0.03),
            learning_rate=2.1,
            direct_epochs=2,
            discovery_rounds=1,
            edges_per_round=1,
            discovery_epochs_per_round=1,
        )
        self.assertEqual(len(report["records"]), 4)
        self.assertEqual(len(report["summary"]), 4)
        self.assertEqual(report["selection_metric"], "none; all configurations reported")
        for row in report["records"]:
            self.assertIn(row["mode"], {
                "direct_sparse_fit", "residual_structure_discovery"
            })
            self.assertTrue(math.isfinite(row["validation_bit_accuracy"]))
            self.assertTrue(math.isfinite(row["support_precision"]))
            self.assertTrue(math.isfinite(row["support_recall"]))

    def test_rejects_invalid_schedules_and_penalties(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_proximal_regularization_sweep(seeds=(), group_l1_values=(0.005,))
        with self.assertRaisesRegex(ValueError, "positive"):
            run_proximal_regularization_sweep(learning_rate=0.0)
        with self.assertRaisesRegex(ValueError, "unique"):
            run_proximal_regularization_sweep(group_l1_values=(0.005, 0.005))
        with self.assertRaisesRegex(ValueError, "non-negative"):
            run_proximal_regularization_sweep(group_l1_values=(-0.1,))


if __name__ == "__main__":
    unittest.main()
