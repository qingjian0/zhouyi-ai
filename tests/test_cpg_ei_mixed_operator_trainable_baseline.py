import unittest

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_trainable_baseline import run_trainable_baseline


class TestTrainablePolynomialBaseline(unittest.TestCase):
    def test_small_mixed_corpus_trains_and_reports_locked_metrics(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=211
        )
        report = run_trainable_baseline(corpus, epochs=12, learning_rate=0.1)
        self.assertEqual(report["development_summary"]["families"], 5)
        self.assertEqual(report["locked_summary"]["families"], 5)
        self.assertEqual(len(report["family_results"]), 5)
        for split in ("development_summary", "locked_summary"):
            metrics = report[split]
            self.assertTrue(0.0 <= metrics["mean_bit_accuracy"] <= 1.0)
            self.assertTrue(0.0 <= metrics["mean_exact_state_accuracy"] <= 1.0)
        self.assertIn("not cross-family meta-learning", report["evaluation_protocol"])
        self.assertIn("fixed exhaustive Boolean monomial basis", report["claim_boundary"])

    def test_empty_training_family_is_not_silently_accepted(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=19
        )
        for row in corpus["rows"]:
            row["state_split"] = "locked"
        with self.assertRaises(ValueError):
            run_trainable_baseline(corpus, epochs=2)


if __name__ == "__main__":
    unittest.main()
