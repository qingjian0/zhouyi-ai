import hashlib
import json
from dataclasses import asdict, replace
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
    def test_exports_only_train_split_and_marks_pairs_as_unreviewed_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = _write_manifest(Path(directory))
            graph, labels, report = build_training_corpus(manifest)
        self.assertEqual(report["records_used"], 4)
        self.assertEqual(report["excluded_dev_records"], 2)
        self.assertEqual(report["excluded_locked_test_records"], 1)
        self.assertFalse(report["locked_test_loaded_into_learner_artifact"])
        self.assertEqual({row.source_family for row in labels}, {"family-a", "family-b"})
        self.assertTrue(all(item.source_family in {"family-a", "family-b"} for item in graph.evidence))
        self.assertGreater(report["positive_examples"], 0)
        self.assertGreater(report["negative_examples"], 0)
        self.assertEqual(report["negative_sampling"], "cross_observation_same_source_family_unreviewed_candidate_only")
        self.assertFalse(report["training_eligible"])
        self.assertTrue(all(not row.reviewed for row in labels))
        self.assertTrue(all(row.label_basis == "weak_cooccurrence_proxy" for row in labels))
        relation_map = {row.relation_id: row for row in graph.relations}
        self.assertEqual({row.relation_type for row in graph.relations}, {"has_aspect"})
        for row in labels:
            subjects = {dict(relation_map[rid].roles)["subject"] for rid in row.relation_ids}
            self.assertEqual(len(subjects), 1 if row.label == 1 else 2)
        with self.assertRaisesRegex(ValueError, "human_reviewed_pair"):
            train_and_evaluate_role_model(graph, labels, seed=7, dimension=8, epochs=30)

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

    def test_one_command_refuses_weak_pairs_before_checkpoint_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _write_manifest(root)
            checkpoint = root / "out" / "model.json"
            with self.assertRaises(subprocess.CalledProcessError):
                subprocess.run(
                    [
                        sys.executable, "-m", "prototype.classiang_native_train",
                        str(manifest), "--graph-out", str(root / "out" / "graph.json"),
                        "--labels-out", str(root / "out" / "labels.jsonl"),
                        "--dataset-report", str(root / "out" / "dataset-report.json"),
                        "--validation-graph-out", str(root / "out" / "dev-graph.json"),
                        "--validation-labels-out", str(root / "out" / "dev-labels.jsonl"),
                        "--validation-dataset-report", str(root / "out" / "dev-dataset-report.json"),
                        "--checkpoint", str(checkpoint),
                        "--training-report", str(root / "out" / "training-report.json"),
                        "--epochs", "30", "--dimension", "8",
                    ],
                    check=True, capture_output=True, text=True,
                )
            summary = json.loads((root / "out" / "dataset-report.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["training_eligible"])
            self.assertFalse(checkpoint.exists())
            self.assertFalse((root / "out" / "training-report.json").exists())

    def test_one_command_rejects_pair_labels_without_m19_m1_m2_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _write_manifest(root)
            train_graph, train_candidates, _ = build_training_corpus(manifest, split="train")
            dev_graph, dev_candidates, _ = build_training_corpus(manifest, split="dev")
            train_gold = root / "train-gold.jsonl"
            dev_gold = root / "dev-gold.jsonl"

            # Synthetic reviewer metadata exists only to test pipeline wiring;
            # it is not a claim that generated fixture labels are real Gold data.
            def write_gold(path, candidates):
                rows = [
                    replace(
                        row, reviewed=True, label_basis="human_reviewed_pair",
                        reviewer_id="test-only-reviewer",
                        adjudication_id=f"test-only:{row.example_id}",
                        scope="synthetic-test-fixture",
                        conditions=("synthetic-test-only",),
                    )
                    for row in candidates
                ]
                path.write_text(
                    "".join(json.dumps(asdict(row), sort_keys=True) + "\n" for row in rows),
                    encoding="utf-8",
                )

            write_gold(train_gold, train_candidates)
            write_gold(dev_gold, dev_candidates)
            checkpoint = root / "out" / "model.json"
            training_report = root / "out" / "training-report.json"
            with self.assertRaisesRegex(ValueError, "must be supplied together"):
                run_native_training(
                    manifest,
                    graph_out=root / "out" / "graph.json",
                    labels_out=root / "out" / "labels.jsonl",
                    dataset_report=root / "out" / "dataset-report.json",
                    validation_graph_out=root / "out" / "dev-graph.json",
                    validation_labels_out=root / "out" / "dev-labels.jsonl",
                    validation_dataset_report=root / "out" / "dev-dataset-report.json",
                    checkpoint=checkpoint,
                    training_report=training_report,
                    train_gold_labels=train_gold,
                    dev_gold_labels=dev_gold,
                    epochs=5,
                    dimension=8,
                )
            self.assertFalse(checkpoint.exists())
            self.assertFalse(training_report.exists())
        self.assertGreater(model.trained_examples, 0)
        self.assertTrue(train_report["training_eligible"])
        self.assertTrue(dev_report["training_eligible"])
        self.assertTrue(train_report["candidate_labels_replaced"])
        self.assertEqual(train_report["label_basis"], "human_reviewed_pair")
        self.assertTrue(learner_report["source_family_disjoint"])
        self.assertEqual(learner_report["validation_mode"], "manifest_dev_split")

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
