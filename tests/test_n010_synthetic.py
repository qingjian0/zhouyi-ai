import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prototype.n010_synthetic import generate_dataset
from prototype.n010_experiment import LearnableSROKError, load_dataset


class N010SyntheticRuleFamilyTests(unittest.TestCase):
    def test_generation_is_deterministic_and_families_are_disjoint(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            manifest = generate_dataset(
                first, seed=31, train_count=12, dev_count=5,
                locked_test_count=7, candidates_per_role=4,
                noise_rate=0.2, missing_rate=0.15,
            )
            generate_dataset(
                second, seed=31, train_count=12, dev_count=5,
                locked_test_count=7, candidates_per_role=4,
                noise_rate=0.2, missing_rate=0.15,
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                manifest["dataset_sha256"],
            )
            self.assertEqual(manifest["rule_families_by_split"]["train"], ["parity-even"])
            self.assertEqual(manifest["rule_families_by_split"]["dev"], ["parity-even"])
            self.assertEqual(manifest["rule_families_by_split"]["locked_test"], ["parity-odd"])
            rows = [json.loads(line) for line in first.read_text().splitlines()]
            self.assertEqual(len(rows), 24)
            self.assertEqual(len({row["id"] for row in rows}), len(rows))
            self.assertEqual({row["rule_family"] for row in rows if row["split"] == "locked_test"},
                             {"parity-odd"})
            self.assertEqual({row["rule_family"] for row in rows if row["split"] != "locked_test"},
                             {"parity-even"})

    def test_each_pool_has_both_latent_signs_and_valid_unique_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            generate_dataset(path, seed=7, train_count=2, dev_count=2,
                             locked_test_count=2, candidates_per_role=5,
                             noise_rate=0.0, missing_rate=0.0)
            for line in path.read_text().splitlines():
                row = json.loads(line)
                by_role = {role: [] for role in ("r0", "r1", "r2")}
                for node in row["nodes"]:
                    by_role[node["node_type"]].append(node)
                for pool in by_role.values():
                    self.assertEqual(len(pool), 5)
                    # With no corruption, the observed sign is the latent sign.
                    self.assertEqual({node["features"][0] for node in pool}, {-1.0, 1.0})
                self.assertEqual(len(row["target_ids"]), 3)
                self.assertEqual(len(set(row["target_ids"])), 3)
                selected = [next(node for node in row["nodes"]
                                 if node["node_id"] == node_id)
                            for node_id in row["target_ids"]]
                product = 1
                for node in selected:
                    product *= int(node["features"][0])
                expected = 1 if row["rule_family"] == "parity-even" else -1
                self.assertEqual(product, expected)

    def test_noise_and_missing_evidence_are_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            manifest = generate_dataset(
                path, seed=9, train_count=10, dev_count=2,
                locked_test_count=2, candidates_per_role=3,
                noise_rate=1.0, missing_rate=1.0,
            )
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(manifest["noise_rate"], 1.0)
            self.assertEqual(manifest["missing_rate"], 1.0)
            self.assertTrue(all(node["features"][0] == 0.0 for row in rows for node in row["nodes"]))
            self.assertTrue(all(node["evidence_ids"] == [] for row in rows for node in row["nodes"]))
            self.assertTrue(all(node["features"][3] == 1.0 for row in rows for node in row["nodes"]))


    def test_generated_jsonl_runs_through_n010_runner(self):
        from prototype.n09_learnable_srok import RoleSpec
        from prototype.n010_experiment import run_experiment

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.jsonl"
            generate_dataset(path, seed=19, train_count=18, dev_count=4,
                             locked_test_count=4, candidates_per_role=2,
                             noise_rate=0.0, missing_rate=0.0)
            roles = tuple(
                RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
                for name in ("r0", "r1", "r2")
            )
            report = run_experiment(
                path, roles, 4, Path(directory) / "run.json",
                epochs=2, max_assignments_per_example=16,
                max_expansions=64, beam_width=8, git_sha="synthetic-test",
            )
            self.assertEqual(report["training_examples"], 18)
            self.assertEqual(report["dataset_manifest"]["rule_families_by_split"]["locked_test"],
                             ["parity-odd"])
            self.assertEqual(
                report["dataset_manifest"]["generation_provenance"]["dataset_sha256"],
                report["dataset_manifest"]["sha256"],
            )
            self.assertEqual(report["locked_test"]["examples"], 4)


    def test_runner_rejects_tampered_generation_family_manifest(self):
        from prototype.n09_learnable_srok import RoleSpec

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.jsonl"
            generate_dataset(path, seed=23, train_count=2, dev_count=2,
                             locked_test_count=2, candidates_per_role=2)
            sidecar = path.with_suffix(path.suffix + ".manifest.json")
            manifest = json.loads(sidecar.read_text(encoding="utf-8"))
            manifest["rule_families_by_split"]["locked_test"] = ["parity-even"]
            sidecar.write_text(json.dumps(manifest), encoding="utf-8")
            roles = tuple(
                RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
                for name in ("r0", "r1", "r2")
            )
            with self.assertRaises(LearnableSROKError):
                load_dataset(path, roles, 4)

    def test_invalid_generator_parameters_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.jsonl"
            for kwargs in (
                {"train_count": 0}, {"candidates_per_role": 1},
                {"noise_rate": -0.1}, {"missing_rate": 1.1},
            ):
                with self.assertRaises(ValueError):
                    generate_dataset(path, **kwargs)


if __name__ == "__main__":
    unittest.main()
