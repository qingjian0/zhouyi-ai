"""Validated, label-blind support/query task views for E10-A v2."""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from typing import Any

TASK_SCHEMA_VERSION = "e10a-task-view-v2"
LEARNER_SCHEMA_VERSION = "e10a-episode-v2"
GENERATOR_VERSION = "e10a-latent-world-v2"


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_context(value: Any, field: str) -> list[list[str]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of key/value pairs")
    result: list[list[str]] = []
    for pair in value:
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(part, str) and part for part in pair)):
            raise ValueError(f"{field} contains a malformed key/value pair")
        result.append([pair[0], pair[1]])
    return result


def _validate_views(
    learner_view: dict[str, Any], evaluator_view: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], set[str]]:
    if not isinstance(learner_view, dict) or not isinstance(evaluator_view, dict):
        raise ValueError("learner and evaluator views must be dictionaries")
    if learner_view.get("schema_version") != LEARNER_SCHEMA_VERSION:
        raise ValueError("unsupported learner schema version")
    if evaluator_view.get("generator_version") != GENERATOR_VERSION:
        raise ValueError("unsupported evaluator generator version")
    episode_id = _nonempty_string(learner_view.get("episode_id"), "episode_id")
    if evaluator_view.get("episode_id") != episode_id:
        raise ValueError("learner/evaluator episode identity mismatch")

    objects = learner_view.get("objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("learner objects must be a non-empty list")
    object_ids: list[str] = []
    for index, obj in enumerate(objects):
        if not isinstance(obj, dict):
            raise ValueError(f"objects[{index}] must be a dictionary")
        object_ids.append(_nonempty_string(obj.get("object_id"),
                                           f"objects[{index}].object_id"))
        attributes = obj.get("attributes")
        if not isinstance(attributes, list):
            raise ValueError(f"objects[{index}].attributes must be a list")
        for pair in attributes:
            if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                    or not all(isinstance(part, str) and part for part in pair)):
                raise ValueError(f"objects[{index}].attributes has a malformed pair")
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("duplicate object identity")
    object_id_set = set(object_ids)

    observations = learner_view.get("observations")
    instances = evaluator_view.get("instances")
    if not isinstance(observations, list) or not observations:
        raise ValueError("learner observations must be a non-empty list")
    if not isinstance(instances, list) or not instances:
        raise ValueError("evaluator instances must be a non-empty list")

    observation_by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError(f"observations[{index}] must be a dictionary")
        oid = _nonempty_string(row.get("observation_id"),
                               f"observations[{index}].observation_id")
        if oid in observation_by_id:
            raise ValueError("duplicate learner observation identity")
        _nonempty_string(row.get("relation_symbol"),
                         f"observations[{index}].relation_symbol")
        participants = row.get("participants")
        if (not isinstance(participants, list) or not participants
                or any(not isinstance(p, str) or not p for p in participants)):
            raise ValueError(f"observations[{index}].participants is malformed")
        if len(participants) != len(set(participants)):
            raise ValueError("participants in an observation must be distinct")
        if not set(participants) <= object_id_set:
            raise ValueError("observation references an unknown object")
        _validate_context(row.get("context"), f"observations[{index}].context")
        if type(row.get("outcome")) is not bool:
            raise ValueError("learner outcome must be an exact boolean")
        observation_by_id[oid] = row

    truth_by_id: dict[str, dict[str, Any]] = {}
    for index, truth in enumerate(instances):
        if not isinstance(truth, dict):
            raise ValueError(f"instances[{index}] must be a dictionary")
        oid = _nonempty_string(truth.get("observation_id"),
                               f"instances[{index}].observation_id")
        if oid in truth_by_id:
            raise ValueError("duplicate evaluator observation identity")
        if type(truth.get("valid")) is not bool:
            raise ValueError("evaluator valid must be an exact boolean")
        _nonempty_string(truth.get("template_id"),
                         f"instances[{index}].template_id")
        violation = truth.get("violation")
        if violation is not None and not isinstance(violation, str):
            raise ValueError("evaluator violation must be a string or null")
        truth_by_id[oid] = truth

    if set(observation_by_id) != set(truth_by_id):
        raise ValueError("learner/evaluator observation identity mismatch")
    for oid, row in observation_by_id.items():
        if row["outcome"] is not truth_by_id[oid]["valid"]:
            raise ValueError(f"learner/evaluator label mismatch for {oid}")

    return observations, truth_by_id, object_id_set


def _group_key(row: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return row["relation_symbol"], tuple(sorted(row["participants"]))


def build_support_query_task(
    learner_view: dict[str, Any],
    evaluator_view: dict[str, Any],
    *,
    seed: int,
    query_fraction: float = 0.25,
) -> dict[str, Any]:
    """Build a deterministic label-blind group split.

    Group assignment uses only relation symbols, participant identities, seed,
    and the requested fraction. Evaluator labels are validated for consistency
    but never consulted when deciding which groups enter Query.
    """
    if (isinstance(query_fraction, bool)
            or not isinstance(query_fraction, (int, float))
            or not 0.0 < query_fraction < 1.0):
        raise ValueError("query_fraction must be strictly between 0 and 1")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    observations, truth_by_id, _ = _validate_views(learner_view, evaluator_view)
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
        shuffled = sorted(keys)
        rng.shuffle(shuffled)
        target_query_groups = min(
            len(keys) - 1, max(1, round(len(keys) * query_fraction))
        )
        query_for_relation = set(shuffled[:target_query_groups])
        query_keys.update(query_for_relation)
        support_keys.update(set(keys) - query_for_relation)

    support_rows: list[dict[str, Any]] = []
    query_rows: list[dict[str, Any]] = []
    evaluator_truth: dict[str, dict[str, Any]] = {}
    for key, rows in groups.items():
        destination = query_rows if key in query_keys else support_rows
        for row in rows:
            if key in query_keys:
                destination.append({
                    "observation_id": row["observation_id"],
                    "relation_symbol": row["relation_symbol"],
                    "participants": list(row["participants"]),
                    "context": _validate_context(row["context"], "context"),
                })
                truth = truth_by_id[row["observation_id"]]
                evaluator_truth[row["observation_id"]] = {
                    "valid": truth["valid"],
                    "template_id": truth["template_id"],
                    "violation": truth.get("violation"),
                }
            else:
                destination.append({
                    "observation_id": row["observation_id"],
                    "relation_symbol": row["relation_symbol"],
                    "participants": list(row["participants"]),
                    "context": _validate_context(row["context"], "context"),
                    "outcome": row["outcome"],
                })

    support_rows.sort(key=lambda row: row["observation_id"])
    query_rows.sort(key=lambda row: row["observation_id"])
    support_ids = {row["observation_id"] for row in support_rows}
    query_ids = {row["observation_id"] for row in query_rows}
    source_ids = {row["observation_id"] for row in observations}
    if support_ids & query_ids or support_ids | query_ids != source_ids:
        raise AssertionError("support/query observation partition is not exact")

    support_label_counts = Counter(
        f'{row["relation_symbol"]}:{str(row["outcome"]).lower()}'
        for row in support_rows
    )
    query_label_counts = Counter(
        f'{row["relation_symbol"]}:{str(truth_by_id[row["observation_id"]]["valid"]).lower()}'
        for row in query_rows
    )
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
        "selection_policy": "label_blind_uniform_group_shuffle_v1",
        "support_label_counts": dict(sorted(support_label_counts.items())),
        "query_label_counts_evaluator_only": dict(sorted(query_label_counts.items())),
    }
    return {
        "support": {
            "schema_version": TASK_SCHEMA_VERSION,
            "episode_id": learner_view["episode_id"],
            "objects": learner_view["objects"],
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
