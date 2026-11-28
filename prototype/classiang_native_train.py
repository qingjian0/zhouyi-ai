"""Run the Gold-admitted native Classiang preparation and learner as isolated processes.

Preparation children validate the manifest and export train and dev artifacts
separately. The learner child receives train artifacts for fitting and dev
artifacts for validation; locked-test labels are never passed to it.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from prototype.classiang_native_learning import graph_from_json, labels_from_jsonl
from prototype.classiang_native_admission import verify_native_gold_admission_jsonl
from prototype.m2_extraction_dataset import DatasetSplit


def _install_gold_labels(
    graph_path: str | Path, source_path: str | Path, target_path: str | Path, *,
    admission_path: str | Path, m1_evidence_db: str | Path, expected_split: DatasetSplit,
) -> dict:
    graph = graph_from_json(graph_path)
    labels = labels_from_jsonl(source_path)
    if not labels:
        raise ValueError(f"Gold annotation file is empty: {source_path}")
    for row in labels:
        row.validate(graph)
        if row.label_basis != "human_reviewed_pair":
            raise ValueError("external annotation files must contain only human_reviewed_pair Gold labels")
    admission_receipts = verify_native_gold_admission_jsonl(
        graph=graph, labels=labels, admission_path=admission_path,
        m1_database=m1_evidence_db, expected_split=expected_split,
    )
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(asdict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in labels),
        encoding="utf-8",
    )
    return {
        "annotation_count": len(labels),
        "positive_count": sum(row.label == 1 for row in labels),
        "explicit_negative_count": sum(row.label == 0 for row in labels),
        "unknown_count": sum(row.label == 2 for row in labels),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "m19_m1_m2_verified_examples": len(admission_receipts),
        "m19_m1_m2_receipts_sha256": hashlib.sha256(
            "".join(item.m2_verification_sha256 for item in admission_receipts).encode("ascii")
        ).hexdigest(),
    }


def _mark_gold_admission(report_path: str | Path, source_path: str | Path, metadata: dict) -> None:
    report_file = Path(report_path)
    report = json.loads(report_file.read_text(encoding="utf-8"))
    report.update({
        "training_eligible": True,
        "label_basis": "human_reviewed_pair",
        "external_gold_annotations": metadata["annotation_count"],
        "positive_examples": metadata["positive_count"],
        "negative_examples": metadata["explicit_negative_count"],
        "unknown_annotations": metadata["unknown_count"],
        "negative_sampling": "independently_reviewed_relation_pair_annotations",
        "label_shortcut_control": {
            "positive_relation_types": report.get("label_shortcut_control", {}).get("positive_relation_types", []),
            "negative_relation_types": report.get("label_shortcut_control", {}).get("negative_relation_types", []),
            "explicit_negative_marker_used": False,
            "shared_subject_overlap_is_label_defining": None,
            "general_composition_supervision": False,
            "requires_independent_reviewed_relation_pair_labels": False,
            "label_source": "external_gold_annotations",
        },
        "external_gold_labels_sha256": metadata["sha256"],
        "candidate_labels_replaced": True,
        "gold_label_source": str(source_path),
    })
    report_file.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_native_training(
    manifest: str | Path,
    *,
    graph_out: str | Path,
    labels_out: str | Path,
    dataset_report: str | Path,
    validation_graph_out: str | Path,
    validation_labels_out: str | Path,
    validation_dataset_report: str | Path,
    checkpoint: str | Path,
    training_report: str | Path,
    seed: int = 17,
    epochs: int = 200,
    learning_rate: float = 0.1,
    validation_fraction: float = 0.2,
    threshold: float = 0.5,
    dimension: int = 16,
    max_pairs_per_record: int = 256,
    train_gold_labels: str | Path | None = None,
    dev_gold_labels: str | Path | None = None,
    m1_evidence_db: str | Path | None = None,
    train_gold_admission: str | Path | None = None,
    dev_gold_admission: str | Path | None = None,
) -> None:
    """Prepare isolated train/dev artifacts, then launch the learner on them."""
    supplied = (train_gold_labels, dev_gold_labels, m1_evidence_db, train_gold_admission, dev_gold_admission)
    if any(value is None for value in supplied) and any(value is not None for value in supplied):
        raise ValueError("train/dev Gold labels, M1 evidence DB, and train/dev admission JSONL must be supplied together")
    python = sys.executable
    preparation = [
        python, "-m", "prototype.classiang_native_dataset", str(manifest),
        "--graph-out", str(graph_out),
        "--labels-out", str(labels_out),
        "--report-out", str(dataset_report),
        "--max-pairs-per-record", str(max_pairs_per_record),
        "--split", "train",
    ]
    subprocess.run(preparation, check=True)
    validation_preparation = [
        python, "-m", "prototype.classiang_native_dataset", str(manifest),
        "--graph-out", str(validation_graph_out),
        "--labels-out", str(validation_labels_out),
        "--report-out", str(validation_dataset_report),
        "--max-pairs-per-record", str(max_pairs_per_record),
        "--split", "dev",
    ]
    subprocess.run(validation_preparation, check=True)
    if train_gold_labels is None:
        raise RuntimeError(
            "training stopped: exporter output contains only unreviewed candidate pairs; "
            "supply --train-gold-labels and --dev-gold-labels with independently adjudicated labels"
        )
    train_metadata = _install_gold_labels(
        graph_out, train_gold_labels, labels_out,
        admission_path=train_gold_admission, m1_evidence_db=m1_evidence_db,
        expected_split=DatasetSplit.TRAIN,
    )
    dev_metadata = _install_gold_labels(
        validation_graph_out, dev_gold_labels, validation_labels_out,
        admission_path=dev_gold_admission, m1_evidence_db=m1_evidence_db,
        expected_split=DatasetSplit.VALIDATION,
    )
    _mark_gold_admission(dataset_report, train_gold_labels, train_metadata)
    _mark_gold_admission(validation_dataset_report, dev_gold_labels, dev_metadata)
    learner = [
        python, "-m", "prototype.classiang_native_learning",
        str(graph_out), str(labels_out),
        "--validation-graph", str(validation_graph_out),
        "--validation-labels", str(validation_labels_out),
        "--model", "role-binding",
        "--checkpoint", str(checkpoint),
        "--report", str(training_report),
        "--seed", str(seed),
        "--epochs", str(epochs),
        "--learning-rate", str(learning_rate),
        "--validation-fraction", str(validation_fraction),
        "--threshold", str(threshold),
        "--dimension", str(dimension),
    ]
    subprocess.run(learner, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--graph-out", default="artifacts/classiang-native-train-graph.json")
    parser.add_argument("--labels-out", default="artifacts/classiang-native-train-labels.jsonl")
    parser.add_argument("--dataset-report", default="artifacts/classiang-native-dataset-report.json")
    parser.add_argument("--validation-graph-out", default="artifacts/classiang-native-dev-graph.json")
    parser.add_argument("--validation-labels-out", default="artifacts/classiang-native-dev-labels.jsonl")
    parser.add_argument("--validation-dataset-report", default="artifacts/classiang-native-dev-dataset-report.json")
    parser.add_argument("--checkpoint", default="artifacts/classiang-native-role-binding.json")
    parser.add_argument("--training-report", default="artifacts/classiang-native-training-report.json")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--dimension", type=int, default=16)
    parser.add_argument("--max-pairs-per-record", type=int, default=256)
    parser.add_argument("--train-gold-labels", help="JSONL of independently reviewed train pair annotations")
    parser.add_argument("--dev-gold-labels", help="JSONL of independently reviewed dev pair annotations")
    parser.add_argument("--m1-evidence-db", help="SQLite M1 immutable evidence database required for Gold admission")
    parser.add_argument("--train-gold-admission", help="JSONL of M19/M2/native evidence mappings for every train label")
    parser.add_argument("--dev-gold-admission", help="JSONL of M19/M2/native evidence mappings for every dev label")
    args = parser.parse_args()
    run_native_training(
        args.manifest,
        graph_out=args.graph_out, labels_out=args.labels_out,
        dataset_report=args.dataset_report,
        validation_graph_out=args.validation_graph_out,
        validation_labels_out=args.validation_labels_out,
        validation_dataset_report=args.validation_dataset_report,
        checkpoint=args.checkpoint,
        training_report=args.training_report, seed=args.seed,
        epochs=args.epochs, learning_rate=args.learning_rate,
        validation_fraction=args.validation_fraction, threshold=args.threshold,
        dimension=args.dimension, max_pairs_per_record=args.max_pairs_per_record,
        train_gold_labels=args.train_gold_labels, dev_gold_labels=args.dev_gold_labels,
        m1_evidence_db=args.m1_evidence_db,
        train_gold_admission=args.train_gold_admission,
        dev_gold_admission=args.dev_gold_admission,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
