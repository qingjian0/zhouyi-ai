import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_native_dataset import build_training_corpus
from prototype.classiang_native_learning import train_and_evaluate_role_model


def _dataset_record(name, source_id):
    text = "moves water; supports bridge; stops water"
    spans = ("moves water", "supports bridge", "stops water")
    offsets = []
    for phrase in spans:
        start = text.index(phrase)
        offsets.append((start, start + len(phrase)))
    return {
        "observation_id": name,
        "subject_id": f"subject:{name}",
        "domain": "mechanics",
        "source_id": source_id,
        "group_id": f"group:{name}",
        "text": text,
        "annotations": [
            {
                "start_char": offsets[0][0], "end_char": offsets[0][1],
                "dimension": "function", "value": "moves-water",
                "purposes": ["recognition"],
            },
            {
                "start_char": offsets[1][0], "end_char": offsets[1][1],
                "dimension": "relation", "value": "supports-bridge",
                "purposes": ["recognition"],
            },
        ],
        "negative_annotations": [
            {"start_char": offsets[2][0], "end_char": offsets[2][1]},
        ],
    }


def _write_manifest(root):
    split_rows = (
        ("train-a", "source-a", "family-a", "train"),
        ("train-b", "source-b", "family-b", "train"),
        ("dev-c", "source-c", "family-c", "dev"),
        ("test-d", "source-d", "family-d", "locked_test"),
    )
    examples = []
    sources = []
    groups = []
    for name, source_id, family_id, split in split_rows:
        examples.append(_dataset_record(name, source_id))
        sources.append({
            "source_id": source_id,
            "source_family_id": family_id,
            "source_uri": f"https://example.test/{source_id}",
            "license_id": "CC-BY-4.0",
            "license_verified": True,
            "training_use_allowed": True,
        })
        groups.append({
            "group_id": f"group:{name}",
            "source_id": source_id,
            "split": split,
            "annotation_status": "human_reviewed",
        })
    dataset = {"schema_version": 1, "examples": examples}
    raw = json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode("utf-8")
    (root / "dataset.json").write_bytes(raw)
    manifest = {
        "schema_version": 1,
        "dataset": {
            "path": "dataset.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "split_policy": "source_family_disjoint_v1",
        "sources": sources,
        "groups": groups,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


class NativeDatasetBuilderTests(unittest.TestCase):
    def test_exports_only_train_split_and_produces_trainable_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = _write_manifest(Path(directory))
            graph, labels, report = build_training_corpus(manifest)
        self.assertEqual(report["train_records_used"], 2)
        self.assertEqual(report["excluded_dev_records"], 1)
        self.assertEqual(report["excluded_locked_test_records"], 1)
        self.assertFalse(report["locked_test_loaded_into_learner_artifact"])
        self.assertEqual({row.source_family for row in labels}, {"family-a", "family-b"})
        self.assertTrue(all(
            item.source_family in {"family-a", "family-b"}
            for item in graph.evidence
        ))
        self.assertGreater(report["positive_examples"], 0)
        self.assertGreater(report["negative_examples"], 0)
        model, evaluation = train_and_evaluate_role_model(
            graph, labels, seed=7, dimension=8, epochs=30,
        )
        self.assertGreater(model.trained_examples, 0)
        self.assertTrue(evaluation["source_family_disjoint"])

    def test_rejects_record_pair_budget_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = _write_manifest(Path(directory))
            with self.assertRaisesRegex(ValueError, "max_pairs_per_record"):
                build_training_corpus(manifest, max_pairs_per_record=1)


if __name__ == "__main__":
    unittest.main()
