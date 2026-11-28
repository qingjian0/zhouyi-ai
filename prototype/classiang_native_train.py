"""Run the Gold-admitted native Classiang preparation and learner as isolated processes.

Preparation children validate the manifest and export train and dev artifacts
separately. The learner child receives train artifacts for fitting and dev
artifacts for validation; locked-test labels are never passed to it.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


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
) -> None:
    """Prepare isolated train/dev artifacts, then launch the learner on them."""
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
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
