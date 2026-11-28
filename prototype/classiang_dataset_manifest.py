"""Auditable admission gate for reviewed Classiang training corpora.

This validates provenance and group/source-family splits before a corpus is
eligible for training. It does not create labels or certify semantic truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from prototype.classiang_learning import load_records


_SPLITS = {"train", "dev", "locked_test"}
_TOP_KEYS = {"schema_version", "dataset", "split_policy", "sources", "groups"}


def _object(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{where} must contain exactly: {', '.join(sorted(keys))}")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} must be non-empty text")
    return value.strip()


def _sha256(value: Any, where: str) -> str:
    value = _text(value, where)
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{where} must be a lowercase SHA-256 digest")
    return value


def validate_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Validate one dataset against its provenance and split manifest."""
    manifest_file = Path(manifest_path).resolve()
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest must be readable UTF-8 JSON") from exc
    _object(manifest, _TOP_KEYS, "manifest")
    if manifest["schema_version"] != 1 or isinstance(manifest["schema_version"], bool):
        raise ValueError("unsupported manifest schema_version")
    if manifest["split_policy"] != "source_family_disjoint_v1":
        raise ValueError("split_policy must be source_family_disjoint_v1")

    dataset = _object(manifest["dataset"], {"path", "sha256"}, "dataset")
    relative_path = _text(dataset["path"], "dataset.path")
    dataset_path = Path(relative_path)
    if dataset_path.is_absolute() or ".." in dataset_path.parts:
        raise ValueError("dataset.path must be a safe path relative to the manifest")
    dataset_path = (manifest_file.parent / dataset_path).resolve()
    if manifest_file.parent not in dataset_path.parents:
        raise ValueError("dataset.path escapes the manifest directory")
    try:
        raw = dataset_path.read_bytes()
    except OSError as exc:
        raise ValueError("dataset.path cannot be read") from exc
    digest = hashlib.sha256(raw).hexdigest()
    expected_digest = _sha256(dataset["sha256"], "dataset.sha256")
    if digest != expected_digest:
        raise ValueError("dataset SHA-256 mismatch")

    sources_raw = manifest["sources"]
    groups_raw = manifest["groups"]
    if not isinstance(sources_raw, list) or not sources_raw:
        raise ValueError("sources must be a non-empty list")
    if not isinstance(groups_raw, list) or not groups_raw:
        raise ValueError("groups must be a non-empty list")

    sources: dict[str, dict[str, str]] = {}
    source_keys = {
        "source_id", "source_family_id", "source_uri", "license_id",
        "license_verified", "training_use_allowed",
    }
    for index, item in enumerate(sources_raw):
        row = _object(item, source_keys, f"sources[{index}]")
        source_id = _text(row["source_id"], f"sources[{index}].source_id")
        if source_id in sources:
            raise ValueError(f"duplicate source_id: {source_id}")
        if row["license_verified"] is not True or row["training_use_allowed"] is not True:
            raise ValueError(f"source {source_id} is not verified and approved for training use")
        sources[source_id] = {
            "source_family_id": _text(row["source_family_id"], f"sources[{index}].source_family_id"),
            "source_uri": _text(row["source_uri"], f"sources[{index}].source_uri"),
            "license_id": _text(row["license_id"], f"sources[{index}].license_id"),
        }

    groups: dict[str, dict[str, str]] = {}
    group_keys = {"group_id", "source_id", "split", "annotation_status"}
    family_splits: dict[str, set[str]] = defaultdict(set)
    for index, item in enumerate(groups_raw):
        row = _object(item, group_keys, f"groups[{index}]")
        group_id = _text(row["group_id"], f"groups[{index}].group_id")
        source_id = _text(row["source_id"], f"groups[{index}].source_id")
        split = _text(row["split"], f"groups[{index}].split")
        status = _text(row["annotation_status"], f"groups[{index}].annotation_status")
        if group_id in groups:
            raise ValueError(f"duplicate group_id: {group_id}")
        if source_id not in sources:
            raise ValueError(f"group {group_id} references unknown source_id {source_id}")
        if split not in _SPLITS:
            raise ValueError(f"group {group_id} has unsupported split {split}")
        if status != "human_reviewed":
            raise ValueError(f"group {group_id} is not human_reviewed")
        family = sources[source_id]["source_family_id"]
        family_splits[family].add(split)
        groups[group_id] = {"source_id": source_id, "split": split, "source_family_id": family}

    leaked = sorted(family for family, splits in family_splits.items() if len(splits) > 1)
    if leaked:
        raise ValueError(f"source-family leakage across splits: {', '.join(leaked)}")
    present_splits = {row["split"] for row in groups.values()}
    if present_splits != _SPLITS:
        raise ValueError("manifest must contain train, dev, and locked_test groups")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("dataset must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("examples"), list):
        raise ValueError("dataset must use the Classiang text examples schema")
    records = load_records(dataset_path)
    observed_groups: set[str] = set()
    observed_sources: set[str] = set()
    record_counts: Counter[str] = Counter()
    for index, item in enumerate(payload["examples"]):
        if not isinstance(item, dict) or "group_id" not in item:
            raise ValueError(f"examples[{index}] must declare group_id explicitly")
        group_id = _text(item["group_id"], f"examples[{index}].group_id")
        source_id = _text(item.get("source_id"), f"examples[{index}].source_id")
        if group_id not in groups:
            raise ValueError(f"example references unmanifested group_id {group_id}")
        if groups[group_id]["source_id"] != source_id:
            raise ValueError(f"group {group_id} mixes source identities")
        observed_groups.add(group_id)
        observed_sources.add(source_id)
        record_counts[groups[group_id]["split"]] += 1
    if observed_groups != set(groups):
        raise ValueError("manifest contains groups absent from the dataset")
    if observed_sources != set(sources):
        raise ValueError("manifest contains sources absent from the dataset")
    if not records:
        raise ValueError("dataset contains no records")

    group_counts = Counter(row["split"] for row in groups.values())
    return {
        "format": "zhouyi-ai.classiang-dataset-admission-report",
        "schema_version": 1,
        "dataset_path": relative_path,
        "dataset_sha256": digest,
        "record_count": len(records),
        "source_count": len(sources),
        "source_family_count": len(family_splits),
        "group_count": len(groups),
        "groups_by_split": {split: group_counts[split] for split in sorted(_SPLITS)},
        "records_by_split": {split: record_counts[split] for split in sorted(_SPLITS)},
        "source_family_disjoint": True,
        "all_sources_license_verified": True,
        "all_sources_training_use_allowed": True,
        "all_groups_human_reviewed": True,
        "locked_test_role": "evaluation-only; keep labels outside learner/training process",
        "claim_boundary": "Admission checks validate declared provenance and split contracts; they do not independently prove source ownership, license interpretation, annotation quality, or semantic truth.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="UTF-8 JSON provenance/split manifest")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    report = validate_manifest(args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
