import json
import tempfile
import unittest
from pathlib import Path

from prototype.n09_learnable_srok import LearnableSROKError, RoleSpec
from prototype.n010_experiment import run_experiment
from prototype.n010_streaming_runner import (
    run_streaming_experiment, scan_stream_dataset,
)


class N010StreamingRunnerTests(unittest.TestCase):
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
            for index in range(4):
                nodes = []
                targets = []
                for role in ("r0", "r1"):
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
                rows.append({
                    "id": f"{prefix}-{index}", "split": split,
                    "rule_family": "family-A" if split != "locked_test" else "family-OOD",
                    "group_id": f"{prefix}-source-{index // 2}",
                    "nodes": nodes, "target_ids": targets,
                })
        self.dataset.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_streaming_runner_matches_materialized_training_metrics(self):
        materialized = run_experiment(
            self.dataset, self.roles, 1, self.root / "materialized.json",
            epochs=3, max_expansions=64, seed=17, git_sha="same",
        )
        streamed = run_streaming_experiment(
            self.dataset, self.roles, 1, self.root / "streamed.json",
            epochs=3, max_expansions=64, seed=17, git_sha="same",
        )
        self.assertEqual(streamed["loss_history"], materialized["loss_history"])
        for split in ("dev", "locked_test"):
            expected = {k: v for k, v in materialized[split].items()
                        if k != "predictions"}
            self.assertEqual(streamed[split], expected)
        self.assertEqual(streamed["training_examples"], 4)
        self.assertEqual(streamed["evaluation_mode"],
                         "streaming_aggregate_no_prediction_retention")
        manifest = streamed["dataset_manifest"]
        self.assertEqual(manifest["loader"], "sqlite_indexed_reopenable_jsonl")
        self.assertEqual(manifest["split_counts"]["train"], 4)
        self.assertNotIn("split_ids", manifest)
        self.assertNotIn("predictions", streamed["dev"])

    def test_streaming_checkpoint_resume_matches_uninterrupted(self):
        partial = self.root / "partial.json"
        full = self.root / "full.json"
        run_streaming_experiment(
            self.dataset, self.roles, 1, partial, epochs=2,
            max_expansions=64, seed=5, git_sha="same",
        )
        resumed = run_streaming_experiment(
            self.dataset, self.roles, 1, partial, epochs=4,
            max_expansions=64, seed=5, git_sha="same", resume=True,
        )
        uninterrupted = run_streaming_experiment(
            self.dataset, self.roles, 1, full, epochs=4,
            max_expansions=64, seed=5, git_sha="same",
        )
        p = json.loads(partial.read_text(encoding="utf-8"))
        f = json.loads(full.read_text(encoding="utf-8"))
        self.assertEqual(p["model_checkpoint"], f["model_checkpoint"])
        self.assertEqual(p["loss_history"], f["loss_history"])
        self.assertEqual(resumed["locked_test"], uninterrupted["locked_test"])

    def test_streaming_preflight_detects_cross_split_group_leakage(self):
        rows = [json.loads(line) for line in self.dataset.read_text(encoding="utf-8").splitlines()]
        rows[0]["group_id"] = "shared-source"
        rows[4]["group_id"] = "shared-source"
        self.dataset.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(LearnableSROKError, "group_id leakage"):
            scan_stream_dataset(self.dataset, self.roles, 1)

    def test_streaming_preflight_uses_disk_backed_compact_manifest(self):
        manifest = scan_stream_dataset(self.dataset, self.roles, 1)
        self.assertEqual(manifest["records"], 12)
        self.assertEqual(manifest["split_counts"], {
            "train": 4, "dev": 4, "locked_test": 4,
        })
        self.assertEqual(manifest["group_id_counts_by_split"]["group_id"]["train"], 2)
        self.assertEqual(len(manifest["split_id_sha256"]["train"]), 64)
        self.assertNotIn("split_ids", manifest)


if __name__ == "__main__":
    unittest.main()
