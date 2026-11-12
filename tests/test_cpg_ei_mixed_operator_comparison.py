import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_mixed_operator_comparison import (
    run_matched_comparison, write_json_report,
)


class TestMatchedBaselineComparison(unittest.TestCase):
    def test_both_methods_use_identical_corpus_and_splits(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=311
        )
        report = run_matched_comparison(corpus, epochs=8)
        self.assertEqual(report["corpus_sha256"], corpus["manifest"]["corpus_sha256"])
        self.assertEqual(report["corpus"]["rows"], 5 * 16)
        self.assertEqual(report["symbolic"]["family_split_results"]["train"]["families"], 3)
        self.assertEqual(report["trainable"]["family_split_results"]["train"]["families"], 3)
        self.assertEqual(report["symbolic"]["family_split_results"]["development"]["families"], 1)
        self.assertEqual(report["trainable"]["family_split_results"]["locked"]["families"], 1)
        self.assertIn("not a zero-shot", report["protocol"])
        for split in ("train", "development", "locked"):
            metrics = report["trainable"]["family_split_results"][split]
            if metrics["families"]:
                self.assertTrue(0.0 <= metrics["mean_locked_bit_accuracy"] <= 1.0)
                self.assertTrue(0.0 <= metrics["mean_training_bit_accuracy"] <= 1.0)

    def test_json_report_is_parseable_and_ends_with_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = {"ok": True, "value": 7}
            write_json_report(report, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), report)

    def test_deterministic_corpus_identity(self):
        first = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=312
        )
        second = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=312
        )
        self.assertEqual(
            first["manifest"]["corpus_sha256"],
            second["manifest"]["corpus_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
