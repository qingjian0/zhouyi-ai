import copy
import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_compute_accounted_hybrid import (
    derive_train_only_support_features,
    run_compute_accounted_comparison,
    run_support_constrained_hybrid,
    write_json_report,
)
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class TestComputeAccountedSupportHybrid(unittest.TestCase):
    def setUp(self):
        self.corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=711
        )

    def test_support_features_use_training_labels_only(self):
        changed = copy.deepcopy(self.corpus)
        for row in changed["rows"]:
            if row["state_split"] != "train":
                row["target"] = [1 - bit for bit in row["target"]]
        original = derive_train_only_support_features(self.corpus)
        mutated = derive_train_only_support_features(changed)
        self.assertEqual(
            original["family_features"],
            mutated["family_features"],
        )
        self.assertEqual(
            original["candidate_output_train_score_evaluations"],
            mutated["candidate_output_train_score_evaluations"],
        )

    def test_locked_labels_do_not_change_selected_hybrid_weights(self):
        changed = copy.deepcopy(self.corpus)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        original = run_support_constrained_hybrid(
            self.corpus, max_epochs=10, patience=3
        )
        mutated = run_support_constrained_hybrid(
            changed, max_epochs=10, patience=3
        )
        self.assertEqual(
            original["candidate_accounting"],
            mutated["candidate_accounting"],
        )
        for left_family, right_family in zip(
            original["family_results"], mutated["family_results"]
        ):
            for left, right in zip(
                left_family["output_fits"], right_family["output_fits"]
            ):
                self.assertEqual(left["best_epoch"], right["best_epoch"])
                self.assertEqual(
                    left["selected_weights_sha256"],
                    right["selected_weights_sha256"],
                )
                self.assertEqual(
                    left["best_development_log_loss"],
                    right["best_development_log_loss"],
                )

    def test_matched_compute_report_accounts_for_same_corpus(self):
        report = run_compute_accounted_comparison(
            self.corpus, max_epochs=8, patience=3
        )
        self.assertEqual(
            report["corpus_sha256"],
            self.corpus["manifest"]["corpus_sha256"],
        )
        methods = report["methods"]
        self.assertGreater(
            methods["exhaustive_symbolic"]["candidate_output_train_score_evaluations"],
            0,
        )
        self.assertEqual(
            methods["full_polynomial_early_stopping"]["feature_accounting"][
                "feature_count_excluding_bias_per_output"
            ],
            15,
        )
        hybrid_features = methods["symbolic_support_constrained_hybrid"][
            "feature_accounting"
        ]["feature_count_excluding_bias"]
        self.assertGreaterEqual(hybrid_features["min"], 1)
        self.assertLessEqual(hybrid_features["max"], 15)
        self.assertGreaterEqual(
            methods["symbolic_support_constrained_hybrid"]["wall_seconds"], 0
        )
        self.assertGreaterEqual(
            methods["symbolic_support_constrained_hybrid"][
                "peak_traced_allocation_delta_bytes"
            ],
            0,
        )

    def test_empty_training_split_is_rejected(self):
        changed = copy.deepcopy(self.corpus)
        for row in changed["rows"]:
            row["state_split"] = "locked"
        with self.assertRaises(ValueError):
            run_support_constrained_hybrid(
                changed, max_epochs=2, patience=1
            )

    def test_report_writer_emits_parseable_json_with_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_json_report({"ok": True}, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), {"ok": True})


if __name__ == "__main__":
    unittest.main()
