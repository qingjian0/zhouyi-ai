import unittest

from prototype.cpg_ei_proposal_fit_epoch_sweep import run_epoch_sweep


class CpgEiProposalFitEpochSweepTests(unittest.TestCase):
    def test_small_epoch_sweep_reports_paired_protocols(self):
        report = run_epoch_sweep(seeds=(11,), epochs=(1,), max_motifs=1)
        self.assertEqual(report["epochs_per_candidate"], [1])
        self.assertEqual(len(report["records"]), 2 * 3)
        aggregate = report["aggregate_by_epoch_and_protocol"]["1"]
        self.assertEqual(aggregate["proposal_split"]["experiments"], 3)
        self.assertEqual(aggregate["legacy_train_ranked"]["experiments"], 3)
        self.assertTrue(all(row["epochs_per_candidate"] == 1 for row in report["records"]))


if __name__ == "__main__":
    unittest.main()
