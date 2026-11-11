"""Versioned, fail-closed data contract for E13 cross-track experiments.

This module deliberately validates representation, not truth. It does not infer
semantics from identifiers, missing fields, or implicit tuple positions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "cpg-ei-experience/0.1"


class ContractError(ValueError):
    """Raised when an input violates the shared experience contract."""


class RoleSemantics(str, Enum):
    ORDERED_NAMED = "ORDERED_NAMED"
    ORDERED_POSITIONAL = "ORDERED_POSITIONAL"
    UNORDERED = "UNORDERED"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(str, Enum):
    SUPPORT = "SUPPORT"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class EventKind(str, Enum):
    OBSERVATION_RECORDED = "OBSERVATION_RECORDED"
    CANDIDATE_PROPOSED = "CANDIDATE_PROPOSED"
    PREDICTION_COMMITTED = "PREDICTION_COMMITTED"
    QUERY_SELECTED = "QUERY_SELECTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    EVIDENCE_REVEALED = "EVIDENCE_REVEALED"
    MAPPING_VALIDATED = "MAPPING_VALIDATED"
    STRUCTURE_REVISED = "STRUCTURE_REVISED"
    CANDIDATE_SUSPENDED = "CANDIDATE_SUSPENDED"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")


def _unique(values: Sequence[str], field: str) -> None:
    if len(set(values)) != len(values):
        raise ContractError(f"{field} must contain unique values")


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.entity_id, "entity_id")
        _nonempty(self.entity_type, "entity_type")
        for key, value in self.attributes:
            _nonempty(key, "attribute key")
            if not isinstance(value, str):
                raise ContractError("attribute values must be strings")


@dataclass(frozen=True)
class RelationSchema:
    relation_type: str
    arity: int
    argument_types: tuple[str, ...]
    role_semantics: RoleSemantics
    role_names: tuple[str, ...] = ()
    symmetry: str = "UNKNOWN"
    context_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.relation_type, "relation_type")
        if self.arity < 1:
            raise ContractError("relation arity must be >= 1")
        if len(self.argument_types) != self.arity:
            raise ContractError("argument_types length must equal arity")
        if self.role_semantics == RoleSemantics.ORDERED_NAMED:
            if len(self.role_names) != self.arity:
                raise ContractError("ORDERED_NAMED requires one role name per argument")
            _unique(self.role_names, "role_names")
        elif self.role_names:
            raise ContractError("role_names are only valid for ORDERED_NAMED")
        if self.symmetry not in {"SYMMETRIC", "ASYMMETRIC", "UNKNOWN"}:
            raise ContractError("symmetry must be SYMMETRIC, ASYMMETRIC, or UNKNOWN")
        if self.symmetry == "SYMMETRIC" and self.role_semantics not in {
            RoleSemantics.UNORDERED, RoleSemantics.UNKNOWN
        }:
            raise ContractError("SYMMETRIC relations must use UNORDERED or UNKNOWN role semantics")
        _unique(self.context_keys, "context_keys")


@dataclass(frozen=True)
class RelationInstance:
    relation_id: str
    relation_type: str
    participants: tuple[str, ...]
    context: tuple[tuple[str, str], ...] = ()
    evidence_status: EvidenceStatus = EvidenceStatus.UNKNOWN
    provenance_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.relation_id, "relation_id")
        _nonempty(self.relation_type, "relation_type")
        if not self.participants:
            raise ContractError("participants cannot be empty")
        for key, value in self.context:
            _nonempty(key, "context key")
            if not isinstance(value, str):
                raise ContractError("context values must be strings")
        _unique(tuple(k for k, _ in self.context), "context keys")


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    episode_id: str
    sequence: int
    kind: EventKind
    actor_track: str
    payload_digest: str
    visibility: str
    parent_refs: tuple[str, ...] = ()
    timestamp: str = ""

    def __post_init__(self) -> None:
        for field in ("event_id", "episode_id", "actor_track", "payload_digest", "visibility"):
            _nonempty(getattr(self, field), field)
        if self.sequence < 0:
            raise ContractError("sequence must be >= 0")
        if self.visibility not in {"LEARNER_VISIBLE", "EVALUATOR_ONLY", "PUBLIC_DESCRIPTOR"}:
            raise ContractError("invalid visibility")


@dataclass(frozen=True)
class RelationalGraph:
    entities: tuple[Entity, ...]
    schemas: tuple[RelationSchema, ...]
    relations: tuple[RelationInstance, ...]

    def __post_init__(self) -> None:
        entity_ids = tuple(item.entity_id for item in self.entities)
        _unique(entity_ids, "entity_ids")
        schema_ids = tuple(item.relation_type for item in self.schemas)
        _unique(schema_ids, "relation_types")
        entity_map = {item.entity_id: item for item in self.entities}
        schema_map = {item.relation_type: item for item in self.schemas}
        relation_ids = tuple(item.relation_id for item in self.relations)
        _unique(relation_ids, "relation_ids")
        for relation in self.relations:
            if relation.relation_type not in schema_map:
                raise ContractError(f"missing schema for relation type {relation.relation_type}")
            schema = schema_map[relation.relation_type]
            if len(relation.participants) != schema.arity:
                raise ContractError(f"wrong arity for relation {relation.relation_id}")
            for index, entity_id in enumerate(relation.participants):
                if entity_id not in entity_map:
                    raise ContractError(f"unknown entity {entity_id}")
                expected_type = schema.argument_types[index]
                actual_type = entity_map[entity_id].entity_type
                if schema.role_semantics != RoleSemantics.UNORDERED and actual_type != expected_type:
                    raise ContractError(f"argument type mismatch in relation {relation.relation_id}")
            if schema.role_semantics == RoleSemantics.UNORDERED:
                expected = Counter(schema.argument_types)
                actual = Counter(entity_map[item].entity_type for item in relation.participants)
                if actual != expected:
                    raise ContractError(f"unordered argument types mismatch in relation {relation.relation_id}")
            context_keys = {key for key, _ in relation.context}
            if not context_keys.issubset(set(schema.context_keys)):
                raise ContractError(f"undeclared context key in relation {relation.relation_id}")


def canonical_digest(value: Any) -> str:
    """Stable SHA-256 digest for contract payloads; not an identity primitive."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def graph_to_dict(graph: RelationalGraph) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "entities": [asdict(item) for item in graph.entities],
        "schemas": [
            {
                **asdict(item),
                "role_semantics": item.role_semantics.value,
            }
            for item in graph.schemas
        ],
        "relations": [
            {
                **asdict(item),
                "evidence_status": item.evidence_status.value,
            }
            for item in graph.relations
        ],
    }


def validate_observation_visibility(phase: str, visibility: str, has_hidden_label: bool) -> None:
    """Reject evaluator-only labels from learner-visible query/support payloads."""
    if phase not in {"SUPPORT", "GATE", "TEST", "QUERY", "REVEAL"}:
        raise ContractError("invalid observation phase")
    if visibility not in {"LEARNER_VISIBLE", "EVALUATOR_ONLY", "PUBLIC_DESCRIPTOR"}:
        raise ContractError("invalid observation visibility")
    if has_hidden_label and visibility == "LEARNER_VISIBLE" and phase in {"QUERY", "SUPPORT", "GATE"}:
        raise ContractError("hidden label leaked into learner-visible payload")
