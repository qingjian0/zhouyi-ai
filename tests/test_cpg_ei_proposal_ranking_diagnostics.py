import math
import unittest

from prototype.cpg_ei_proposal_ranking_diagnostics import run_diagnostics


class TestProposalRankingDiagnostics(unittest.TestCase):
    def test_small_diagnostic_reports_best_rejected_candidate(self):
        report = run_diagnostics(
            seeds=(11,),
            epochs_grid=(1,),
            learning_rate=4.2,
        )
        self.assertEqual(len(report["records"]), 3)
        self.assertEqual(report["candidate_fit_partition"], "train")
        self.assertEqual(report["ranking_partition"], "proposal")
        self.assertFalse(report["locked_and_ood_metrics_used_for_selection"])
        for row in report["records"]:
            self.assertGreaterEqual(row["candidate_fits"], 20)
            self.assertLessEqual(row["candidate_fits"], 57)
            self.assertEqual(row["training_passes"], row["candidate_fits"] + 1)
            self.assertTrue(row["best_candidate_proposal_improvements"])
            self.assertTrue(all(
                math.isfinite(value)
                for value in row["best_candidate_proposal_improvements"]
            ))
            self.assertTrue(all(
                math.isfinite(value)
                for value in row["best_candidate_proposal_bces"]
            ))
            self.assertGreaterEqual(row["selected_motif_count"], 0)
            self.assertLessEqual(row["selected_motif_count"], 3)


if __name__ == "__main__":
    unittest.main()
