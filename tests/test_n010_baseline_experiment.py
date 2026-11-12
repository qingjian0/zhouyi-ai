import json
import tempfile
import unittest
from pathlib import Path

from prototype.n09_learnable_srok import RoleSpec
from prototype.n010_baseline_experiment import run_comparison
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
                dataset, roles, 4, output, latent_dim=2, seed=7,
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
            self.assertEqual(report["models"]["parameter_matched_mlp"]["parameter_count"], 25)
            self.assertEqual(report["models"]["parameter_matched_low_rank_tensor"]["parameter_count"], 25)
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema"], "zhouyi-ai.n010-baseline-comparison-v1")

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
