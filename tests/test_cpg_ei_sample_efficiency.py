import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_sample_efficiency import (
    run_sample_efficiency_comparison, write_json_report,
)


class TestSampleEfficiencyComparison(unittest.TestCase):
    def test_matched_support_sizes_and_fixed_holdouts(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=411
        )
        report = run_sample_efficiency_comparison(
            corpus, support_sizes=(2, 4), epochs=3
        )
        self.assertEqual(report["corpus_sha256"], corpus["manifest"]["corpus_sha256"])
        self.assertEqual(report["support_sizes"], [2, 4])
        self.assertEqual(set(report["results_by_support_size"]), {"2", "4"})
        for size in ("2", "4"):
            result = report["results_by_support_size"][size]
            self.assertEqual(
                result["trainable"]["overall"]["families"], 5
            )
            self.assertEqual(
                result["symbolic"]["family_split_results"]["locked"]["families"], 1
            )
            self.assertEqual(
                result["symbolic"]["family_split_results"]["locked"]["outputs"], 7
            )
            self.assertEqual(
                result["trainable"]["overall"]["mean_locked_bit_accuracy"] >= 0.0,
                True,
            )
        self.assertIn("not cross-family zero-shot", report["evaluation_protocol"])

    def test_invalid_support_sizes_rejected(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=412
        )
        with self.assertRaises(ValueError):
            run_sample_efficiency_comparison(corpus, support_sizes=(4, 2), epochs=1)
        with self.assertRaises(ValueError):
            run_sample_efficiency_comparison(corpus, support_sizes=(5,), epochs=1)

    def test_json_report_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = {"result": 1}
            write_json_report(report, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\\n"))
            self.assertEqual(json.loads(raw), report)


if __name__ == "__main__":
    unittest.main()
