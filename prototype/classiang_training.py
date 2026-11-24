"""Runnable, reproducible training entry point for the learnable SROK backend.

Input annotations and labels are supplied by the dataset author; this module
does not infer semantic features from raw text or claim autonomous perception.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any

from prototype.n09_learnable_srok import (
    LearnableSROK, Node, RoleSpec, TrainingExample,
)


def _require_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise ValueError(f"{where}: missing={missing}, extra={extra}")


def load_dataset(path: str | Path) -> tuple[tuple[RoleSpec, ...], tuple[TrainingExample, ...], str]:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("dataset must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("dataset root must be an object")
    _require_keys(payload, {"schema_version", "feature_dim", "roles", "examples"}, "dataset")
    if payload["schema_version"] != 1 or isinstance(payload["schema_version"], bool):
        raise ValueError("unsupported dataset schema_version")
    dim = payload["feature_dim"]
    if isinstance(dim, bool) or not isinstance(dim, int) or dim < 1:
        raise ValueError("feature_dim must be a positive integer")
    if not isinstance(payload["roles"], list) or len(payload["roles"]) < 2:
        raise ValueError("roles must contain at least two entries")
    roles = []
    for index, item in enumerate(payload["roles"]):
        if not isinstance(item, dict):
            raise ValueError(f"roles[{index}] must be an object")
        _require_keys(item, {"name", "allowed_types", "required_tags"}, f"roles[{index}]")
        if not isinstance(item["name"], str):
            raise ValueError(f"roles[{index}].name must be text")
        if not isinstance(item["allowed_types"], list) or not isinstance(item["required_tags"], list):
            raise ValueError(f"roles[{index}] type/tag constraints must be lists")
        roles.append(RoleSpec(item["name"], frozenset(item["allowed_types"]),
                              frozenset(item["required_tags"])))
    if not isinstance(payload["examples"], list) or len(payload["examples"]) < 2:
        raise ValueError("examples must contain at least two labeled examples")
    examples = []
    for index, item in enumerate(payload["examples"]):
        where = f"examples[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be an object")
        _require_keys(item, {"role_candidates", "target_ids"}, where)
        pools_raw = item["role_candidates"]
        if not isinstance(pools_raw, list) or len(pools_raw) != len(roles):
            raise ValueError(f"{where}.role_candidates must match the role count")
        pools = []
        for role_index, pool_raw in enumerate(pools_raw):
            if not isinstance(pool_raw, list) or not pool_raw:
                raise ValueError(f"{where}.role_candidates[{role_index}] must be non-empty")
            pool = []
            for node_index, node_raw in enumerate(pool_raw):
                node_where = f"{where}.role_candidates[{role_index}][{node_index}]"
                if not isinstance(node_raw, dict):
                    raise ValueError(f"{node_where} must be an object")
                _require_keys(node_raw, {"node_id", "node_type", "features", "tags", "evidence_ids"}, node_where)
                if not isinstance(node_raw["features"], list) or len(node_raw["features"]) != dim:
                    raise ValueError(f"{node_where}.features must have feature_dim values")
                if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
                       for x in node_raw["features"]):
                    raise ValueError(f"{node_where}.features must be finite numbers")
                if not isinstance(node_raw["tags"], list) or not isinstance(node_raw["evidence_ids"], list):
                    raise ValueError(f"{node_where}.tags/evidence_ids must be lists")
                pool.append(Node(
                    node_raw["node_id"], node_raw["node_type"],
                    tuple(float(x) for x in node_raw["features"]),
                    frozenset(node_raw["tags"]), tuple(node_raw["evidence_ids"]),
                ))
            pools.append(tuple(pool))
        targets = item["target_ids"]
        if not isinstance(targets, list) or len(targets) != len(roles):
            raise ValueError(f"{where}.target_ids must match the role count")
        examples.append(TrainingExample(tuple(pools), tuple(targets)))
    return tuple(roles), tuple(examples), digest


def train_and_evaluate(
    roles: tuple[RoleSpec, ...],
    examples: tuple[TrainingExample, ...],
    *,
    dataset_sha256: str,
    validation_fraction: float = 0.2,
    seed: int = 17,
    epochs: int = 100,
    learning_rate: float = 0.1,
    l2: float = 1e-4,
    max_assignments_per_example: int = 4096,
) -> tuple[LearnableSROK, dict[str, Any]]:
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1")
    if len(examples) < 2:
        raise ValueError("at least two examples are required for train/validation split")
    indices = list(range(len(examples)))
    random.Random(seed).shuffle(indices)
    validation_count = min(len(indices) - 1, max(1, round(len(indices) * validation_fraction)))
    validation_ids = set(indices[:validation_count])
    train_rows = tuple(row for i, row in enumerate(examples) if i not in validation_ids)
    validation_rows = tuple(row for i, row in enumerate(examples) if i in validation_ids)
    feature_dim = len(examples[0].role_candidates[0][0].features)
    if any(len(node.features) != feature_dim
           for row in examples for pool in row.role_candidates for node in pool):
        raise ValueError("all nodes must use the same feature dimension")
    model = LearnableSROK(roles, feature_dim)
    loss = model.fit(
        train_rows, epochs=epochs, learning_rate=learning_rate, l2=l2,
        max_assignments_per_example=max_assignments_per_example,
    )
    correct = 0
    abstentions = 0
    evaluated = 0
    for row in validation_rows:
        nodes = tuple(node for pool in row.role_candidates for node in pool)
        prediction = model.predict(
            nodes, retrieval_mode="joint", search_strategy="product",
            max_expansions=max_assignments_per_example, result_limit=1,
        )
        evaluated += 1
        if prediction.abstained or prediction.budget_exhausted or not prediction.candidates:
            abstentions += 1
            continue
        predicted_ids = tuple(node_id for _, node_id in prediction.candidates[0].role_bindings)
        correct += int(predicted_ids == row.target_ids)
    checkpoint = model.checkpoint_json()
    # Verify that the emitted artifact is loadable before reporting success.
    restored = LearnableSROK.from_checkpoint_json(checkpoint)
    if restored.weights != model.weights or restored.training_steps != model.training_steps:
        raise RuntimeError("checkpoint round-trip changed model state")
    report = {
        "format": "zhouyi-ai.classiang-training-report",
        "schema_version": 1,
        "dataset_sha256": dataset_sha256,
        "seed": seed,
        "train_examples": len(train_rows),
        "validation_examples": evaluated,
        "epochs": epochs,
        "training_steps": model.training_steps,
        "initial_loss": loss[0],
        "final_loss": loss[-1],
        "validation_exact_match": correct / evaluated,
        "validation_correct": correct,
        "validation_abstentions": abstentions,
        "checkpoint_sha256": hashlib.sha256(checkpoint.encode("utf-8")).hexdigest(),
        "claim_boundary": (
            "Supervised structured-relation learner only. Labels and feature vectors "
            "are supplied by the dataset; this is not raw-text/multimodal perception "
            "or proof of open-domain semantic generalization."
        ),
    }
    return model, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and validate the learnable SROK backend.")
    parser.add_argument("dataset", help="UTF-8 JSON dataset")
    parser.add_argument("--checkpoint", default="classiang-srok.json")
    parser.add_argument("--report", default="classiang-training-report.json")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--max-assignments", type=int, default=4096)
    args = parser.parse_args()
    roles, examples, digest = load_dataset(args.dataset)
    model, report = train_and_evaluate(
        roles, examples, dataset_sha256=digest,
        validation_fraction=args.validation_fraction, seed=args.seed,
        epochs=args.epochs, learning_rate=args.learning_rate, l2=args.l2,
        max_assignments_per_example=args.max_assignments,
    )
    Path(args.checkpoint).write_text(model.checkpoint_json() + "\n", encoding="utf-8")
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
