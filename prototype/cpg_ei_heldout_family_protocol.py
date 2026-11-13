""""Leakage-audited family-held-out few-shot transfer episode construction.

Training, validation, and test teacher families are disjoint. Validation/test
families expose a bounded labeled support set for adaptation, while their query
labels are emitted in a separate evaluator view. This is few-shot transfer, not
zero-shot transfer or a model implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _episode(task_id: str, rows: list[dict], query_split: str,
             support_size: int, seed: int) -> tuple[dict, dict]:
    train_rows = sorted(
        (row for row in rows if row["state_split"] == "train"),
        key=lambda row: tuple(row["state"]),
    )
    query_rows = sorted(
        (row for row in rows if row["state_split"] == query_split),
        key=lambda row: tuple(row["state"]),
    )
    if support_size > len(train_rows):
        raise ValueError("support_size exceeds available within-family training states")
    if not query_rows:
        raise ValueError(f"family has no {query_split} query states")
    selected = list(train_rows)
    random.Random(seed).shuffle(selected)
    support = selected[:support_size]
    learner_episode = {
        "task_id": task_id,
        "support": [{"state": row["state"], "target": row["target"]} for row in support],
        "query_states": [row["state"] for row in query_rows],
    }
    evaluator_targets = {
        "task_id": task_id,
        "query_targets": [row["target"] for row in query_rows],
    }
    return learner_episode, evaluator_targets


def build_heldout_family_protocol(corpus: dict[str, Any], *, support_size: int = 16,
                                  seed: int = 20261115) -> dict[str, Any]:
    if (isinstance(support_size, bool) or not isinstance(support_size, int)
            or support_size < 1):
        raise ValueError("support_size must be a positive integer")
    grouped: dict[str, list[dict]] = defaultdict(list)
    family_split: dict[str, str] = {}
    for row in corpus["rows"]:
        family_id = row["family_id"]
        grouped[family_id].append(row)
        split = row["family_split"]
        if split not in ("train", "development", "locked"):
            raise ValueError("unknown teacher-family split")
        if row["state_split"] not in ("train", "development", "locked"):
            raise ValueError("unknown within-family state split")
        if family_id in family_split and family_split[family_id] != split:
            raise ValueError("a teacher family appears in multiple family splits")
        family_split[family_id] = split

    by_split = {
        split: sorted(family_id for family_id, value in family_split.items()
                      if value == split)
        for split in ("train", "development", "locked")
    }
    if any(not by_split[split] for split in by_split):
        raise ValueError("train, development, and locked family splits must be non-empty")
    for family_id, rows in grouped.items():
        states = [tuple(row["state"]) for row in rows]
        if len(states) != len(set(states)):
            raise ValueError("a teacher family contains duplicate state rows")
        state_splits = {row["state_split"] for row in rows}
        if state_splits != {"train", "development", "locked"}:
            raise ValueError("every family must contain train, development, and locked states")
    if set(by_split["train"]) & set(by_split["development"]):
        raise ValueError("training and validation teacher families overlap")
    if set(by_split["train"]) & set(by_split["locked"]):
        raise ValueError("training and test teacher families overlap")
    if set(by_split["development"]) & set(by_split["locked"]):
        raise ValueError("validation and test teacher families overlap")

    learner = {
        "protocol_id": "zhouyi-cpg-ei-heldout-family-fewshot-v1",
        "support_size": support_size,
        "seed": seed,
        "meta_train_episodes": [],
        "validation_episodes": [],
        "test_episodes": [],
    }
    evaluator = {
        "protocol_id": learner["protocol_id"],
        "validation_query_targets": [],
        "test_query_targets": [],
    }

    for split, family_ids in by_split.items():
        for index, family_id in enumerate(family_ids):
            task_id = f"{split}-task-{index:05d}"
            query_split = "locked" if split == "locked" else "development"
            episode, targets = _episode(
                task_id, grouped[family_id], query_split, support_size,
                seed + index * 1009 + (0 if split == "train" else 100_000 if split == "development" else 200_000),
            )
            if split == "train":
                episode["meta_train_query_targets"] = targets["query_targets"]
                learner["meta_train_episodes"].append(episode)
            elif split == "development":
                learner["validation_episodes"].append(episode)
                evaluator["validation_query_targets"].append(targets)
            else:
                learner["test_episodes"].append(episode)
                evaluator["test_query_targets"].append(targets)

    summary = {
        "training_families": len(by_split["train"]),
        "validation_families": len(by_split["development"]),
        "test_families": len(by_split["locked"]),
        "support_size_per_family": support_size,
        "validation_query_states_per_family": len(learner["validation_episodes"][0]["query_states"]),
        "test_query_states_per_family": len(learner["test_episodes"][0]["query_states"]),
        "family_overlap_count": 0,
    }
    learner["summary"] = summary
    evaluator["summary"] = summary
    learner["view_sha256"] = hashlib.sha256(_canonical(learner)).hexdigest()
    evaluator["view_sha256"] = hashlib.sha256(_canonical(evaluator)).hexdigest()
    return {"learner_view": learner, "evaluator_view": evaluator}


def write_views(protocol: dict[str, Any], learner_path: str | Path,
                evaluator_path: str | Path) -> None:
    for value, path in ((protocol["learner_view"], learner_path),
                        (protocol["evaluator_view"], evaluator_path)):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", type=int, default=400)
    parser.add_argument("--input-dim", type=int, default=8)
    parser.add_argument("--output-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--support-size", type=int, default=16)
    parser.add_argument("--learner-view", type=Path, required=True)
    parser.add_argument("--evaluator-view", type=Path, required=True)
    args = parser.parse_args()
    from prototype.cpg_ei_mixed_operator_data import generate_mixed_corpus
    corpus = generate_mixed_corpus(
        family_count=args.families, input_dim=args.input_dim,
        output_dim=args.output_dim, seed=args.seed,
    )
    protocol = build_heldout_family_protocol(corpus, support_size=args.support_size,
                                             seed=args.seed + 1)
    write_views(protocol, args.learner_view, args.evaluator_view)
    print(json.dumps(protocol["learner_view"]["summary"], indent=2))


if __name__ == "__main__":
    main()
