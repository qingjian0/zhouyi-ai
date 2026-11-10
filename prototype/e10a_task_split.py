"""Leakage-resistant support/query task views for E10-A generator v2.

This module accepts serialized learner and evaluator payloads separately. It
never accepts an Episode object. Related observations sharing the same
(relation symbol, unordered participant set) are assigned to one partition.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from typing import Any


TASK_SCHEMA_VERSION = "e10a-task-view-v1"


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _group_key(row: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return row["relation_symbol"], tuple(sorted(row["participants"]))


def build_support_query_task(
    learner_view: dict[str, Any],
    evaluator_view: dict[str, Any],
    *,
    seed: int,
    query_fraction: float = 0.25,
) -> dict[str, Any]:
    """Build support/query views with query labels isolated to evaluator output.

    Grouping by unordered participant set keeps positive, context-negative and
    role-near-miss observations for an identical participant combination on
    the same side. The support partition must retain both labels per relation.
    """
    if not 0.0 < query_fraction < 1.0:
        raise ValueError("query_fraction must be strictly between 0 and 1")
    if learner_view.get("episode_id") != evaluator_view.get("episode_id"):
        raise ValueError("learner/evaluator episode identity mismatch")

    observations = learner_view.get("observations")
    instances = evaluator_view.get("instances")
    if not isinstance(observations, list) or not observations:
        raise ValueError("learner observations must be a non-empty list")
    if not isinstance(instances, list):
        raise ValueError("evaluator instances must be a list")

    truth_by_id = {row["observation_id"]: row for row in instances}
    observation_ids = [row["observation_id"] for row in observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("duplicate learner observation identity")
    if set(observation_ids) != set(truth_by_id):
        raise ValueError("learner/evaluator observation identity mismatch")

    groups: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[_group_key(row)].append(row)

    by_relation: dict[str, list[tuple[str, tuple[str, ...]]]] = defaultdict(list)
    for key in groups:
        by_relation[key[0]].append(key)

    rng = random.Random(seed)
    support_keys: set[tuple[str, tuple[str, ...]]] = set()
    query_keys: set[tuple[str, tuple[str, ...]]] = set()

    for relation_symbol, keys in sorted(by_relation.items()):
        if len(keys) < 3:
            raise ValueError(
                f"relation {relation_symbol!r} needs at least 3 distinct "
                "participant groups for support/query evaluation"
            )
        labels = {
            key: {bool(truth_by_id[row["observation_id"]]["valid"])
                  for row in groups[key]}
            for key in keys
        }
        all_labels = set().union(*(labels[key] for key in keys))
        if all_labels != {False, True}:
            raise ValueError(
                f"relation {relation_symbol!r} needs positive and negative evidence"
            )

        shuffled = list(keys)
        rng.shuffle(shuffled)
        target_query_groups = max(1, round(len(keys) * query_fraction))
        selected: list[tuple[str, tuple[str, ...]]] = []
        remaining = set(keys)
        for key in shuffled:
            if len(selected) >= target_query_groups:
                break
            candidate_remaining = remaining - {key}
            remaining_labels = set().union(
                *(labels[item] for item in candidate_remaining)
            ) if candidate_remaining else set()
            if len(candidate_remaining) >= 2 and remaining_labels == {False, True}:
                selected.append(key)
                remaining.remove(key)

        if not selected:
            raise ValueError(
                f"relation {relation_symbol!r} cannot form a non-empty query "
                "while preserving positive and negative support"
            )
        query_keys.update(selected)
        support_keys.update(remaining)

    support_rows = []
    query_rows = []
    evaluator_truth = {}
    for key, rows in groups.items():
        destination = query_rows if key in query_keys else support_rows
        for row in rows:
            if key in query_keys:
                # Deliberately construct a strict allowlist: no outcome or
                # violation/template metadata is copied into QueryView.
                destination.append({
                    "observation_id": row["observation_id"],
                    "relation_symbol": row["relation_symbol"],
                    "participants": list(row["participants"]),
                    "context": [list(pair) for pair in row["context"]],
                })
                truth = truth_by_id[row["observation_id"]]
                evaluator_truth[row["observation_id"]] = {
                    "valid": bool(truth["valid"]),
                    "template_id": truth["template_id"],
                    "violation": truth.get("violation"),
                }
            else:
                destination.append({
                    "observation_id": row["observation_id"],
                    "relation_symbol": row["relation_symbol"],
                    "participants": list(row["participants"]),
                    "context": [list(pair) for pair in row["context"]],
                    "outcome": bool(row["outcome"]),
                })

    # Stable ordering makes task serialization reproducible for a fixed seed.
    support_rows.sort(key=lambda row: row["observation_id"])
    query_rows.sort(key=lambda row: row["observation_id"])
    support_ids = {row["observation_id"] for row in support_rows}
    query_ids = {row["observation_id"] for row in query_rows}
    if support_ids & query_ids or support_ids | query_ids != set(observation_ids):
        raise AssertionError("support/query observation partition is not exact")

    # Check that every relation remains learnable from both positive and
    # negative support examples after the grouped split.
    for relation_symbol in by_relation:
        relation_support = [
            row for row in support_rows
            if row["relation_symbol"] == relation_symbol
        ]
        if {row["outcome"] for row in relation_support} != {False, True}:
            raise AssertionError("support lost a required label class")

    manifest = {
        "schema_version": TASK_SCHEMA_VERSION,
        "episode_id": learner_view["episode_id"],
        "split_seed": seed,
        "query_fraction_requested": query_fraction,
        "support_group_count": len(support_keys),
        "query_group_count": len(query_keys),
        "support_observation_count": len(support_rows),
        "query_observation_count": len(query_rows),
        "support_observation_ids_hash": _canonical_hash(sorted(support_ids)),
        "query_observation_ids_hash": _canonical_hash(sorted(query_ids)),
        "grouping": "relation_symbol+unordered_participant_set",
    }
    return {
        "support": {
            "schema_version": TASK_SCHEMA_VERSION,
            "episode_id": learner_view["episode_id"],
            "objects": learner_view.get("objects", []),
            "observations": support_rows,
        },
        "query": {
            "schema_version": TASK_SCHEMA_VERSION,
            "episode_id": learner_view["episode_id"],
            "observations": query_rows,
        },
        "evaluator_truth": evaluator_truth,
        "manifest": manifest,
    }
