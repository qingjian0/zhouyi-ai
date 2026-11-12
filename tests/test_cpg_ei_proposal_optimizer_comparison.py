import math
import unittest

from prototype.cpg_ei_proposal_optimizer_comparison import run_comparison


class TestProposalOptimizerComparison(unittest.TestCase):
    def test_small_proposal_comparison_runs_both_optimizers(self):
        report = run_comparison(
            seeds=(11,),
            epochs_grid=(1,),
        )
        self.assertEqual(len(report["records"]), 3 * 2)
        self.assertEqual(report["candidate_fit_partition"], "train")
        self.assertEqual(report["candidate_ranking_partition"], "proposal")
        self.assertFalse(report["locked_and_ood_metrics_used_for_selection"])
        self.assertEqual(
            {row["optimizer"] for row in report["records"]},
            {"sgd", "adam"},
        )
        for row in report["records"]:
            self.assertTrue(math.isfinite(row["proposal_bce"]))
            self.assertTrue(math.isfinite(row["locked_bce"]))
            self.assertTrue(row["best_candidate_proposal_improvements"])
            self.assertTrue(all(
                math.isfinite(value)
                for value in row["best_candidate_proposal_improvements"]
            ))
            self.assertGreaterEqual(row["candidate_fits"], 20)
            self.assertLessEqual(row["candidate_fits"], 57)
            self.assertEqual(
                row["training_passes"],
                row["epochs_per_candidate"] * (1 + row["candidate_fits"]),
            )


if __name__ == "__main__":
    unittest.main()
