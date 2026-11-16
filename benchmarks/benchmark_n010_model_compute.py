"""In-memory compute benchmark for the N0.10 SROK learner.

This benchmark deliberately excludes JSONL generation/parsing, SQLite indexing,
filesystem I/O, and dev traversal. It measures the model's in-memory training
API (including its feature preparation/validation) and scoring API separately.
It is a synthetic relational-classification microbenchmark, not an LLM benchmark.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

# Support both direct-script and module execution from arbitrary working dirs.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from prototype.n09_learnable_srok import (
    LearnableSROK,
    Node,
    RelationClassificationExample,
    RoleSpec,
)


ROLES = tuple(RoleSpec(f"r{i}", frozenset({f"r{i}"})) for i in range(3))


def build_examples(count: int) -> tuple[RelationClassificationExample, ...]:
    """Build a balanced 3-way parity set; count must be divisible by eight."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 8 or count % 8:
        raise ValueError("count must be a positive multiple of eight")
    examples = []
    for index in range(count):
        bits = tuple(1.0 if (index % 8) & (1 << role) else -1.0 for role in range(3))
        assignment = tuple(
            Node(
                node_id=f"sample-{index}-role-{role}",
                node_type=f"r{role}",
                features=(value,),
            )
            for role, value in enumerate(bits)
        )
        label = 1 if bits[0] * bits[1] * bits[2] > 0 else -1
        examples.append(RelationClassificationExample(assignment, label))
    return tuple(examples)


def throughput(count: int, epochs: int, elapsed_seconds: float) -> dict[str, float]:
    if elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive")
    return {
        "training_example_epochs_per_second": round(count * epochs / elapsed_seconds, 3),
        "training_epochs_per_second": round(epochs / elapsed_seconds, 3),
    }


def run_case(count: int, epochs: int, repeats: int) -> dict:
    examples = build_examples(count)
    train_durations = []
    scoring_durations = []
    final_losses = []
    accuracies = []

    for _ in range(repeats):
        model = LearnableSROK(ROLES, feature_dim=1)
        started = time.perf_counter()
        history = model.fit_relation_classifier(
            examples, epochs=epochs, learning_rate=0.1,
            l2=1e-4, interaction_order=3,
        )
        train_durations.append(time.perf_counter() - started)
        final_losses.append(history[-1])

        started = time.perf_counter()
        correct = 0
        for row in examples:
            probability = model.predict_relation_probability(
                row.assignment, interaction_order=3
            )
            correct += int((1 if probability >= 0.5 else -1) == row.label)
        scoring_durations.append(time.perf_counter() - started)
        accuracies.append(correct / count)

    train_elapsed = statistics.median(train_durations)
    scoring_elapsed = statistics.median(scoring_durations)
    return {
        "examples": count,
        "epochs": epochs,
        "repeats": repeats,
        "median_training_seconds": round(train_elapsed, 6),
        **throughput(count, epochs, train_elapsed),
        "median_scoring_seconds": round(scoring_elapsed, 6),
        "scoring_assignments_per_second": round(count / scoring_elapsed, 3),
        "final_loss_median": round(statistics.median(final_losses), 8),
        "training_accuracy_median": round(statistics.median(accuracies), 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[8, 64, 256, 1024])
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.epochs < 1 or args.repeats < 1:
        parser.error("epochs and repeats must be positive")
    if any(size < 8 or size % 8 for size in args.sizes):
        parser.error("every size must be a positive multiple of eight")

    results = [
        run_case(size, args.epochs, args.repeats)
        for size in args.sizes
    ]
    print(json.dumps({
        "benchmark": "n010_srok_in_memory_model_compute",
        "model": "LearnableSROK",
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "implementation": platform.python_implementation(),
        },
        "measurement_scope": (
            "in-memory model fit and score APIs; excludes data generation, "
            "JSONL parsing, SQLite indexing, filesystem I/O, and dev traversal"
        ),
        "task": "balanced synthetic three-role parity classification",
        "feature_dim": 1,
        "interaction_order": 3,
        "measurements": results,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
