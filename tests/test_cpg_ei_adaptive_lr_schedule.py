import copy
import json
import tempfile
import unittest
from pathlib import Path

from prototype.cpg_ei_adaptive_lr_schedule import fit_with_plateau_schedule, run_adaptive_schedule, write_json_report
from prototype.cpg_ei_generic_learner import RelationalTransitionModel, TransitionExample
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus


class TestAdaptiveLearningRateSchedule(unittest.TestCase):
    def test_small_corpus_runs_and_reports_schedule(self):
        corpus = generate_mixed_corpus(family_count=5, input_dim=3, output_dim=2, seed=711)
        report = run_adaptive_schedule(corpus, max_epochs=24, lr_patience=4, stop_patience=8)
        self.assertEqual(report["locked_summary"]["families"], 5)
        self.assertEqual(len(report["family_results"]), 5)
        for row in report["family_results"]:
            self.assertGreaterEqual(row["epochs_run"], 1)
            self.assertLessEqual(row["epochs_run"], 24)
            self.assertGreaterEqual(row["learning_rate_reductions"], 0)
            self.assertGreater(row["final_learning_rate"], 0)
            self.assertEqual(len(row["selected_weights_sha256"]), 64)

    def test_locked_labels_cannot_change_selected_weights(self):
        original = generate_mixed_corpus(family_count=5, input_dim=3, output_dim=2, seed=712)
        changed = copy.deepcopy(original)
        for row in changed["rows"]:
            if row["state_split"] == "locked":
                row["target"] = [1 - bit for bit in row["target"]]
        a = run_adaptive_schedule(original, max_epochs=20, lr_patience=4, stop_patience=8)
        b = run_adaptive_schedule(changed, max_epochs=20, lr_patience=4, stop_patience=8)
        for left, right in zip(a["family_results"], b["family_results"]):
            self.assertEqual(left["best_epoch"], right["best_epoch"])
            self.assertEqual(left["learning_rate_reductions"], right["learning_rate_reductions"])
            self.assertEqual(left["selected_weights_sha256"], right["selected_weights_sha256"])
            self.assertEqual(left["best_development_log_loss"], right["best_development_log_loss"])

    def test_invalid_scheduler_configuration_is_rejected(self):
        model = RelationalTransitionModel.create(2, 1, 1, 2)
        rows = [TransitionExample((0, 0), (0,)), TransitionExample((1, 1), (1,))]
        with self.assertRaises(ValueError):
            fit_with_plateau_schedule(model, rows, rows, lr_factor=1.0)
        with self.assertRaises(ValueError):
            fit_with_plateau_schedule(model, rows, rows, min_learning_rate=0.2)

    def test_json_report_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_json_report({"ok": True}, path)
            raw = path.read_text(encoding="utf-8")
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), {"ok": True})


if __name__ == "__main__":
    unittest.main()
