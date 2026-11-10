"""E10-A latent-world generator (v2).

Creates repeated, learnable relation mechanisms before emitting observations.
Learner and evaluator views are separate serializable payloads. This is a
controlled synthetic benchmark primitive, not an open-world discovery system.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
from dataclasses import dataclass
from typing import Iterable


GENERATOR_VERSION = "e10a-latent-world-v2"
SCHEMA_VERSION = "e10a-episode-v2"


@dataclass(frozen=True)
class ObjectRecord:
    object_id: str
    attributes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RelationObservation:
    observation_id: str
    relation_symbol: str
    participants: tuple[str, ...]
    context: tuple[tuple[str, str], ...]
    outcome: bool


@dataclass(frozen=True)
class TemplateTruth:
    template_id: str
    family: str
    relation_symbol: str
    feature_key: str
    role_values: tuple[str, ...]
    context_key: str
    required_context: str


@dataclass(frozen=True)
class InstanceTruth:
    observation_id: str
    template_id: str
    role_objects: tuple[str, ...]
    valid: bool
    violation: str | None


@dataclass(frozen=True)
class Episode:
    episode_id: str
    objects: tuple[ObjectRecord, ...]
    observations: tuple[RelationObservation, ...]
    templates: tuple[TemplateTruth, ...]
    instances: tuple[InstanceTruth, ...]

    def learner_view(self) -> dict:
        """Serialize only observable fields; do not pass Episode to a learner."""
        return {
            "schema_version": SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "objects": [
                {"object_id": obj.object_id,
                 "attributes": [list(pair) for pair in obj.attributes]}
                for obj in self.objects
            ],
            "observations": [
                {
                    "observation_id": row.observation_id,
                    "relation_symbol": row.relation_symbol,
                    "participants": list(row.participants),
                    "context": [list(pair) for pair in row.context],
                    "outcome": row.outcome,
                }
                for row in self.observations
            ],
        }

    def audit_view(self) -> dict:
        """Evaluator-only latent structure and per-observation role mapping."""
        return {
            "generator_version": GENERATOR_VERSION,
            "episode_id": self.episode_id,
            "templates": [
                {
                    "template_id": row.template_id,
                    "family": row.family,
                    "relation_symbol": row.relation_symbol,
                    "feature_key": row.feature_key,
                    "role_values": list(row.role_values),
                    "context_key": row.context_key,
                    "required_context": row.required_context,
                }
                for row in self.templates
            ],
            "instances": [
                {
                    "observation_id": row.observation_id,
                    "template_id": row.template_id,
                    "role_objects": list(row.role_objects),
                    "valid": row.valid,
                    "violation": row.violation,
                }
                for row in self.instances
            ],
        }

    def identifiability_report(self) -> dict:
        """Check generator-side prerequisites, not a proof of universal identifiability."""
        object_map = {obj.object_id: dict(obj.attributes) for obj in self.objects}
        template_by_id = {row.template_id: row for row in self.templates}
        report = {}
        for template in self.templates:
            rows = [row for row in self.instances
                    if row.template_id == template.template_id and row.valid]
            role_counts = [0] * len(template.role_values)
            role_objects = [set() for _ in template.role_values]
            for row in rows:
                for index, object_id in enumerate(row.role_objects):
                    role_counts[index] += 1
                    role_objects[index].add(object_id)
            distinct_role_values = len(set(template.role_values)) == len(template.role_values)
            feature_present = all(
                template.feature_key in object_map[object_id]
                for row in rows for object_id in row.role_objects
            )
            report[template.template_id] = {
                "positive_instances": len(rows),
                "role_support": role_counts,
                "distinct_role_values": distinct_role_values,
                "feature_observed_for_positive_roles": feature_present,
                "identifiable_up_to_role_permutation": (
                    len(rows) >= 2 and distinct_role_values and feature_present
                    and all(count >= 2 for count in role_counts)
                    and all(len(values) >= 2 for values in role_objects)
                ),
            }
        return report


@dataclass(frozen=True)
class SplitManifest:
    generator_version: str
    schema_version: str
    train_episode_ids: tuple[str, ...]
    test_episode_ids: tuple[str, ...]
    train_object_ids: tuple[str, ...]
    test_object_ids: tuple[str, ...]
    train_learner_hash: str
    test_learner_hash: str
    train_truth_hash: str
    test_truth_hash: str
    policy: str


def _opaque(rng: random.Random, prefix: str, width: int = 8) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return prefix + "".join(rng.choice(alphabet) for _ in range(width))


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_episode(episode: Episode) -> None:
    object_ids = [row.object_id for row in episode.objects]
    if len(object_ids) != len(set(object_ids)):
        raise ValueError("duplicate object identity")
    object_id_set = set(object_ids)
    observation_ids = [row.observation_id for row in episode.observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("duplicate observation identity")
    truth_ids = [row.observation_id for row in episode.instances]
    if len(truth_ids) != len(set(truth_ids)) or set(truth_ids) != set(observation_ids):
        raise ValueError("observation/truth identity mismatch")
    template_ids = {row.template_id for row in episode.templates}
    symbol_to_template = {row.relation_symbol: row.template_id for row in episode.templates}
    if len(symbol_to_template) != len(episode.templates):
        raise ValueError("relation symbols must identify distinct templates")
    truth_by_id = {row.observation_id: row for row in episode.instances}
    template_by_id = {row.template_id: row for row in episode.templates}
    for obs in episode.observations:
        if not set(obs.participants) <= object_id_set:
            raise ValueError("observation references an unknown object")
        if len(obs.participants) != len(set(obs.participants)):
            raise ValueError("participants in an observation must be distinct")
        if obs.relation_symbol not in symbol_to_template:
            raise ValueError("observation references an unknown relation symbol")
        truth = truth_by_id[obs.observation_id]
        if truth.template_id not in template_ids:
            raise ValueError("truth references an unknown template")
        if template_by_id[truth.template_id].relation_symbol != obs.relation_symbol:
            raise ValueError("observation/template relation symbol mismatch")
        if set(truth.role_objects) != set(obs.participants):
            raise ValueError("truth role objects must match the unordered participants")
        if obs.outcome != truth.valid:
            raise ValueError("observable outcome disagrees with evaluator truth")


def generate_episode(seed: int, *, object_count: int = 18,
                     attribute_count: int = 4, template_count: int = 2,
                     instances_per_template: int = 4) -> Episode:
    """Generate reusable attribute-conditioned binary/ternary relation templates.

    Each template requires distinct categorical values of one opaque attribute
    and a particular opaque context value. Participants are shuffled before
    observation. Positive, context-negative, and role-near-miss cases are emitted.
    """
    if object_count < 12:
        raise ValueError("object_count must be at least 12 for balanced role pools")
    if attribute_count < 1 or template_count < 1:
        raise ValueError("attribute_count and template_count must be positive")
    if template_count > attribute_count:
        raise ValueError("template_count cannot exceed attribute_count")
    if instances_per_template < 2:
        raise ValueError("instances_per_template must be at least 2")

    rng = random.Random(seed)
    episode_id = _opaque(rng, "ep")
    object_ids = [_opaque(rng, "obj") for _ in range(object_count)]
    feature_keys = [_opaque(rng, "attr") for _ in range(attribute_count)]
    value_maps = []
    for _ in feature_keys:
        categories = [0, 1, 2]
        rng.shuffle(categories)
        value_maps.append({category: _opaque(rng, "val") for category in categories})

    # Independently permuted, balanced categorical attributes prevent record-order shortcuts.
    latent_attributes = {object_id: {} for object_id in object_ids}
    for feature_index, feature_key in enumerate(feature_keys):
        categories = list(itertools.islice(itertools.cycle((0, 1, 2)), object_count))
        rng.shuffle(categories)
        for object_id, category in zip(object_ids, categories):
            latent_attributes[object_id][feature_key] = value_maps[feature_index][category]

    context_key = _opaque(rng, "ctxk")
    context_values = [_opaque(rng, "ctxv"), _opaque(rng, "ctxv")]
    objects = [
        ObjectRecord(object_id, tuple(sorted(latent_attributes[object_id].items())))
        for object_id in object_ids
    ]

    observations = []
    templates = []
    instances = []
    next_observation = 0

    for template_index in range(template_count):
        arity = 2 if template_index % 2 == 0 else 3
        feature_key = feature_keys[template_index]
        role_categories = rng.sample((0, 1, 2), arity)
        role_values = tuple(value_maps[template_index][category]
                            for category in role_categories)
        required_context = context_values[template_index % 2]
        relation_symbol = _opaque(rng, "rel")
        template_id = _opaque(rng, "tpl")
        family = f"distinct-category-context-gated-arity-{arity}"
        template = TemplateTruth(
            template_id, family, relation_symbol, feature_key, role_values,
            context_key, required_context
        )
        templates.append(template)

        buckets = []
        for category in role_categories:
            value = value_maps[template_index][category]
            bucket = [object_id for object_id in object_ids
                      if latent_attributes[object_id][feature_key] == value]
            buckets.append(bucket)

        role_pools = [
            rng.sample(bucket, k=min(instances_per_template, len(bucket)))
            for bucket in buckets
        ]
        for instance_index in range(instances_per_template):
            role_objects = tuple(
                pool[instance_index % len(pool)] for pool in role_pools
            )
            if len(set(role_objects)) != arity:
                raise ValueError("generator produced duplicate role objects")

            cases = [
                (role_objects, required_context, True, None),
                (role_objects, context_values[1 - (template_index % 2)],
                 False, "context_mismatch"),
            ]

            # One near-miss per role: replace that slot with an object that violates
            # its attribute constraint while keeping all participants distinct.
            for slot, required_value in enumerate(role_values):
                other_objects = set(role_objects) - {role_objects[slot]}
                replacements = [
                    object_id for object_id in object_ids
                    if object_id not in other_objects
                    and latent_attributes[object_id][feature_key] != required_value
                ]
                if replacements:
                    changed = list(role_objects)
                    changed[slot] = rng.choice(replacements)
                    if len(set(changed)) == arity:
                        cases.append((tuple(changed), required_context, False,
                                      f"role_constraint_{slot}"))

            for candidate_roles, context_value, valid, violation in cases:
                observation_id = f"{episode_id}-{next_observation}"
                next_observation += 1
                participants = list(candidate_roles)
                rng.shuffle(participants)
                observations.append(RelationObservation(
                    observation_id=observation_id,
                    relation_symbol=relation_symbol,
                    participants=tuple(participants),
                    context=((context_key, context_value),),
                    outcome=valid,
                ))
                instances.append(InstanceTruth(
                    observation_id=observation_id,
                    template_id=template_id,
                    role_objects=tuple(candidate_roles),
                    valid=valid,
                    violation=violation,
                ))

    rng.shuffle(objects)
    rng.shuffle(observations)
    episode = Episode(episode_id, tuple(objects), tuple(observations),
                      tuple(templates), tuple(instances))
    _validate_episode(episode)
    return episode


def build_split_manifest(train: Iterable[Episode], test: Iterable[Episode],
                         *, policy: str = "identity-disjoint") -> SplitManifest:
    """Build an auditable identity-disjoint split with separate learner/truth hashes."""
    train_rows, test_rows = tuple(train), tuple(test)
    if not train_rows or not test_rows:
        raise ValueError("train and test splits must both be non-empty")
    train_ids = [row.episode_id for row in train_rows]
    test_ids = [row.episode_id for row in test_rows]
    if len(train_ids) != len(set(train_ids)) or len(test_ids) != len(set(test_ids)):
        raise ValueError("episode IDs must be unique within each split")
    if set(train_ids) & set(test_ids):
        raise ValueError("episode identity leakage between train and test")

    train_objects = {obj.object_id for ep in train_rows for obj in ep.objects}
    test_objects = {obj.object_id for ep in test_rows for obj in ep.objects}
    if train_objects & test_objects:
        raise ValueError("object identity leakage between train and test")

    train_learner = [ep.learner_view() for ep in train_rows]
    test_learner = [ep.learner_view() for ep in test_rows]
    train_truth = [ep.audit_view() for ep in train_rows]
    test_truth = [ep.audit_view() for ep in test_rows]
    return SplitManifest(
        generator_version=GENERATOR_VERSION,
        schema_version=SCHEMA_VERSION,
        train_episode_ids=tuple(train_ids),
        test_episode_ids=tuple(test_ids),
        train_object_ids=tuple(sorted(train_objects)),
        test_object_ids=tuple(sorted(test_objects)),
        train_learner_hash=_canonical_hash(train_learner),
        test_learner_hash=_canonical_hash(test_learner),
        train_truth_hash=_canonical_hash(train_truth),
        test_truth_hash=_canonical_hash(test_truth),
        policy=policy,
    )
