import unittest

from prototype.cpg_ei_compute_accounted_hybrid import run_support_constrained_hybrid
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class TestNumpyHybridIntegration(unittest.TestCase):
    def test_cached_feature_accounting_matches_model_heads(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=3, seed=20261114
        )
        report = run_support_constrained_hybrid(
            corpus, max_epochs=12, patience=3, optimizer_backend="numpy"
        )
        self.assertEqual(report["model"]["optimizer_backend"], "numpy")
        train_rows = corpus["manifest"]["state_split_per_family"]["train"]
        development_rows = corpus["manifest"]["state_split_per_family"]["development"]
        fits = [
            fit
            for family in report["family_results"]
            for fit in family["output_fits"]
        ]
        expected_train_encodings = sum(
            train_rows * fit["feature_columns_including_bias"] for fit in fits
        )
        expected_development_encodings = sum(
            development_rows * fit["feature_columns_including_bias"] for fit in fits
        )
        expected_gradient_terms = sum(
            fit["epochs_run"] * train_rows * fit["feature_columns_including_bias"]
            for fit in fits
        )
        accounting = report["compute_accounting"]
        self.assertEqual(
            accounting["training_feature_encodings"], expected_train_encodings
        )
        self.assertEqual(
            accounting["development_feature_encodings_for_checkpoint_selection"],
            expected_development_encodings,
        )
        self.assertEqual(
            accounting["gradient_feature_contributions"], expected_gradient_terms
        )

    def test_unknown_backend_is_rejected(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=20261114
        )
        with self.assertRaises(ValueError):
            run_support_constrained_hybrid(corpus, optimizer_backend="gpu")


if __name__ == "__main__":
    unittest.main()
