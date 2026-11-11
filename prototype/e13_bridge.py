"""E13-B2 explicit cross-domain bridge hypotheses and structural validator.

Candidate proposal is deliberately separate from validation. This module does not
infer semantic equivalence from names or surface similarity: every bridge is an
auditable hypothesis supplied by a proposer or enumerated finite hypothesis source.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .e13_contract import ContractError, RelationalGraph, RoleSemantics


@dataclass(frozen=True)
class TypeMap:
    source: str
    target: str


@dataclass(frozen=True)
class RelationMap:
    source: str
    target: str


@dataclass(frozen=True)
class RoleMap:
    source_relation: str
    target_relation: str
    source_role: str
    target_role: str


@dataclass(frozen=True)
class ContextMap:
    source_key: str
    target_key: str


@dataclass(frozen=True)
class BridgeHypothesis:
    hypothesis_id: str
    entity_types: tuple[TypeMap, ...]
    relations: tuple[RelationMap, ...]
    roles: tuple[RoleMap, ...]
    contexts: tuple[ContextMap, ...] = ()
    provenance: str = ""
    rationale: str = ""
    allow_many_to_one: bool = False


@dataclass(frozen=True)
class BridgeValidation:
    status: str
    reasons: tuple[str, ...]
    matched_relation_pairs: tuple[tuple[str, str], ...]
    checked_constraints: tuple[str, ...]


def _unique_mapping(pairs: Iterable[tuple[str, str]], label: str, allow_many_to_one: bool) -> None:
    pairs = tuple(pairs)
    sources = [a for a, _ in pairs]
    targets = [b for _, b in pairs]
    if len(set(sources)) != len(sources):
        raise ContractError(f"{label} source entries must be unique")
    if not allow_many_to_one and len(set(targets)) != len(targets):
        raise ContractError(f"{label} target entries collide; many-to-one is disabled")


def propose_bridge(
    hypothesis_id: str,
    *,
    entity_types: Iterable[tuple[str, str]],
    relations: Iterable[tuple[str, str]],
    roles: Iterable[tuple[str, str, str, str]],
    contexts: Iterable[tuple[str, str]] = (),
    provenance: str,
    rationale: str,
    allow_many_to_one: bool = False,
) -> BridgeHypothesis:
    """Create an auditable proposal; this function makes no truth claim."""
    if not hypothesis_id.strip() or not provenance.strip() or not rationale.strip():
        raise ContractError("hypothesis_id, provenance, and rationale are required")
    type_maps = tuple(TypeMap(*item) for item in entity_types)
    relation_maps = tuple(RelationMap(*item) for item in relations)
    role_maps = tuple(RoleMap(*item) for item in roles)
    context_maps = tuple(ContextMap(*item) for item in contexts)
    _unique_mapping(((x.source, x.target) for x in type_maps), "entity type map", allow_many_to_one)
    _unique_mapping(((x.source, x.target) for x in relation_maps), "relation map", allow_many_to_one)
    _unique_mapping(((x.source_key, x.target_key) for x in context_maps), "context map", allow_many_to_one)
    role_keys = [(x.source_relation, x.source_role) for x in role_maps]
    if len(set(role_keys)) != len(role_keys):
        raise ContractError("each source relation role may be mapped only once")
    return BridgeHypothesis(
        hypothesis_id, type_maps, relation_maps, role_maps, context_maps,
        provenance, rationale, allow_many_to_one
    )


def validate_bridge(
    source: RelationalGraph,
    target: RelationalGraph,
    hypothesis: BridgeHypothesis,
) -> BridgeValidation:
    """Validate a proposed bridge against finite graph structure; fail closed."""
    reasons: list[str] = []
    checked = ["entity-type compatibility", "relation correspondence",
               "role identity and direction", "context equality"]
    source_types = {x.entity_type for x in source.entities}
    target_types = {x.entity_type for x in target.entities}
    type_map = {x.source: x.target for x in hypothesis.entity_types}
    relation_map = {x.source: x.target for x in hypothesis.relations}
    context_map = {x.source_key: x.target_key for x in hypothesis.contexts}
    if set(type_map) != source_types:
        reasons.append("UNMAPPED_OR_EXTRA_SOURCE_ENTITY_TYPE")
    if any(v not in target_types for v in type_map.values()):
        reasons.append("UNKNOWN_TARGET_ENTITY_TYPE")
    if not hypothesis.allow_many_to_one and len(set(type_map.values())) != len(type_map):
        reasons.append("ENTITY_TYPE_MAP_COLLISION")

    source_schemas = {x.relation_type: x for x in source.schemas}
    target_schemas = {x.relation_type: x for x in target.schemas}
    if set(relation_map) != {x.relation_type for x in source.schemas}:
        reasons.append("UNMAPPED_OR_EXTRA_SOURCE_RELATION")
    if any(v not in target_schemas for v in relation_map.values()):
        reasons.append("UNKNOWN_TARGET_RELATION")
    if not hypothesis.allow_many_to_one and len(set(relation_map.values())) != len(relation_map):
        reasons.append("RELATION_MAP_COLLISION")

    role_map = {(x.source_relation, x.source_role): x.target_role for x in hypothesis.roles}
    expected_role_keys = set()
    for source_name, target_name in relation_map.items():
        if source_name not in source_schemas or target_name not in target_schemas:
            continue
        ss, ts = source_schemas[source_name], target_schemas[target_name]
        if ss.arity != ts.arity:
            reasons.append(f"ARITY_MISMATCH:{source_name}")
            continue
        if ss.role_semantics != RoleSemantics.ORDERED_NAMED or ts.role_semantics != RoleSemantics.ORDERED_NAMED:
            reasons.append(f"ROLE_SEMANTICS_NOT_EXPLICIT:{source_name}")
            continue
        for sr, tr in zip(ss.role_names, ts.role_names):
            expected_role_keys.add((source_name, sr))
            if role_map.get((source_name, sr)) != tr:
                reasons.append(f"ROLE_MISMATCH:{source_name}:{sr}")
        if tuple(type_map.get(t, "") for t in ss.argument_types) != ts.argument_types:
            reasons.append(f"ARGUMENT_TYPE_PATTERN_MISMATCH:{source_name}")
        if ss.symmetry != ts.symmetry:
            reasons.append(f"SYMMETRY_MISMATCH:{source_name}")
    if set(role_map) != expected_role_keys:
        reasons.append("ROLE_MAP_HAS_MISSING_OR_UNAUTHORIZED_ENTRIES")

    matched = []
    target_relations = {x.relation_id: x for x in target.relations}
    target_by_type = {}
    for item in target.relations:
        target_by_type.setdefault(item.relation_type, []).append(item)
    used_targets = set()
    source_entities = {x.entity_id: x for x in source.entities}
    target_entities = {x.entity_id: x for x in target.entities}
    for sr in source.relations:
        mapped_name = relation_map.get(sr.relation_type)
        if mapped_name is None:
            continue
        ss = source_schemas[sr.relation_type]
        candidates = target_by_type.get(mapped_name, [])
        mapped_context = {}
        for key, value in sr.context:
            target_key = context_map.get(key)
            if target_key is None:
                reasons.append(f"UNMAPPED_CONTEXT_KEY:{key}")
                continue
            mapped_context[target_key] = value
        matches = []
        for tr in candidates:
            if tr.relation_id in used_targets or dict(tr.context) != mapped_context:
                continue
            ts = target_schemas[mapped_name]
            ok = True
            for index, (source_entity_id, target_entity_id) in enumerate(zip(sr.participants, tr.participants)):
                source_entity = source_entities[source_entity_id]
                target_entity = target_entities[target_entity_id]
                if type_map.get(source_entity.entity_type) != target_entity.entity_type:
                    ok = False
                    break
                source_role = ss.role_names[index] if ss.role_semantics == RoleSemantics.ORDERED_NAMED else None
                target_role = ts.role_names[index] if ts.role_semantics == RoleSemantics.ORDERED_NAMED else None
                if source_role is None or role_map.get((sr.relation_type, source_role)) != target_role:
                    ok = False
                    break
            if ok:
                matches.append(tr)
        if len(matches) != 1:
            reasons.append(f"RELATION_INSTANCE_MATCH_COUNT:{sr.relation_id}:{len(matches)}")
        else:
            used_targets.add(matches[0].relation_id)
            matched.append((sr.relation_id, matches[0].relation_id))

    status = "VALID" if not reasons else "REJECTED"
    return BridgeValidation(status, tuple(sorted(set(reasons))), tuple(sorted(matched)), tuple(checked))
