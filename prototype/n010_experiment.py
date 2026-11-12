"""Deterministic N0.10 experiment runner with strict split isolation.

Input JSONL records:
{"id":"...","split":"train|dev|locked_test","nodes":[...],"target_ids":["..."]}
The runner trains only on train records; dev and locked_test labels are consumed
only by the evaluator after predictions have been produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Sequence

from prototype.n09_learnable_srok import (
    LearnableSROK, LearnableSROKError, Node, RoleSpec, TrainingExample,
)


DATASET_SCHEMA = "zhouyi-ai.n010-dataset-v1"
RUN_SCHEMA = "zhouyi-ai.n010-run-v1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _node_from_json(value: dict) -> Node:
    try:
        node = Node(
            value["node_id"], value["node_type"], tuple(value["features"]),
            frozenset(value.get("tags", [])), tuple(value.get("evidence_ids", [])),
        )
    except (KeyError, TypeError) as exc:
        raise LearnableSROKError("malformed dataset node") from exc
    return node


def load_dataset(path: str | Path, roles: Sequence[RoleSpec], feature_dim: int):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    rows = []
    seen = set()
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if not isinstance(item, dict) or not {
                "id", "split", "nodes", "target_ids"
            }.issubset(item) or set(item) - {
                "id", "split", "nodes", "target_ids", "rule_family"
            }:
                raise ValueError("record fields do not match schema")
            example_id, split = item["id"], item["split"]
            rule_family = item.get("rule_family", "unspecified")
            if not isinstance(rule_family, str) or not rule_family.strip():
                raise ValueError("rule_family must be a non-empty string")
            if not isinstance(example_id, str) or not example_id.strip() or example_id in seen:
                raise ValueError("example IDs must be unique non-empty strings")
            if split not in ("train", "dev", "locked_test"):
                raise ValueError("split must be train, dev, or locked_test")
            if not isinstance(item["nodes"], list) or not isinstance(item["target_ids"], list):
                raise ValueError("nodes and target_ids must be lists")
            nodes = tuple(_node_from_json(node) for node in item["nodes"])
            if not nodes or len({node.node_id for node in nodes}) != len(nodes):
                raise ValueError("each row requires non-empty unique nodes")
            if any(len(node.features) != feature_dim for node in nodes):
                raise ValueError("node feature dimension mismatch")
            if any(not isinstance(target, str) or not target for target in item["target_ids"]):
                raise ValueError("target IDs must be non-empty strings")
            if len(item["target_ids"]) != len(roles) or len(set(item["target_ids"])) != len(roles):
                raise ValueError("target IDs must uniquely match role count")
            pools = tuple(tuple(node for node in nodes if
                (not role.allowed_types or node.node_type in role.allowed_types)
                and role.required_tags.issubset(node.tags)) for role in roles)
            if any(not pool for pool in pools):
                raise ValueError("every role requires at least one compatible candidate")
            rows.append({
                "id": example_id, "split": split, "rule_family": rule_family, "nodes": nodes,
                "target_ids": tuple(item["target_ids"]), "pools": pools,
            })
            seen.add(example_id)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LearnableSROKError(
                f"invalid dataset row {line_number}: {exc}"
            ) from exc
    if not rows:
        raise LearnableSROKError("dataset is empty")
    splits = {name: [row for row in rows if row["split"] == name]
              for name in ("train", "dev", "locked_test")}
    if not splits["train"] or not splits["dev"] or not splits["locked_test"]:
        raise LearnableSROKError("train, dev, and locked_test must all be non-empty")
    manifest = {
        "schema": DATASET_SCHEMA, "sha256": digest, "records": len(rows),
        "split_ids": {name: [row["id"] for row in group]
                      for name, group in splits.items()},
        "rule_families_by_split": {
            name: sorted({row["rule_family"] for row in group})
            for name, group in splits.items()
        },
        "feature_dim": feature_dim,
        "roles": [{"name": r.name, "allowed_types": sorted(r.allowed_types),
                   "required_tags": sorted(r.required_tags)} for r in roles],
    }
    return splits, manifest


def evaluate(model: LearnableSROK, rows, *, max_expansions: int = 4096):
    correct = covered = abstained = exhausted = 0
    predictions = []
    for row in rows:
        result = model.predict(
            row["nodes"], retrieval_mode="joint", search_strategy="product",
            max_expansions=max_expansions, result_limit=1,
        )
        prediction = None if result.abstained or not result.candidates else tuple(
            node_id for _, node_id in result.candidates[0].role_bindings
        )
        covered += prediction is not None
        abstained += prediction is None
        exhausted += int(result.budget_exhausted)
        correct += int(prediction == row["target_ids"])
        predictions.append({"id": row["id"], "prediction": prediction,
                            "target_match": prediction == row["target_ids"]})
    total = len(rows)
    return {
        "examples": total, "exact_match_accuracy": correct / total,
        "coverage": covered / total, "abstention_rate": abstained / total,
        "budget_exhaustion_rate": exhausted / total,
        "covered_accuracy": correct / covered if covered else 0.0,
        "predictions": predictions,
    }


def run_experiment(dataset_path: str | Path, roles: Sequence[RoleSpec], feature_dim: int,
                   output_path: str | Path, *, epochs: int = 20,
                   learning_rate: float = 0.2, l2: float = 1e-4,
                   max_assignments_per_example: int = 4096,
                   max_expansions: int = 4096, seed: int = 0,
                   git_sha: str = "unknown", resume: bool = False):
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise LearnableSROKError("epochs must be a positive integer")
    splits, dataset_manifest = load_dataset(dataset_path, roles, feature_dim)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise LearnableSROKError("seed must be a non-negative integer")
    if not isinstance(git_sha, str) or not git_sha.strip():
        raise LearnableSROKError("git_sha must be a non-empty string")
    config = {
        "epochs": epochs, "learning_rate": learning_rate, "l2": l2,
        "max_assignments_per_example": max_assignments_per_example,
        "max_expansions": max_expansions, "seed": seed, "git_sha": git_sha,
        "seed_semantics": "recorded_only_no_stochastic_operations",
    }
    output = Path(output_path)
    history = []
    completed_epochs = 0
    if resume:
        if not output.exists():
            raise LearnableSROKError("resume checkpoint does not exist")
        bundle = json.loads(output.read_text(encoding="utf-8"))
        if bundle.get("schema") != RUN_SCHEMA or bundle.get("dataset_manifest") != dataset_manifest:
            raise LearnableSROKError("resume dataset/schema does not match")
        saved_config = bundle.get("config", {})
        if {k: v for k, v in saved_config.items() if k != "epochs"} != {
            k: v for k, v in config.items() if k != "epochs"
        }:
            raise LearnableSROKError("resume configuration does not match")
        model = LearnableSROK.from_checkpoint_json(bundle["model_checkpoint"])
        history = list(bundle["loss_history"])
        completed_epochs = bundle["completed_epochs"]
        if isinstance(completed_epochs, bool) or not isinstance(completed_epochs, int) or completed_epochs < 0:
            raise LearnableSROKError("invalid completed epoch count")
        if epochs < completed_epochs:
            raise LearnableSROKError("requested epochs precede checkpoint progress")
    else:
        model = LearnableSROK(roles, feature_dim)

    training = [TrainingExample(row["pools"], row["target_ids"])
                for row in splits["train"]]
    if completed_epochs > epochs:
        raise LearnableSROKError("checkpoint has more completed epochs than requested")
    # Full-batch gradient descent has no optimizer state. One-epoch checkpoints
    # therefore resume exactly from model weights and the completed epoch count.
    for epoch in range(completed_epochs, epochs):
        history.extend(model.fit(
            training, epochs=1, learning_rate=learning_rate, l2=l2,
            max_assignments_per_example=max_assignments_per_example,
        ))
        bundle = {
            "schema": RUN_SCHEMA, "dataset_manifest": dataset_manifest,
            "config": config, "completed_epochs": epoch + 1,
            "loss_history": history, "model_checkpoint": model.checkpoint_json(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(bundle, sort_keys=True, indent=2,
                                      ensure_ascii=False, allow_nan=False) + "\n",
                          encoding="utf-8")

    dev_metrics = evaluate(model, splits["dev"], max_expansions=max_expansions)
    # Locked labels are read only here, after the model is fully fitted and frozen.
    locked_metrics = evaluate(model, splits["locked_test"], max_expansions=max_expansions)
    report = {
        "schema": RUN_SCHEMA, "dataset_manifest": dataset_manifest,
        "config": config, "completed_epochs": epochs,
        "training_examples": len(training), "loss_history": history,
        "dev": dev_metrics, "locked_test": locked_metrics,
        "checkpoint": str(output),
    }
    report_path = output.with_suffix(output.suffix + ".report.json")
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2,
                                      ensure_ascii=False, allow_nan=False) + "\n",
                           encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Train/evaluate the N0.10 structured learner")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0,
                        help="recorded reproducibility seed; current full-batch learner is deterministic")
    parser.add_argument("--git-sha", required=True,
                        help="source revision used for this experiment")
    parser.add_argument("--max-expansions", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=0.2)
    parser.add_argument("--l2", type=float, default=1e-4)
    parser.add_argument("--feature-dim", type=int, required=True)
    parser.add_argument("--roles-json", required=True,
                        help='JSON list: [{"name":"r0","allowed_types":["r0"],"required_tags":[]}, ...]')
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    role_rows = json.loads(args.roles_json)
    roles = tuple(RoleSpec(row["name"], frozenset(row.get("allowed_types", [])),
                           frozenset(row.get("required_tags", []))) for row in role_rows)
    report = run_experiment(
        args.dataset, roles, args.feature_dim, args.checkpoint,
        epochs=args.epochs, learning_rate=args.learning_rate, l2=args.l2,
        resume=args.resume,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
