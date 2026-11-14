import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.core.experiment_archive import archive_benchmark_report
from orchestrator.research.archive_adapter import evaluate_archived_evidence


class ArchivedEvidenceAdapterTests(unittest.TestCase):
    def make_row(self, evidence_id, split, control, task_id, source):
        return {
            "evidence_id": evidence_id,
            "split": split,
            "control": control,
            "effect_mean": 0.2,
            "ci_lower": 0.1,
            "ci_upper": 0.3,
            "seeds": 10,
            "valid": True,
            "preregistered": True,
            "task_ids": [task_id],
            "observation_ids": [f"obs-{task_id}"],
            "expected_seeds": list(range(10)),
            "observed_seeds": list(range(10)),
            "metric": "ood_accuracy_delta",
            "metric_direction": "positive",
            "split_source": source,
            "control_family": control,
        }

    def archive(self, directory, rows):
        report = {"task_set_digest": "matrix-abc", "evidence_rows": rows}
        result = archive_benchmark_report(report, directory, run_id="run-001", code_revision="test-rev")
        return Path(result["path"])

    def test_verifies_archive_and_provenance_then_evaluates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, [
                self.make_row("ood", "ood", "none", "task-ood", "heldout_ood_split_v1"),
                self.make_row("shuffle", "iid", "shuffled", "task-shuffle", "iid_validation_v1"),
            ])
            result = evaluate_archived_evidence(path, expected_task_set_digest="matrix-abc", predicted_direction="positive")
            self.assertEqual(result["verdict"], "supported")
            self.assertEqual(result["archive"]["unique_task_count"], 2)
            self.assertEqual(result["archive"]["unique_observation_count"], 2)

    def test_rejects_wrong_task_set_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, [
                self.make_row("ood", "ood", "none", "task-ood", "heldout_ood_split_v1"),
            ])
            with self.assertRaisesRegex(ValueError, "task-set digest"):
                evaluate_archived_evidence(path, expected_task_set_digest="other", predicted_direction="positive")

    def test_rejects_tampered_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, [
                self.make_row("ood", "ood", "none", "task-ood", "heldout_ood_split_v1"),
            ])
            envelope = json.loads(path.read_text())
            envelope["report"]["evidence_rows"][0]["effect_mean"] = 99
            path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                evaluate_archived_evidence(path, expected_task_set_digest="matrix-abc", predicted_direction="positive")

    def test_rejects_ood_without_ood_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, [
                self.make_row("ood", "ood", "none", "task-ood", "ordinary_validation"),
            ])
            with self.assertRaisesRegex(ValueError, "OOD provenance"):
                evaluate_archived_evidence(path, expected_task_set_digest="matrix-abc", predicted_direction="positive")

    def test_rejects_seed_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            row = self.make_row("ood", "ood", "none", "task-ood", "heldout_ood_split_v1")
            row["observed_seeds"] = [0, 1, 2]
            path = self.archive(directory, [row])
            with self.assertRaisesRegex(ValueError, "seed count"):
                evaluate_archived_evidence(path, expected_task_set_digest="matrix-abc", predicted_direction="positive")


if __name__ == "__main__":
    unittest.main()
