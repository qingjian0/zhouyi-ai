import builtins
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prototype.cpg_ei_generic_learner import RelationalTransitionModel, TransitionExample
from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
from prototype.cpg_ei_early_stopping import (
    fit_with_early_stopping, fit_with_early_stopping_scalar,
    fit_with_early_stopping_vectorized, run_early_stopping_baseline,
    write_json_report,
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


    def test_vectorized_optimizer_matches_scalar_reference(self):
        corpus = generate_mixed_corpus(
            family_count=5, input_dim=4, output_dim=3, seed=533
        )
        family_id = sorted({row["family_id"] for row in corpus["rows"]})[0]
        rows = [row for row in corpus["rows"] if row["family_id"] == family_id]
        training = [
            TransitionExample(tuple(row["state"]), tuple(row["target"]))
            for row in rows if row["state_split"] == "train"
        ]
        development = [
            TransitionExample(tuple(row["state"]), tuple(row["target"]))
            for row in rows if row["state_split"] == "development"
        ]
        scalar_model = RelationalTransitionModel.create(4, 3, 1, 4)
        vector_model = RelationalTransitionModel.create(4, 3, 1, 4)
        scalar = fit_with_early_stopping_scalar(
            scalar_model, training, development,
            max_epochs=24, patience=8, learning_rate=0.1, l2=1e-4,
        )
        vector = fit_with_early_stopping_vectorized(
            vector_model, training, development,
            max_epochs=24, patience=8, learning_rate=0.1, l2=1e-4,
        )
        self.assertEqual(scalar["best_epoch"], vector["best_epoch"])
        self.assertEqual(scalar["epochs_run"], vector["epochs_run"])
        self.assertAlmostEqual(
            scalar["best_development_log_loss"],
            vector["best_development_log_loss"],
            places=9,
        )
        for left_head, right_head in zip(scalar_model.weights, vector_model.weights):
            for left, right in zip(left_head, right_head):
                self.assertAlmostEqual(left, right, places=8)
        for example in development:
            self.assertEqual(
                scalar_model.predict(example.state),
                vector_model.predict(example.state),
            )
        self.assertEqual(vector["optimizer_backend"], "numpy-vectorized-float64")


    def test_optional_numpy_dependency_falls_back_to_scalar(self):
        model = RelationalTransitionModel.create(2, 1, 1, 2)
        training = [
            TransitionExample((0, 0), (0,)),
            TransitionExample((0, 1), (0,)),
            TransitionExample((1, 0), (0,)),
            TransitionExample((1, 1), (1,)),
        ]
        development = [
            TransitionExample((0, 0), (0,)),
            TransitionExample((1, 1), (1,)),
        ]
        original_import = builtins.__import__

        def without_numpy(name, *args, **kwargs):
            if name == "numpy":
                raise ImportError("simulated minimal installation")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_numpy):
            result = fit_with_early_stopping(
                model, training, development, max_epochs=4, patience=2
            )
        self.assertEqual(result["optimizer_backend"], "stdlib-scalar-reference")

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
            self.assertTrue(raw.endswith("\n"))
            self.assertEqual(json.loads(raw), report)


if __name__ == "__main__":
    unittest.main()
