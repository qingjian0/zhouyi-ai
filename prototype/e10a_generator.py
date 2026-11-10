"""E10-A synthetic relation-structure episodes.

The generator keeps latent truth separate from learner-visible observations.
It is infrastructure for benchmark development, not a learner or a claim of
autonomous concept discovery.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable


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


@dataclass(frozen=True)
class RelationTruth:
    relation_symbol: str
    role_names: tuple[str, ...]
    role_objects: tuple[str, ...]
    context: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Episode:
    objects: tuple[ObjectRecord, ...]
    observations: tuple[RelationObservation, ...]
    truth: tuple[RelationTruth, ...]

    def learner_view(self) -> dict:
        """Return observations only; latent role assignments never cross boundary."""
        return {
            "objects": [
                {"object_id": obj.object_id, "attributes": list(obj.attributes)}
                for obj in self.objects
            ],
            "observations": [
                {
                    "observation_id": obs.observation_id,
                    "relation_symbol": obs.relation_symbol,
                    "participants": list(obs.participants),
                    "context": list(obs.context),
                }
                for obs in self.observations
            ],
        }

    def audit_view(self) -> dict:
        """Return latent truth for evaluator-only use."""
        return {
            "relations": [
                {
                    "relation_symbol": row.relation_symbol,
                    "role_names": list(row.role_names),
                    "role_objects": list(row.role_objects),
                    "context": list(row.context),
                }
                for row in self.truth
            ]
        }


@dataclass(frozen=True)
class SplitManifest:
    train_episode_ids: tuple[str, ...]
    test_episode_ids: tuple[str, ...]
    train_object_ids: tuple[str, ...]
    test_object_ids: tuple[str, ...]


def _opaque(rng: random.Random, prefix: str, width: int = 8) -> str:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return prefix + "".join(rng.choice(alphabet) for _ in range(width))


def generate_episode(seed: int, *, episode_index: int = 0,
                     object_count: int = 8, relation_count: int = 5,
                     max_arity: int = 3, attribute_count: int = 3,
                     missing_rate: float = 0.0) -> Episode:
    """Generate one episode with opaque symbols and separately held-out truth."""
    if object_count < 3:
        raise ValueError("object_count must be at least 3")
    if relation_count < 1:
        raise ValueError("relation_count must be positive")
    if max_arity not in (2, 3):
        raise ValueError("max_arity must be 2 or 3")
    if attribute_count < 1:
        raise ValueError("attribute_count must be positive")
    if not 0.0 <= missing_rate < 1.0:
        raise ValueError("missing_rate must be in [0, 1)")

    rng = random.Random(seed)
    object_ids = [_opaque(rng, "o") for _ in range(object_count)]
    attr_keys = [_opaque(rng, "k", 4) for _ in range(attribute_count)]
    attr_values = [[_opaque(rng, "v", 4) for _ in range(4)]
                   for _ in range(attribute_count)]
    objects = []
    for object_id in object_ids:
        attrs = []
        for key, values in zip(attr_keys, attr_values):
            if rng.random() >= missing_rate:
                attrs.append((key, rng.choice(values)))
        objects.append(ObjectRecord(object_id, tuple(attrs)))

    relation_symbols = [_opaque(rng, "r", 5) for _ in range(2)]
    role_names = ("role_a", "role_b", "role_c")
    observations = []
    truth = []
    for index in range(relation_count):
        arity = 2 if max_arity == 2 or rng.random() < 0.5 else 3
        participants = tuple(rng.sample(object_ids, arity))
        symbol = relation_symbols[index % len(relation_symbols)]
        context = (("ctx", _opaque(rng, "c", 4)),)
        observations.append(RelationObservation(
            observation_id=f"obs-{episode_index}-{index}",
            relation_symbol=symbol,
            participants=participants,
            context=context,
        ))
        truth.append(RelationTruth(
            relation_symbol=symbol,
            role_names=role_names[:arity],
            role_objects=participants,
            context=context,
        ))

    # Randomize record order; role order within each relation remains semantic.
    rng.shuffle(observations)
    rng.shuffle(objects)
    return Episode(tuple(objects), tuple(observations), tuple(truth))


def build_split_manifest(train: Iterable[Episode], test: Iterable[Episode],
                         *, train_ids: Iterable[str],
                         test_ids: Iterable[str]) -> SplitManifest:
    """Build and validate an identity-disjoint split manifest."""
    train_rows, test_rows = tuple(train), tuple(test)
    train_objects = {obj.object_id for ep in train_rows for obj in ep.objects}
    test_objects = {obj.object_id for ep in test_rows for obj in ep.objects}
    overlap = train_objects & test_objects
    if overlap:
        raise ValueError("object identity leakage between train and test")
    train_episode_ids, test_episode_ids = tuple(train_ids), tuple(test_ids)
    if set(train_episode_ids) & set(test_episode_ids):
        raise ValueError("episode identity leakage between train and test")
    return SplitManifest(
        train_episode_ids=train_episode_ids,
        test_episode_ids=test_episode_ids,
        train_object_ids=tuple(sorted(train_objects)),
        test_object_ids=tuple(sorted(test_objects)),
    )
