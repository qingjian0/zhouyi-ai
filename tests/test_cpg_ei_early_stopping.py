import copy
import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_generic_learner import RelationalTransitionModel, TransitionExample
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_early_stopping import (
    fit_with_early_stopping, run_early_stopping_baseline, write_json_report,
)


class TestEarlyStoppingBaseline(unittest.TestCase):
    def test_checkpoint_is_selected_and_reported(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=7, seed=511
        )
        report = run_early_stopping_baseline(
            corpus, max_epochs=12, patience=3
        )
        self.assertEqual(report["locked_summary"]["families"], 5)
        self.assertEqual(len(report["family_results"]), 5)
        for row in report["family_results"]:
            self.assertGreaterEqual(row["best_epoch"], 0)
            self.assertLessEqual(row["best_epoch"], row["epochs_run"])
            self.assertLessEqual(row["epochs_run"], 12)
            self.assertEqual(len(row["selected_weights_sha256"]), 64)
            self.assertTrue(0.0 <= row["locked"]["bit_accuracy"] <= 1.0)

    def test_locked_labels_cannot_change_checkpoint_selection(self):
        original = generate_mixed_corpus(
            family_count=5, input_dim=3, output_dim=2, seed=512
        )
        changed = copy.deepcopy(original)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - value for value in row["target"]]
        a = run_early_stopping_baseline(original, max_epochs=10, patience=3)
        b = run_early_stopping_baseline(changed, max_epochs=10, patience=3)
        for left, right in zip(a["family_results"], b["family_results"]):
            self.assertEqual(left["best_epoch"], right["best_epoch"])
            self.assertEqual(
                left["selected_weights_sha256"], right["selected_weights_sha256"]
            )
            self.assertEqual(
                left["best_development_log_loss"], right["best_development_log_loss"]
            )

    def test_empty_development_is_rejected(self):
        model = RelationalTransitionModel.create(2, 1, 1, 2)
        training = [TransitionExample((0, 0), (0,)), TransitionExample((1, 1), (1,))]
        with self.assertRaises(ValueError):
            fit_with_early_stopping(model, training, [], max_epochs=2)

    def test_json_report_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = {"valid": True}
            write_json_report(report, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\\n"))
            self.assertEqual(json.loads(raw), report)


if __name__ == "__main__":
    unittest.main()
