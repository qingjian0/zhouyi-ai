import math
import unittest

from prototype.cpg_ei_selection_optimizer_sweep import run_selection_optimizer_sweep


class TestSelectionOptimizerSweep(unittest.TestCase):
    def test_small_sweep_pairs_protocols_without_locked_selection(self):
        report = run_selection_optimizer_sweep(
            seeds=(11,), learning_rates=(0.15, 0.35), epochs=2
        )
        self.assertEqual(len(report["records"]), 3 * 2 * 2)
        self.assertEqual(len(report["summary"]), 2 * 2)
        self.assertEqual(report["split_sizes"], {
            "train": 40, "proposal_selection": 12, "locked_test": 12
        })
        self.assertEqual(
            report["selection_metric"],
            "candidate_ranking_bce_on_protocol_specific_partition",
        )
        self.assertEqual(report["ranking_partitions"], {
            "proposal_split": "proposal", "legacy_train_ranked": "train"
        })
        self.assertFalse(report["locked_and_ood_metrics_used_for_selection"])
        for row in report["records"]:
            self.assertEqual(row["train_examples"], 40)
            self.assertEqual(row["locked_test_examples"], 12)
            self.assertIn(row["selection_protocol"], ("proposal_split", "legacy_train_ranked"))
            self.assertEqual(
                row["candidate_ranking_partition"],
                "proposal" if row["selection_protocol"] == "proposal_split" else "train",
            )
            self.assertTrue(math.isfinite(row["candidate_ranking_bce"]))
            if row["selection_protocol"] == "proposal_split":
                self.assertTrue(math.isfinite(row["proposal_selection_bce"]))
            else:
                self.assertIsNone(row["proposal_selection_bce"])
            for key in (
                "locked_test_bce", "locked_test_bit_accuracy",
                "support_precision", "support_recall",
            ):
                self.assertTrue(math.isfinite(row[key]))

    def test_rejects_invalid_schedules(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            run_selection_optimizer_sweep(seeds=(), learning_rates=(0.35,), epochs=1)
        with self.assertRaisesRegex(ValueError, "positive"):
            run_selection_optimizer_sweep(seeds=(11,), learning_rates=(0.0,), epochs=1)
        with self.assertRaisesRegex(ValueError, "unique"):
            run_selection_optimizer_sweep(seeds=(11,), learning_rates=(0.35, 0.35), epochs=1)


if __name__ == "__main__":
    unittest.main()
