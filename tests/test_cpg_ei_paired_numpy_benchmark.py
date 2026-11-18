import unittest

from prototype.cpg_ei_compute_accounted_hybrid import run_support_constrained_hybrid
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_paired_numpy_benchmark import _family_signature


class TestPairedNumpyHybridBenchmark(unittest.TestCase):
    def test_python_and_numpy_preserve_predictions_and_feature_support(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=991
        )
        python = run_support_constrained_hybrid(
            corpus, max_epochs=12, patience=3, optimizer_backend="python"
        )
        numpy = run_support_constrained_hybrid(
            corpus, max_epochs=12, patience=3, optimizer_backend="numpy"
        )
        self.assertEqual(python["corpus_sha256"], numpy["corpus_sha256"])
        self.assertEqual(python["locked_summary"], numpy["locked_summary"])
        left = _family_signature(python)
        right = _family_signature(numpy)
        self.assertEqual(left.keys(), right.keys())
        for family_id in left:
            self.assertEqual(
                left[family_id]["prediction_sha256"],
                right[family_id]["prediction_sha256"],
            )
            self.assertEqual(
                left[family_id]["feature_counts_by_output"],
                right[family_id]["feature_counts_by_output"],
            )

    def test_prediction_digest_is_stable(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=992
        )
        first = run_support_constrained_hybrid(
            corpus, max_epochs=8, patience=2, optimizer_backend="python"
        )
        second = run_support_constrained_hybrid(
            corpus, max_epochs=8, patience=2, optimizer_backend="python"
        )
        self.assertEqual(
            [row["prediction_sha256"] for row in first["family_results"]],
            [row["prediction_sha256"] for row in second["family_results"]],
        )


if __name__ == "__main__":
    unittest.main()
