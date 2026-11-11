"""E10-A generator-first object-disjoint Support/Query prototype.

The latent mechanism is sampled once. Support and Query object pools are then
constructed independently from split-specific deterministic RNG streams.
This is a controlled known-mechanism/unseen-object transfer task, not open-world
concept discovery.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

from prototype.e10a_latent_generator import generate_episode


SCHEMA = "e10a-object-disjoint-task-v1"


def _rng(root_seed: int, label: str) -> random.Random:
    material = f"e10a-ao-v1:{root_seed}:{label}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
    return random.Random(seed)


def _hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _build_pool(mechanisms: list[dict[str, Any]], *, seed: int,
                split: str, instances_per_template: int) -> tuple[list[dict], list[dict], list[dict]]:
    rng = _rng(seed, f"{split}-pool")
    objects: list[dict] = []
    observations: list[dict] = []
    truth: list[dict] = []
    next_id = 0

    for template in mechanisms:
        arity = len(template["role_values"])
        feature = template["feature_key"]
        role_values = list(template["role_values"])
        context_key = template["context_key"]
        required_context = template["required_context"]
        # Each required role value has an independent object supply in each pool.
        buckets: list[list[str]] = []
        for role_index, value in enumerate(role_values):
            bucket = []
            for object_index in range(instances_per_template):
                object_id = f"{split}-obj-{next_id:06d}"
                next_id += 1
                objects.append({
                    "object_id": object_id,
                    "attributes": [[feature, value]],
                })
                bucket.append(object_id)
            buckets.append(bucket)

        # Nuisance values are added independently; they are not copied across pools.
        nuisance_id = f"{split}-obj-{next_id:06d}"
        next_id += 1
        nuisance_value = f"{split}-nuisance-{template['template_id']}"
        objects.append({
            "object_id": nuisance_id,
            "attributes": [[feature, nuisance_value]],
        })

        for instance_index in range(instances_per_template):
            role_objects = tuple(bucket[instance_index] for bucket in buckets)
            if len(set(role_objects)) != arity:
                raise ValueError("role object assignment is not distinct")
            source_id = f"{split}-source-{template['template_id']}-{instance_index}"
            cases = [
                (role_objects, required_context, True, None),
                (role_objects, f"{required_context}-wrong", False, "context_mismatch"),
            ]
            for slot in range(arity):
                changed = list(role_objects)
                changed[slot] = nuisance_id
                cases.append((tuple(changed), required_context, False,
                              f"role_constraint_{slot}"))

            for case_index, (participants, context_value, valid, violation) in enumerate(cases):
                observation_id = f"{split}-obs-{len(observations):06d}"
                shuffled = list(participants)
                rng.shuffle(shuffled)
                observations.append({
                    "observation_id": observation_id,
                    "relation_symbol": template["relation_symbol"],
                    "participants": shuffled,
                    "context": [[context_key, context_value]],
                    "outcome": valid if split == "support" else None,
                })
                truth.append({
                    "observation_id": observation_id,
                    "source_group_id": source_id,
                    "template_id": template["template_id"],
                    "role_objects": list(participants),
                    "valid": valid,
                    "violation": violation,
                })

    rng.shuffle(objects)
    rng.shuffle(observations)
    return objects, observations, truth


def build_object_disjoint_task(
    seed: int, *, instances_per_template: int = 6
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return separate Support payload, Query payload, and evaluator truth.

    The returned values are three distinct serializable objects. A production
    runner must serialize/send Support first, then Query at prediction time, and
    keep evaluator_truth in a separate process or protected service.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not isinstance(instances_per_template, int) or isinstance(instances_per_template, bool) or instances_per_template < 2:
        raise ValueError("instances_per_template must be an integer >= 2")

    # Sample the latent mechanism once. Its object pool is discarded; only the
    # evaluator mechanism specification is reused to construct fresh pools.
    # Keep mechanism sampling independent of the requested pool size.
    seed_episode = generate_episode(seed, instances_per_template=2)
    mechanisms = [
        {
            "template_id": row.template_id,
            "family": row.family,
            "relation_symbol": row.relation_symbol,
            "feature_key": row.feature_key,
            "role_values": list(row.role_values),
            "context_key": row.context_key,
            "required_context": row.required_context,
        }
        for row in seed_episode.templates
    ]
    mechanism_hash = _hash(mechanisms)

    support_objects, support_observations, support_truth = _build_pool(
        mechanisms, seed=seed, split="support",
        instances_per_template=instances_per_template,
    )
    query_objects, query_observations, query_truth = _build_pool(
        mechanisms, seed=seed, split="query",
        instances_per_template=instances_per_template,
    )

    support_ids = {row["object_id"] for row in support_objects}
    query_ids = {row["object_id"] for row in query_objects}
    if support_ids & query_ids:
        raise ValueError("Support/Query object identity leakage")
    for row in support_observations:
        if not set(row["participants"]) <= support_ids:
            raise ValueError("Support observation references non-Support object")
    for row in query_observations:
        if not set(row["participants"]) <= query_ids:
            raise ValueError("Query observation references non-Query object")

    support = {
        "schema_version": SCHEMA,
        "phase": "support",
        "mechanism_hash": mechanism_hash,
        "objects": support_objects,
        "observations": support_observations,
    }
    query = {
        "schema_version": SCHEMA,
        "phase": "query",
        "mechanism_hash": mechanism_hash,
        "objects": query_objects,
        "observations": [
            {key: value for key, value in row.items() if key != "outcome"}
            for row in query_observations
        ],
    }
    evaluator_truth = {
        "schema_version": SCHEMA,
        "mechanism_hash": mechanism_hash,
        "mechanisms": mechanisms,
        "support_truth": support_truth,
        "query_truth": query_truth,
        "audit": {
            "support_object_count": len(support_objects),
            "query_object_count": len(query_objects),
            "object_id_intersection": sorted(support_ids & query_ids),
            "support_positive_count": sum(row["valid"] for row in support_truth),
            "query_positive_count": sum(row["valid"] for row in query_truth),
        },
    }

    # Query object IDs and attributes must not occur anywhere in Support payload.
    support_bytes = json.dumps(support, sort_keys=True, separators=(",", ":"))
    if any(object_id in support_bytes for object_id in query_ids):
        raise ValueError("Query object identity leaked into Support payload")
    if any(row["object_id"] in support_bytes for row in query_objects):
        raise ValueError("Query object record leaked into Support payload")
    forbidden = {"outcome", "valid", "violation", "template_id",
                 "role_objects", "source_group_id"}
    for row in query["observations"]:
        if forbidden.intersection(row):
            raise ValueError("Query payload contains evaluator-only fields")
    return support, query, evaluator_truth
