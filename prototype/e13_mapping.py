"""Exact small-graph relational mapping enumerator for E13-B1.

This is a bounded oracle for finite graphs with shared relation symbols and
compatible entity types. It is not an open-world semantic analogy learner.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Mapping

from .e13_contract import (
    ContractError,
    RelationalGraph,
    RoleSemantics,
)


@dataclass(frozen=True)
class MappingCandidate:
    node_mapping: tuple[tuple[str, str], ...]
    preserved_relations: tuple[tuple[str, str], ...]
    source_relation_count: int
    target_relation_count: int
    role_semantics_used: tuple[str, ...]
    coverage: float
    preservation_rate: float


@dataclass(frozen=True)
class EnumerationResult:
    status: str
    candidates: tuple[MappingCandidate, ...]
    examined_node_maps: int
    candidate_budget: int


def _context_matches(source_context, target_context) -> bool:
    return dict(source_context) == dict(target_context)


def _relation_match(source_relation, target_relation, schema, node_map) -> bool:
    if source_relation.relation_type != target_relation.relation_type:
        return False
    if not _context_matches(source_relation.context, target_relation.context):
        return False
    mapped = tuple(node_map[item] for item in source_relation.participants)
    target = target_relation.participants
    if schema.role_semantics == RoleSemantics.UNORDERED:
        return set(mapped) == set(target)
    # POSITIONAL and UNKNOWN are compared positionally. UNKNOWN is never
    # upgraded to named semantic roles; this is conservative slot matching.
    if schema.role_semantics in {
        RoleSemantics.ORDERED_POSITIONAL,
        RoleSemantics.ORDERED_NAMED,
        RoleSemantics.UNKNOWN,
    }:
        return mapped == target
    return False


def enumerate_exact_mappings(
    source: RelationalGraph,
    target: RelationalGraph,
    *,
    candidate_budget: int = 100_000,
) -> EnumerationResult:
    """Enumerate all injective, type-compatible, relation-preserving maps.

    A budget overflow returns BUDGET_EXHAUSTED with no partial candidate list,
    avoiding a truncated result being mistaken for a complete optimum set.
    """
    if candidate_budget < 1:
        raise ContractError("candidate_budget must be >= 1")
    source_entities = source.entities
    target_entities = target.entities
    if len(source_entities) > len(target_entities):
        return EnumerationResult("NO_MAPPING", (), 0, candidate_budget)

    target_by_type: dict[str, tuple[str, ...]] = {}
    for entity in target_entities:
        target_by_type.setdefault(entity.entity_type, tuple())
        target_by_type[entity.entity_type] += (entity.entity_id,)
    pools = []
    for entity in source_entities:
        pool = target_by_type.get(entity.entity_type, ())
        if not pool:
            return EnumerationResult("NO_MAPPING", (), 0, candidate_budget)
        pools.append(pool)

    source_schema = {item.relation_type: item for item in source.schemas}
    target_schema = {item.relation_type: item for item in target.schemas}
    compatible_relations = {
        key: value
        for key, value in source_schema.items()
        if key in target_schema
        and value.arity == target_schema[key].arity
        and value.role_semantics == target_schema[key].role_semantics
        and value.argument_types == target_schema[key].argument_types
        and value.symmetry == target_schema[key].symmetry
        and value.context_keys == target_schema[key].context_keys
    }
    if any(item.relation_type not in compatible_relations for item in source.relations):
        return EnumerationResult("NO_MAPPING", (), 0, candidate_budget)

    source_relation_count = len(source.relations)
    target_relation_index = {}
    for relation in target.relations:
        target_relation_index.setdefault(relation.relation_type, []).append(relation)

    results = []
    examined = 0
    used: set[str] = set()
    current: dict[str, str] = {}
    overflow = False

    def evaluate() -> None:
        nonlocal examined, overflow
        examined += 1
        if examined > candidate_budget:
            overflow = True
            return
        preserved = []
        for relation in source.relations:
            schema = source_schema[relation.relation_type]
            matches = [
                candidate
                for candidate in target_relation_index.get(relation.relation_type, ())
                if _relation_match(relation, candidate, schema, current)
            ]
            if not matches:
                return
            # Keep one deterministic target relation for each source relation.
            preserved.append((relation.relation_id, sorted(matches, key=lambda x: x.relation_id)[0].relation_id))
        semantics = tuple(sorted({source_schema[item.relation_type].role_semantics.value for item in source.relations}))
        denominator = source_relation_count
        results.append(
            MappingCandidate(
                node_mapping=tuple(sorted(current.items())),
                preserved_relations=tuple(preserved),
                source_relation_count=source_relation_count,
                target_relation_count=len(target.relations),
                role_semantics_used=semantics,
                coverage=1.0 if denominator else 0.0,
                preservation_rate=1.0 if denominator else 0.0,
            )
        )

    def visit(index: int) -> None:
        nonlocal overflow
        if overflow:
            return
        if index == len(source_entities):
            evaluate()
            return
        source_id = source_entities[index].entity_id
        for target_id in pools[index]:
            if target_id in used:
                continue
            current[source_id] = target_id
            used.add(target_id)
            visit(index + 1)
            used.remove(target_id)
            del current[source_id]
            if overflow:
                return

    visit(0)
    if overflow:
        return EnumerationResult("BUDGET_EXHAUSTED", (), examined, candidate_budget)
    results.sort(key=lambda item: item.node_mapping)
    if not results:
        return EnumerationResult("NO_MAPPING", (), examined, candidate_budget)
    return EnumerationResult("COMPLETE", tuple(results), examined, candidate_budget)
