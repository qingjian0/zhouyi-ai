import json
import tempfile
import unittest
from pathlib import Path

from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_experiment import LearnableSROKError, run_experiment


class N010ExperimentRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dataset = self.root / "data.jsonl"
        self.roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"eligible"}))
            for name in ("r0", "r1")
        )
        rows = []
        for split, prefix in (("train", "tr"), ("dev", "dv"), ("locked_test", "te")):
            for index in range(3):
                nodes = []
                targets = []
                for role_index, role in enumerate(("r0", "r1")):
                    target_id = f"{prefix}-{index}-{role}-positive"
                    targets.append(target_id)
                    nodes.extend([
                        {"node_id": target_id, "node_type": role,
                         "features": [1.0], "tags": ["eligible"],
                         "evidence_ids": [f"e-{target_id}"]},
                        {"node_id": f"{prefix}-{index}-{role}-negative",
                         "node_type": role, "features": [-1.0],
                         "tags": ["eligible"], "evidence_ids": []},
                    ])
                rows.append({"id": f"{prefix}-{index}", "split": split,
                             "nodes": nodes, "target_ids": targets})
        self.dataset.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_train_dev_locked_test_manifest_and_metrics(self):
        report = run_experiment(
            self.dataset, self.roles, 1, self.root / "run.json",
            epochs=3, max_expansions=64, seed=17, git_sha="test-sha",
        )
        manifest = report["dataset_manifest"]
        self.assertEqual(report["training_examples"], 3)
        self.assertEqual(len(manifest["split_ids"]["train"]), 3)
        self.assertEqual(len(manifest["split_ids"]["dev"]), 3)
        self.assertEqual(len(manifest["split_ids"]["locked_test"]), 3)
        self.assertTrue(set(manifest["split_ids"]["train"]).isdisjoint(
            manifest["split_ids"]["dev"]))
        self.assertTrue(set(manifest["split_ids"]["train"]).isdisjoint(
            manifest["split_ids"]["locked_test"]))
        self.assertEqual(report["completed_epochs"], 3)
        for split in ("dev", "locked_test"):
            self.assertEqual(report[split]["examples"], 3)
            self.assertGreaterEqual(report[split]["coverage"], 0.0)
            self.assertLessEqual(report[split]["coverage"], 1.0)

    def test_interrupted_checkpoint_resume_matches_uninterrupted_training(self):
        partial = self.root / "partial.json"
        full = self.root / "full.json"
        run_experiment(self.dataset, self.roles, 1, partial, epochs=2,
                       max_expansions=64, seed=5, git_sha="same")
        resumed = run_experiment(self.dataset, self.roles, 1, partial, epochs=4,
                                 max_expansions=64, seed=5, git_sha="same",
                                 resume=True)
        uninterrupted = run_experiment(
            self.dataset, self.roles, 1, full, epochs=4,
            max_expansions=64, seed=5, git_sha="same",
        )
        partial_bundle = json.loads(partial.read_text(encoding="utf-8"))
        full_bundle = json.loads(full.read_text(encoding="utf-8"))
        self.assertEqual(partial_bundle["model_checkpoint"],
                         full_bundle["model_checkpoint"])
        self.assertEqual(partial_bundle["loss_history"],
                         full_bundle["loss_history"])
        self.assertEqual(resumed["locked_test"], uninterrupted["locked_test"])

    def test_resume_rejects_changed_dataset(self):
        checkpoint = self.root / "run.json"
        run_experiment(self.dataset, self.roles, 1, checkpoint, epochs=1)
        self.dataset.write_text(self.dataset.read_text(encoding="utf-8") + "\n",
                                encoding="utf-8")
        with self.assertRaises(LearnableSROKError):
            run_experiment(self.dataset, self.roles, 1, checkpoint,
                           epochs=2, resume=True)


if __name__ == "__main__":
    unittest.main()
