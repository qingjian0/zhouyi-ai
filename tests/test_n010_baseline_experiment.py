import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_baseline_experiment import main, run_comparison, run_multi_seed_comparison
from prototype.n010_synthetic import generate_compositional_dataset


class N010BaselineExperimentTests(unittest.TestCase):
    def test_comparison_runs_all_models_on_identical_splits(self):
        roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
            for name in ("r0", "r1", "r2")
        )
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "cycle.jsonl"
            output = Path(directory) / "comparison.json"
            generate_compositional_dataset(
                dataset, seed=101, train_count=5, dev_count=2,
                locked_test_count=2, candidates_per_role=2,
                noise_rate=0.0, missing_rate=0.0,
            )
            report = run_comparison(
                dataset, roles, 4, output, latent_dim=8, seed=7,
                epochs=3, learning_rate=0.02, max_expansions=8,
            )
            expected = {
                "learnable_xiang", "fixed_random_xiang",
                "parameter_matched_mlp", "parameter_matched_low_rank_tensor",
            }
            self.assertEqual(set(report["models"]), expected)
            self.assertEqual(report["config"]["train_relation_examples"], 40)
            self.assertEqual(report["models"]["learnable_xiang"]["dev"]["examples"], 2)
            self.assertEqual(report["models"]["learnable_xiang"]["locked_test"]["examples"], 2)
            self.assertEqual(report["models"]["parameter_matched_mlp"]["parameter_count"], 99)
            self.assertEqual(report["models"]["parameter_matched_low_rank_tensor"]["parameter_count"], 97)
            self.assertEqual(report["models"]["learnable_xiang"]["total_parameter_count"], 96)
            self.assertEqual(report["models"]["learnable_xiang"]["trainable_parameter_count"], 96)
            self.assertEqual(report["models"]["fixed_random_xiang"]["total_parameter_count"], 96)
            self.assertEqual(report["models"]["fixed_random_xiang"]["trainable_parameter_count"], 56)
            self.assertEqual(report["models"]["parameter_matched_mlp"]["trainable_parameter_count"], 99)
            self.assertEqual(
                report["parameter_accounting_policy"]["matched_trainable_group"],
                ["learnable_xiang", "parameter_matched_mlp", "parameter_matched_low_rank_tensor"],
            )
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema"], "zhouyi-ai.n010-baseline-comparison-v1")

    def test_multi_seed_report_aggregates_models_and_intervals(self):
        roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
            for name in ("r0", "r1", "r2")
        )
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "cycle.jsonl"
            output = Path(directory) / "multi.json"
            generate_compositional_dataset(
                dataset, seed=111, train_count=3, dev_count=1,
                locked_test_count=1, candidates_per_role=2,
                noise_rate=0.0, missing_rate=0.0,
            )
            report = run_multi_seed_comparison(
                dataset, roles, 4, output, seeds=(3, 5),
                latent_dim=8, epochs=1, max_expansions=8,
            )
            self.assertEqual(report["seed_count"], 2)
            self.assertEqual(report["seeds"], [3, 5])
            metrics = report["models"]["learnable_xiang"]["locked_test"]["exact_match_accuracy"]
            self.assertEqual(len(metrics["per_seed"]), 2)
            self.assertLessEqual(metrics["ci95_normal"][0], metrics["mean"])
            self.assertGreaterEqual(metrics["ci95_normal"][1], metrics["mean"])
            self.assertTrue(output.exists())
            self.assertTrue((Path(directory) / "multi.seed-3.json").exists())
            self.assertTrue((Path(directory) / "multi.seed-5.json").exists())
            self.assertEqual(report["schema"], "zhouyi-ai.n010-baseline-multiseed-v2")
            paired = report["paired_comparisons"]["locked_test"][
                "learnable_xiang_minus_fixed_random_xiang"
            ]["exact_match_accuracy"]
            self.assertEqual(len(paired["per_seed_delta"]), 2)
            self.assertEqual(len(paired["bootstrap_ci95_percentile"]), 2)
            self.assertEqual(report["bootstrap"]["resamples"], 10000)

    def test_cli_seeds_runs_multi_seed_path(self):
        roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
            for name in ("r0", "r1", "r2")
        )
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "cycle.jsonl"
            output = Path(directory) / "cli.json"
            generate_compositional_dataset(
                dataset, seed=222, train_count=2, dev_count=1,
                locked_test_count=1, candidates_per_role=2,
                noise_rate=0.0, missing_rate=0.0,
            )
            argv = [
                "n010_baseline_experiment", "--dataset", str(dataset),
                "--output", str(output), "--feature-dim", "4",
                "--roles-json", json.dumps([
                    {"name": role.name, "allowed_types": [role.name],
                     "required_tags": ["candidate"]} for role in roles
                ]),
                "--latent-dim", "8", "--epochs", "1", "--max-expansions", "8",
                "--seeds", "2,4",
            ]
            with patch("sys.argv", argv):
                main()
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema"], "zhouyi-ai.n010-baseline-multiseed-v2")
            self.assertEqual(saved["seeds"], [2, 4])

    def test_candidate_expansion_cap_fails_closed(self):
        roles = tuple(
            RoleSpec(name, frozenset({name}), frozenset({"candidate"}))
            for name in ("r0", "r1", "r2")
        )
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "cycle.jsonl"
            generate_compositional_dataset(
                dataset, seed=5, train_count=2, dev_count=1,
                locked_test_count=1, candidates_per_role=3,
            )
            with self.assertRaises(ValueError):
                run_comparison(dataset, roles, 4, Path(directory) / "out.json",
                               latent_dim=2, epochs=1, max_expansions=8)


if __name__ == "__main__":
    unittest.main()
