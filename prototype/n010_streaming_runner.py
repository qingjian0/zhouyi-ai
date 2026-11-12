"""File-backed N0.10 runner.

This path performs a metadata preflight, then reopens JSONL for each training
pass and each evaluation split. It deliberately emits compact split fingerprints
instead of retaining per-record IDs or decoded examples in memory.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Sequence

from prototype.n09_learnable_srok import (
    LearnableSROK, LearnableSROKError, Node, RoleSpec, TrainingExample,
)
from prototype.n010_experiment import (
    RUN_SCHEMA, _node_from_json, _streaming_sha256,
)

STREAM_DATASET_SCHEMA = "zhouyi-ai.n010-streaming-dataset-v1"


def _parse_row(item: object, roles: Sequence[RoleSpec], feature_dim: int,
               line_number: int, max_record_bytes: int) -> dict:
    try:
        allowed = {
            "id", "split", "nodes", "target_ids", "rule_family",
            "group_id", "source_group_id", "episode_id",
        }
        required = {"id", "split", "nodes", "target_ids"}
        if not isinstance(item, dict) or not required.issubset(item) or set(item) - allowed:
            raise ValueError("record fields do not match schema")
        example_id, split = item["id"], item["split"]
        if not isinstance(example_id, str) or not example_id.strip():
            raise ValueError("example IDs must be non-empty strings")
        if split not in ("train", "dev", "locked_test"):
            raise ValueError("split must be train, dev, or locked_test")
        family = item.get("rule_family", "unspecified")
        if not isinstance(family, str) or not family.strip():
            raise ValueError("rule_family must be a non-empty string")
        group_ids = {}
        for field in ("group_id", "source_group_id", "episode_id"):
            value = item.get(field)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field} must be a non-empty string")
                group_ids[field] = value
        if not isinstance(item["nodes"], list) or not isinstance(item["target_ids"], list):
            raise ValueError("nodes and target_ids must be lists")
        nodes = tuple(_node_from_json(node) for node in item["nodes"])
        if not nodes or len({node.node_id for node in nodes}) != len(nodes):
            raise ValueError("each row requires non-empty unique nodes")
        if any(len(node.features) != feature_dim for node in nodes):
            raise ValueError("node feature dimension mismatch")
        targets = item["target_ids"]
        if (len(targets) != len(roles) or len(set(targets)) != len(roles)
                or any(not isinstance(target, str) or not target for target in targets)):
            raise ValueError("target IDs must uniquely match role count")
        pools = tuple(tuple(node for node in nodes if
            (not role.allowed_types or node.node_type in role.allowed_types)
            and role.required_tags.issubset(node.tags)) for role in roles)
        if any(not pool for pool in pools):
            raise ValueError("every role requires at least one compatible candidate")
        return {
            "id": example_id, "split": split, "rule_family": family,
            "group_ids": group_ids, "nodes": nodes,
            "target_ids": tuple(targets), "pools": pools,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise LearnableSROKError(f"invalid dataset row {line_number}: {exc}") from exc


def _iter_rows(path: Path, roles: Sequence[RoleSpec], feature_dim: int,
               max_record_bytes: int):
    with path.open("rb") as source:
        for line_number, raw_line in enumerate(source, 1):
            if len(raw_line) > max_record_bytes:
                raise LearnableSROKError(
                    f"dataset row {line_number} exceeds max_record_bytes={max_record_bytes}"
                )
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LearnableSROKError(
                    f"invalid dataset row {line_number}: malformed UTF-8 JSON"
                ) from exc
            yield _parse_row(item, roles, feature_dim, line_number, max_record_bytes)


def scan_stream_dataset(path: str | Path, roles: Sequence[RoleSpec], feature_dim: int,
                        *, max_record_bytes: int = 8 * 1024 * 1024) -> dict:
    """Validate the whole JSONL file with O(1)-row RAM and disk-backed uniqueness indexes."""
    dataset_path = Path(path)
    if (isinstance(max_record_bytes, bool) or not isinstance(max_record_bytes, int)
            or max_record_bytes < 1):
        raise LearnableSROKError("max_record_bytes must be a positive integer")
    digest = _streaming_sha256(dataset_path)
    provenance_path = dataset_path.with_suffix(dataset_path.suffix + ".manifest.json")
    provenance = None
    if provenance_path.exists():
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LearnableSROKError("invalid generation provenance manifest") from exc
        if (not isinstance(provenance, dict)
                or provenance.get("schema") != "zhouyi-ai.n010-synthetic-rule-families-v1"):
            raise LearnableSROKError("unsupported generation provenance schema")
        if provenance.get("dataset_sha256") != digest:
            raise LearnableSROKError("generation provenance dataset hash mismatch")

    # Temporary SQLite indexes keep unique IDs and group memberships off the Python heap.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="zhouyi-n010-index-") as temp_dir:
        db = sqlite3.connect(str(Path(temp_dir) / "index.sqlite3"))
        try:
            db.execute("CREATE TABLE ids (id TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE groups (field TEXT, value TEXT, split TEXT, PRIMARY KEY(field,value))")
            db.execute("CREATE TABLE families (split TEXT, family TEXT, PRIMARY KEY(split,family))")
            counts = {name: 0 for name in ("train", "dev", "locked_test")}
            hashers = {name: hashlib.sha256() for name in counts}
            for row in _iter_rows(dataset_path, roles, feature_dim, max_record_bytes):
                try:
                    db.execute("INSERT INTO ids(id) VALUES (?)", (row["id"],))
                except sqlite3.IntegrityError as exc:
                    raise LearnableSROKError("example IDs must be unique non-empty strings") from exc
                split = row["split"]
                counts[split] += 1
                encoded_id = row["id"].encode("utf-8")
                hashers[split].update(len(encoded_id).to_bytes(8, "big"))
                hashers[split].update(encoded_id)
                db.execute("INSERT OR IGNORE INTO families(split,family) VALUES (?,?)",
                           (split, row["rule_family"]))
                for field, value in row["group_ids"].items():
                    existing = db.execute(
                        "SELECT split FROM groups WHERE field=? AND value=?", (field, value)
                    ).fetchone()
                    if existing and existing[0] != split:
                        raise LearnableSROKError(
                            f"{field} leakage between {existing[0]} and {split} splits"
                        )
                    db.execute("INSERT OR IGNORE INTO groups(field,value,split) VALUES (?,?,?)",
                               (field, value, split))
            db.commit()
            if not all(counts.values()):
                raise LearnableSROKError("train, dev, and locked_test must all be non-empty")
            family_map = {
                name: [r[0] for r in db.execute(
                    "SELECT family FROM families WHERE split=? ORDER BY family", (name,)
                )]
                for name in counts
            }
            group_counts = {
                field: {
                    name: db.execute(
                        "SELECT COUNT(*) FROM groups WHERE field=? AND split=?", (field, name)
                    ).fetchone()[0]
                    for name in counts
                }
                for field in ("group_id", "source_group_id", "episode_id")
            }
        finally:
            db.close()

    if provenance is not None:
        expected = provenance.get("rule_families_by_split")
        if not isinstance(expected, dict) or {
            name: expected.get(name) for name in counts
        } != family_map:
            raise LearnableSROKError("generation provenance rule-family split mismatch")
        held_out = set(family_map["locked_test"])
        if held_out.intersection(family_map["train"]) or held_out.intersection(family_map["dev"]):
            raise LearnableSROKError("generated locked-test rule family leaks into train/dev")

    return {
        "schema": STREAM_DATASET_SCHEMA,
        "sha256": digest,
        "records": sum(counts.values()),
        "split_counts": counts,
        "split_id_sha256": {name: hashers[name].hexdigest() for name in counts},
        "rule_families_by_split": family_map,
        "group_id_counts_by_split": group_counts,
        "feature_dim": feature_dim,
        "roles": [{"name": r.name, "allowed_types": sorted(r.allowed_types),
                   "required_tags": sorted(r.required_tags)} for r in roles],
        "max_record_bytes": max_record_bytes,
        "loader": "sqlite_indexed_reopenable_jsonl",
        "generation_provenance": provenance,
    }


def iter_dataset_split(path: str | Path, roles: Sequence[RoleSpec], feature_dim: int,
                       split: str, *, max_record_bytes: int = 8 * 1024 * 1024):
    if split not in ("train", "dev", "locked_test"):
        raise LearnableSROKError("unknown dataset split")
    for row in _iter_rows(Path(path), roles, feature_dim, max_record_bytes):
        if row["split"] == split:
            yield row


def _evaluate_stream(model: LearnableSROK, rows_factory, *,
                     max_expansions: int, search_strategy: str, beam_width: int):
    correct = covered = exhausted = 0
    total = 0
    for row in rows_factory():
        result = model.predict(
            row["nodes"], retrieval_mode="joint", search_strategy=search_strategy,
            beam_width=beam_width, max_expansions=max_expansions, result_limit=1,
        )
        prediction = None if result.abstained or not result.candidates else tuple(
            node_id for _, node_id in result.candidates[0].role_bindings
        )
        total += 1
        covered += int(prediction is not None)
        exhausted += int(result.budget_exhausted)
        correct += int(prediction == row["target_ids"])
    if not total:
        raise LearnableSROKError("evaluation split must not be empty")
    return {
        "search_strategy": search_strategy, "beam_width": beam_width,
        "examples": total, "exact_match_accuracy": correct / total,
        "coverage": covered / total, "abstention_rate": 1.0 - covered / total,
        "budget_exhaustion_rate": exhausted / total,
        "covered_accuracy": correct / covered if covered else 0.0,
    }


def run_streaming_experiment(dataset_path: str | Path, roles: Sequence[RoleSpec],
                             feature_dim: int, output_path: str | Path, *,
                             epochs: int = 20, learning_rate: float = 0.2,
                             l2: float = 1e-4, max_assignments_per_example: int = 4096,
                             max_expansions: int = 4096, beam_width: int = 64,
                             max_record_bytes: int = 8 * 1024 * 1024,
                             seed: int = 0, git_sha: str = "unknown",
                             resume: bool = False) -> dict:
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise LearnableSROKError("epochs must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise LearnableSROKError("seed must be a non-negative integer")
    if not isinstance(git_sha, str) or not git_sha.strip():
        raise LearnableSROKError("git_sha must be a non-empty string")
    dataset = Path(dataset_path)
    manifest = scan_stream_dataset(
        dataset, roles, feature_dim, max_record_bytes=max_record_bytes
    )
    config = {
        "epochs": epochs, "learning_rate": learning_rate, "l2": l2,
        "max_assignments_per_example": max_assignments_per_example,
        "max_expansions": max_expansions, "beam_width": beam_width,
        "max_record_bytes": max_record_bytes, "seed": seed, "git_sha": git_sha,
        "seed_semantics": "recorded_only_no_stochastic_operations",
        "runner": "file_backed_reopenable",
    }
    output = Path(output_path)
    history = []
    completed_epochs = 0
    if resume:
        if not output.exists():
            raise LearnableSROKError("resume checkpoint does not exist")
        try:
            bundle = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LearnableSROKError("invalid resume checkpoint") from exc
        if bundle.get("schema") != RUN_SCHEMA or bundle.get("dataset_manifest") != manifest:
            raise LearnableSROKError("resume dataset/schema does not match")
        saved = bundle.get("config", {})
        if {k: v for k, v in saved.items() if k != "epochs"} != {
            k: v for k, v in config.items() if k != "epochs"
        }:
            raise LearnableSROKError("resume configuration does not match")
        model = LearnableSROK.from_checkpoint_json(bundle["model_checkpoint"])
        history = list(bundle.get("loss_history", []))
        completed_epochs = bundle.get("completed_epochs", 0)
        if isinstance(completed_epochs, bool) or not isinstance(completed_epochs, int) or completed_epochs < 0:
            raise LearnableSROKError("invalid completed epoch count")
        if epochs < completed_epochs:
            raise LearnableSROKError("requested epochs precede checkpoint progress")
    else:
        model = LearnableSROK(roles, feature_dim)
    if completed_epochs > epochs:
        raise LearnableSROKError("checkpoint has more completed epochs than requested")

    def training_factory():
        for row in iter_dataset_split(
            dataset, roles, feature_dim, "train", max_record_bytes=max_record_bytes
        ):
            yield TrainingExample(row["pools"], row["target_ids"])

    for epoch in range(completed_epochs, epochs):
        history.extend(model.fit_reiterable(
            training_factory, epochs=1, learning_rate=learning_rate, l2=l2,
            max_assignments_per_example=max_assignments_per_example,
        ))
        bundle = {
            "schema": RUN_SCHEMA, "dataset_manifest": manifest, "config": config,
            "completed_epochs": epoch + 1, "loss_history": history,
            "model_checkpoint": model.checkpoint_json(),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(
            bundle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        ) + "\n", encoding="utf-8")
        temporary.replace(output)

    def rows_factory(split):
        return lambda: iter_dataset_split(
            dataset, roles, feature_dim, split, max_record_bytes=max_record_bytes
        )

    dev = _evaluate_stream(
        model, rows_factory("dev"), max_expansions=max_expansions,
        search_strategy="product", beam_width=beam_width,
    )
    dev_beam = _evaluate_stream(
        model, rows_factory("dev"), max_expansions=max_expansions,
        search_strategy="beam", beam_width=beam_width,
    )
    locked = _evaluate_stream(
        model, rows_factory("locked_test"), max_expansions=max_expansions,
        search_strategy="product", beam_width=beam_width,
    )
    locked_beam = _evaluate_stream(
        model, rows_factory("locked_test"), max_expansions=max_expansions,
        search_strategy="beam", beam_width=beam_width,
    )
    report = {
        "schema": RUN_SCHEMA, "dataset_manifest": manifest, "config": config,
        "completed_epochs": epochs, "training_examples": manifest["split_counts"]["train"],
        "loss_history": history, "dev": dev, "dev_beam": dev_beam,
        "locked_test": locked, "locked_test_beam": locked_beam,
        "checkpoint": str(output), "evaluation_mode": "streaming_aggregate_no_prediction_retention",
    }
    report_path = output.with_suffix(output.suffix + ".report.json")
    report_path.write_text(json.dumps(
        report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n", encoding="utf-8")
    return report
