"""Role-labelled n-ary relation preservation for evidence-gated yixiang."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class HyperRelation:
    relation_id: str
    kind: str
    roles: tuple[tuple[str, str], ...]
    dimension: str = "relation"

@dataclass(frozen=True)
class HypergraphAnalogy:
    candidate_id: str
    source_entities: tuple[str, ...]
    target_entities: tuple[str, ...]
    mapping: Mapping[str, str]
    source_relations: tuple[HyperRelation, ...]
    target_relations: tuple[HyperRelation, ...]
    evidence_refs: tuple[str, ...]
    conditions: tuple[str, ...]
    validity_scope: str

@dataclass(frozen=True)
class HypergraphAssessment:
    candidate_id: str
    accepted: bool
    precision: float
    recall: float
    f1: float
    preserved: tuple
    missing: tuple
    extra: tuple
    reason_codes: tuple[str, ...]

def _signature(relation, entity_map=None):
    roles = tuple(sorted((role, entity_map.get(entity, entity) if entity_map is not None else entity)
                         for role, entity in relation.roles))
    return relation.kind, roles, relation.dimension

def _validate_relations(relations, known_entities, label):
    ids = []
    for relation in relations:
        if not isinstance(relation, HyperRelation):
            raise ValueError(f"{label} relations must be HyperRelation values")
        if not isinstance(relation.relation_id, str) or not relation.relation_id.strip() or not isinstance(relation.kind, str) or not relation.kind.strip():
            raise ValueError(f"{label} relation id and kind are required")
        if not isinstance(relation.dimension, str) or not relation.dimension.strip():
            raise ValueError(f"{label} relation dimension is required")
        if len(relation.roles) < 2:
            raise ValueError(f"{label} hyperrelations require at least two roles")
        names = [role for role, _ in relation.roles]
        if any(not isinstance(role, str) or not role.strip() for role in names):
            raise ValueError(f"{label} role names must be non-empty")
        if len(names) != len(set(names)):
            raise ValueError(f"{label} role names must be unique within a relation")
        if any(not isinstance(entity, str) or entity not in known_entities for _, entity in relation.roles):
            raise ValueError(f"{label} relation references an unknown entity")
        ids.append(relation.relation_id)
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} relation ids must be unique")

def assess_hypergraph_analogy(candidate: HypergraphAnalogy) -> HypergraphAssessment:
    """Evaluate exact role-labelled n-ary relation preservation."""
    if not isinstance(candidate.candidate_id, str) or not candidate.candidate_id.strip():
        raise ValueError("candidate_id is required")
    if not candidate.source_entities or not candidate.target_entities:
        raise ValueError("both entity sets must be non-empty")
    if len(set(candidate.source_entities)) != len(candidate.source_entities) or len(set(candidate.target_entities)) != len(candidate.target_entities):
        raise ValueError("entity ids must be unique")
    if any(s not in candidate.source_entities for s in candidate.mapping):
        raise ValueError("mapping contains unknown source entity")
    if any(t not in candidate.target_entities for t in candidate.mapping.values()):
        raise ValueError("mapping points to unknown target entity")
    if len(set(candidate.mapping.values())) != len(candidate.mapping):
        raise ValueError("mapping must be injective")
    _validate_relations(candidate.source_relations, set(candidate.source_entities), "source")
    _validate_relations(candidate.target_relations, set(candidate.target_entities), "target")
    expected = set()
    for relation in candidate.source_relations:
        # Keep partially unmapped source relations visible as false negatives.
        mapped = {source: target for source, target in candidate.mapping.items()}
        for _, entity in relation.roles:
            if entity not in mapped:
                mapped[entity] = "UNMAPPED_SOURCE_ENTITY::" + entity
        expected.add(_signature(relation, mapped))
    observed = {_signature(r) for r in candidate.target_relations}
    good, missing, extra = expected & observed, expected - observed, observed - expected
    precision = len(good) / len(observed) if observed else (1.0 if not expected else 0.0)
    recall = len(good) / len(expected) if expected else (1.0 if not observed else 0.0)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    def readable(items):
        return tuple(sorted((kind, roles, dimension) for kind, roles, dimension in items))
    reasons = []
    if not expected or not observed: reasons.append("INSUFFICIENT_HYPERRELATION_DATA")
    if missing or extra: reasons.append("NARY_ROLE_STRUCTURE_NOT_PRESERVED")
    if not candidate.evidence_refs: reasons.append("MISSING_EVIDENCE")
    if not candidate.conditions: reasons.append("MISSING_CONDITIONS")
    if not isinstance(candidate.validity_scope, str) or not candidate.validity_scope.strip():
        reasons.append("MISSING_VALIDITY_SCOPE")
    return HypergraphAssessment(candidate.candidate_id, not reasons, precision, recall, f1,
                                 readable(good), readable(missing), readable(extra), tuple(reasons))
