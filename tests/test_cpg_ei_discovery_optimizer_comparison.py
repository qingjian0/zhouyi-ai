import math
import unittest

from prototype.cpg_ei_discovery_optimizer_comparison import (
    run_selection_optimizer_comparison,
)


class TestDiscoveryOptimizerComparison(unittest.TestCase):
    def test_small_sweep_pairs_optimizers_and_selection_protocols(self):
        report = run_selection_optimizer_comparison(
            seeds=(11,),
            optimizer_configs=(("sgd", 0.35), ("adam", 0.01)),
            epochs_per_candidate=1,
            max_motifs=1,
        )
        self.assertEqual(len(report["records"]), 3 * 2 * 2)
        self.assertEqual(len(report["summary"]), 4)
        self.assertFalse(report["locked_and_ood_metrics_used_for_selection"])
        for row in report["records"]:
            self.assertIn(row["optimizer"], {"sgd", "adam"})
            self.assertIn(row["selection_protocol"], {
                "proposal_split", "legacy_train_ranked"
            })
            self.assertEqual(row["train_examples"], 40)
            self.assertEqual(row["locked_test_examples"], 12)
            self.assertTrue(math.isfinite(row["selection_bce"]))
            self.assertTrue(math.isfinite(row["locked_test_bit_accuracy"]))

    def test_rejects_invalid_optimizer_configurations(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_selection_optimizer_comparison(
                seeds=(), optimizer_configs=(("sgd", 0.35),), epochs_per_candidate=1
            )
        with self.assertRaisesRegex(ValueError, "optimizer"):
            run_selection_optimizer_comparison(
                seeds=(11,), optimizer_configs=(("rmsprop", 0.01),),
                epochs_per_candidate=1,
            )
        with self.assertRaisesRegex(ValueError, "positive"):
            run_selection_optimizer_comparison(
                seeds=(11,), optimizer_configs=(("adam", 0.0),),
                epochs_per_candidate=1,
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            run_selection_optimizer_comparison(
                seeds=(11,), optimizer_configs=(("adam", 0.01), ("adam", 0.01)),
                epochs_per_candidate=1,
            )


if __name__ == "__main__":
    unittest.main()
