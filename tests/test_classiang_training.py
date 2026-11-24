"""Regression tests for the end-to-end structured SROK training entry point."""
import json
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_training import load_dataset, train_and_evaluate


def sample_dataset():
    return {
        "schema_version": 1,
        "feature_dim": 1,
        "roles": [
            {"name": "cause", "allowed_types": ["cause"], "required_tags": ["reviewed"]},
            {"name": "effect", "allowed_types": ["effect"], "required_tags": ["reviewed"]},
        ],
        "examples": [
            {
                "role_candidates": [
                    [
                        {"node_id": f"c{i}", "node_type": "cause", "features": [1.0],
                         "tags": ["reviewed"], "evidence_ids": [f"e-c{i}"]},
                        {"node_id": f"cx{i}", "node_type": "cause", "features": [0.0],
                         "tags": ["reviewed"], "evidence_ids": [f"e-cx{i}"]},
                    ],
                    [
                        {"node_id": f"e{i}", "node_type": "effect", "features": [1.0],
                         "tags": ["reviewed"], "evidence_ids": [f"e-e{i}"]},
                        {"node_id": f"ex{i}", "node_type": "effect", "features": [0.0],
                         "tags": ["reviewed"], "evidence_ids": [f"e-ex{i}"]},
                    ],
                ],
                "target_ids": [f"c{i}", f"e{i}"],
            }
            for i in range(10)
        ],
    }


class ClassiangTrainingTests(unittest.TestCase):
    def test_load_train_validate_and_checkpoint_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_path = Path(directory) / "dataset.json"
            dataset_path.write_text(json.dumps(sample_dataset()), encoding="utf-8")
            roles, examples, digest = load_dataset(dataset_path)
            model, report = train_and_evaluate(
                roles, examples, dataset_sha256=digest, seed=5, epochs=30,
            )
            self.assertEqual(report["train_examples"] + report["validation_examples"], 10)
            self.assertEqual(report["training_steps"], 30)
            self.assertEqual(model.training_steps, 30)
            self.assertEqual(len(report["dataset_sha256"]), 64)
            self.assertEqual(len(report["checkpoint_sha256"]), 64)
            self.assertGreaterEqual(report["validation_exact_match"], 0.0)
            self.assertLessEqual(report["validation_exact_match"], 1.0)

    def test_dataset_rejects_unknown_fields(self):
        payload = sample_dataset()
        payload["unreviewed_magic"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "extra"):
                load_dataset(path)

    def test_training_requires_validation_split(self):
        payload = sample_dataset()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            roles, examples, digest = load_dataset(path)
            with self.assertRaises(ValueError):
                train_and_evaluate(
                    roles, examples, dataset_sha256=digest,
                    validation_fraction=0.0,
                )


if __name__ == "__main__":
    unittest.main()
