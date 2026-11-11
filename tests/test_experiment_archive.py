import json
import tempfile
import unittest
from pathlib import Path
from orchestrator.core.experiment_archive import archive_benchmark_report

class ExperimentArchiveTests(unittest.TestCase):
    def test_writes_verified_envelope(self):
        with tempfile.TemporaryDirectory() as directory:
            report = {"task_set_digest": "abc", "equivalent": True, "speedup": 2.0}
            result = archive_benchmark_report(report, directory, run_id="trial-001", code_revision="deadbeef")
            saved = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["report"], report)
            self.assertEqual(saved["task_set_digest"], "abc")
            self.assertEqual(saved["code_revision"], "deadbeef")
            self.assertEqual(saved["report_digest"], result["report_digest"])

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_benchmark_report({"x": 1}, directory, run_id="same")
            with self.assertRaises(FileExistsError):
                archive_benchmark_report({"x": 2}, directory, run_id="same")

    def test_rejects_invalid_json_and_run_id(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                archive_benchmark_report({"x": float("nan")}, directory, run_id="bad")
            with self.assertRaises(ValueError):
                archive_benchmark_report({"x": 1}, directory, run_id="../escape")

if __name__ == "__main__":
    unittest.main()