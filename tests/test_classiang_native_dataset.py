import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from prototype.classiang_native_dataset import build_training_corpus
from prototype.classiang_native_train import run_native_training
from prototype.classiang_native_learning import (
    NativeRoleBindingModel, graph_from_json, labels_from_jsonl, train_and_evaluate_role_model,
)


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
        ("train-a1", "source-a", "family-a", "train"),
        ("train-a2", "source-a", "family-a", "train"),
        ("train-b1", "source-b", "family-b", "train"),
        ("train-b2", "source-b", "family-b", "train"),
        ("dev-c1", "source-c", "family-c", "dev"),
        ("dev-c2", "source-c", "family-c", "dev"),
        ("test-d", "source-d", "family-d", "locked_test"),
    )
    examples = []
    sources_by_id = {}
    groups = []
    for name, source_id, family_id, split in split_rows:
        examples.append(_dataset_record(name, source_id))
        sources_by_id[source_id] = {
            "source_id": source_id,
            "source_family_id": family_id,
            "source_uri": f"https://example.test/{source_id}",
            "license_id": "CC-BY-4.0",
            "license_verified": True,
            "training_use_allowed": True,
        }
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
        "sources": list(sources_by_id.values()),
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
        self.assertEqual(report["records_used"], 4)
        self.assertEqual(report["excluded_dev_records"], 2)
        self.assertEqual(report["excluded_locked_test_records"], 1)
        self.assertFalse(report["locked_test_loaded_into_learner_artifact"])
        self.assertEqual({row.source_family for row in labels}, {"family-a", "family-b"})
        self.assertTrue(all(
            item.source_family in {"family-a", "family-b"}
            for item in graph.evidence
        ))
        self.assertGreater(report["positive_examples"], 0)
        self.assertGreater(report["negative_examples"], 0)
        self.assertEqual(report["negative_sampling"], "cross_observation_same_source_family_weak_negative")
        relation_map = {row.relation_id: row for row in graph.relations}
        self.assertEqual({row.relation_type for row in graph.relations}, {"has_aspect"})
        for row in labels:
            subjects = {
                dict(relation_map[relation_id].roles)["subject"]
                for relation_id in row.relation_ids
            }
            self.assertEqual(len(subjects), 1 if row.label == 1 else 2)
        model, evaluation = train_and_evaluate_role_model(
            graph, labels, seed=7, dimension=8, epochs=30,
        )
        self.assertGreater(model.trained_examples, 0)
        self.assertTrue(evaluation["source_family_disjoint"])
        self.assertTrue(evaluation["shared_symbol_ratio_diagnostic"]["label_defining_in_current_exporter"])
        self.assertIn("shared-subject overlap", evaluation["shared_symbol_ratio_diagnostic"]["interpretation"])
        self.assertIn("validation_vocabulary_coverage", evaluation)

    def test_cli_exports_round_trip_compatible_training_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _write_manifest(root)
            graph_path = root / "out" / "graph.json"
            labels_path = root / "out" / "labels.jsonl"
            report_path = root / "out" / "report.json"
            subprocess.run(
                [
                    sys.executable, "-m", "prototype.classiang_native_dataset",
                    str(manifest), "--graph-out", str(graph_path),
                    "--labels-out", str(labels_path), "--report-out", str(report_path),
                ],
                check=True, capture_output=True, text=True,
            )
            graph = graph_from_json(graph_path)
            labels = labels_from_jsonl(labels_path)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            graph_digest = hashlib.sha256(graph_path.read_bytes()).hexdigest()
            labels_digest = hashlib.sha256(labels_path.read_bytes()).hexdigest()
        graph.validate()
        self.assertTrue(labels)
        self.assertEqual(report["graph_sha256"], graph_digest)
        self.assertEqual(report["labels_sha256"], labels_digest)
        self.assertEqual({row.source_family for row in labels}, {"family-a", "family-b"})

    def test_one_command_runs_isolated_gold_to_checkpoint_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _write_manifest(root)
            graph_path = root / "out" / "graph.json"
            labels_path = root / "out" / "labels.jsonl"
            dataset_report = root / "out" / "dataset-report.json"
            validation_graph = root / "out" / "dev-graph.json"
            validation_labels = root / "out" / "dev-labels.jsonl"
            validation_dataset_report = root / "out" / "dev-dataset-report.json"
            checkpoint = root / "out" / "model.json"
            training_report = root / "out" / "training-report.json"
            subprocess.run(
                [
                    sys.executable, "-m", "prototype.classiang_native_train",
                    str(manifest), "--graph-out", str(graph_path),
                    "--labels-out", str(labels_path),
                    "--dataset-report", str(dataset_report),
                    "--validation-graph-out", str(validation_graph),
                    "--validation-labels-out", str(validation_labels),
                    "--validation-dataset-report", str(validation_dataset_report),
                    "--checkpoint", str(checkpoint),
                    "--training-report", str(training_report),
                    "--epochs", "30", "--dimension", "8",
                ],
                check=True, capture_output=True, text=True,
            )
            model = NativeRoleBindingModel.load(checkpoint)
            dataset_summary = json.loads(dataset_report.read_text(encoding="utf-8"))
            dev_summary = json.loads(validation_dataset_report.read_text(encoding="utf-8"))
            train_summary = json.loads(training_report.read_text(encoding="utf-8"))
        self.assertGreater(model.trained_examples, 0)
        self.assertEqual(model.dimension, 8)
        self.assertEqual(dataset_summary["excluded_locked_test_records"], 1)
        self.assertEqual(dev_summary["exported_split"], "dev")
        self.assertTrue(train_summary["source_family_disjoint"])
        self.assertEqual(train_summary["validation_mode"], "manifest_dev_split")
        self.assertEqual(train_summary["model_type"], "classiang-native-role-binding-v1")

    def test_invalid_gold_manifest_stops_before_checkpoint_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _write_manifest(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["dataset"]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            checkpoint = root / "out" / "model.json"
            with self.assertRaises(subprocess.CalledProcessError):
                run_native_training(
                    manifest,
                    graph_out=root / "out" / "graph.json",
                    labels_out=root / "out" / "labels.jsonl",
                    dataset_report=root / "out" / "dataset-report.json",
                    validation_graph_out=root / "out" / "dev-graph.json",
                    validation_labels_out=root / "out" / "dev-labels.jsonl",
                    validation_dataset_report=root / "out" / "dev-dataset-report.json",
                    checkpoint=checkpoint,
                    training_report=root / "out" / "training-report.json",
                    epochs=10, dimension=8,
                )
            self.assertFalse(checkpoint.exists())
            self.assertFalse((root / "out" / "training-report.json").exists())

    def test_rejects_record_pair_budget_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = _write_manifest(Path(directory))
            with self.assertRaisesRegex(ValueError, "max_pairs_per_record"):
                build_training_corpus(manifest, max_pairs_per_record=1)


if __name__ == "__main__":
    unittest.main()
