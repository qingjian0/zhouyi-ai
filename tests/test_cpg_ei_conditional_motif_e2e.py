import unittest

from prototype.cpg_ei_conditional_motif_e2e import run_experiment


class TestConditionalMotifEndToEnd(unittest.TestCase):
    def test_joint_proposals_train_a_heldout_parity_model(self):
        report = run_experiment(
            seeds=(11,),
            train_samples=512,
            test_samples=256,
            epochs=300,
            learning_rate=0.35,
        )
        row = report["records"][0]
        expected = {(0, 1, 2), (1, 3, 4), (2, 4, 5)}
        selected = {tuple(lines) for lines in row["selected_motifs"]}
        self.assertEqual(selected, expected)
        self.assertTrue(row["exact_support_recovery"])
        self.assertEqual(row["support_precision"], 1.0)
        self.assertEqual(row["support_recall"], 1.0)
        self.assertTrue(row["finite_loss"])
        # Baseline is a diagnostic floor, not a claim that training has converged.
        self.assertGreaterEqual(row["heldout_bit_accuracy"], 0.75)
        self.assertGreaterEqual(row["heldout_exact_state_accuracy"], 0.0)
        self.assertLessEqual(row["heldout_exact_state_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
