import json
import tempfile
import unittest
from pathlib import Path

from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_experiment import load_dataset
from prototype.n010_synthetic import generate_compositional_dataset


class CompositionalSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
            for name in ("r0", "r1", "r2")
        )

    def test_generator_is_deterministic_and_family_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            manifest_a = generate_compositional_dataset(
                first, seed=41, train_count=8, dev_count=4,
                locked_test_count=4, candidates_per_role=3,
            )
            manifest_b = generate_compositional_dataset(
                second, seed=41, train_count=8, dev_count=4,
                locked_test_count=4, candidates_per_role=3,
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(manifest_a["dataset_sha256"], manifest_b["dataset_sha256"])
            self.assertEqual(manifest_a["rule_families_by_split"], {
                "train": ["cycle-forward"], "dev": ["cycle-forward"],
                "locked_test": ["cycle-reverse"],
            })
            splits, run_manifest = load_dataset(first, self.roles, 4)
            self.assertEqual(len(splits["train"]), 8)
            self.assertEqual(len(splits["dev"]), 4)
            self.assertEqual(len(splits["locked_test"]), 4)
            self.assertEqual(run_manifest["generation_provenance"]["target_rule"],
                             manifest_a["target_rule"])

    def test_records_have_role_complete_unique_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cycle.jsonl"
            generate_compositional_dataset(
                path, seed=9, train_count=2, dev_count=2,
                locked_test_count=2, candidates_per_role=4,
                noise_rate=0.0, missing_rate=0.0,
            )
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.assertEqual(len(row["target_ids"]), 3)
                self.assertEqual(len(set(row["target_ids"])), 3)
                by_id = {node["node_id"]: node for node in row["nodes"]}
                self.assertEqual(
                    [by_id[node_id]["node_type"] for node_id in row["target_ids"]],
                    ["r0", "r1", "r2"],
                )
                self.assertTrue(all(len(node["features"]) == 4 for node in row["nodes"]))

    def test_provenance_hash_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cycle.jsonl"
            generate_compositional_dataset(
                path, seed=3, train_count=2, dev_count=2, locked_test_count=2,
            )
            manifest_path = path.with_suffix(path.suffix + ".manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["rule_families_by_split"]["locked_test"] = ["cycle-forward"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dataset(path, self.roles, 4)


if __name__ == "__main__":
    unittest.main()
