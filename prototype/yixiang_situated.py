"""Situated yixiang: joint state, role-relation, time, position and context.

This is an explicit symbolic comparison baseline, not an automatic theory of
change, causality, or classical-text interpretation.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from typing import Mapping


@dataclass(frozen=True)
class SituatedRelation:
    kind: str
    roles: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class YixiangSituation:
    situation_id: str
    domain: str
    step: int
    position: str
    stage: str
    state: Mapping[str, str]
    relations: tuple[SituatedRelation, ...]
    context: Mapping[str, str]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class SituationComparison:
    accepted: bool
    state_precision: float
    relation_precision: float
    context_match: tuple[str, ...]
    context_mismatch: tuple[str, ...]
    position_match: bool
    stage_match: bool
    reason_codes: tuple[str, ...]


def _validate(s: YixiangSituation) -> None:
    if not isinstance(s, YixiangSituation):
        raise ValueError("situation must be YixiangSituation")
    for value in (s.situation_id, s.domain, s.position, s.stage):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("situation identity, domain, position and stage are required")
    if type(s.step) is not int:
        raise ValueError("step must be an integer")
    for field, mapping in (("state", s.state), ("context", s.context)):
        if not isinstance(mapping, Mapping):
            raise ValueError(f"{field} must be a mapping")
        if any(not isinstance(k, str) or not k.strip() or
               not isinstance(v, str) or not v.strip() for k, v in mapping.items()):
            raise ValueError(f"{field} keys and values must be non-empty strings")
    for relation in s.relations:
        if not isinstance(relation, SituatedRelation) or not isinstance(relation.kind, str) or not relation.kind.strip():
            raise ValueError("relations require a non-empty kind")
        if not isinstance(relation.roles, tuple) or len(relation.roles) < 2:
            raise ValueError("relations require at least two named roles")
        if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in relation.roles):
            raise ValueError("each relation role must be a (role, entity) pair")
        role_names = [role for role, _ in relation.roles]
        if len(role_names) != len(set(role_names)) or any(not isinstance(role, str) or not role.strip() for role in role_names):
            raise ValueError("relation roles must be unique and non-empty")
        if any(not isinstance(entity, str) or entity not in s.state for _, entity in relation.roles):
            raise ValueError("relation participants must be declared in state")
    if not isinstance(s.evidence_refs, tuple) or any(not isinstance(x, str) or not x.strip() for x in s.evidence_refs):
        raise ValueError("evidence_refs must be a tuple of non-empty strings")


def compare_situations(
    source: YixiangSituation,
    target: YixiangSituation,
    *,
    entity_mapping: Mapping[str, str],
    required_context: tuple[str, ...],
    require_same_position: bool = False,
    require_same_stage: bool = False,
) -> SituationComparison:
    """Compare explicitly mapped states without collapsing all axes to one score.

    Relation roles and kinds are exact. Context keys are compared only when
    explicitly required. Position and stage are independent, optional gates.
    """
    _validate(source)
    _validate(target)
    if not isinstance(entity_mapping, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in entity_mapping.items()):
        raise ValueError("entity_mapping must map string ids to string ids")
    if not isinstance(required_context, tuple) or not required_context or len(set(required_context)) != len(required_context):
        raise ValueError("required_context must be non-empty and unique")
    if any(not isinstance(k, str) or not k.strip() for k in required_context):
        raise ValueError("context keys must be non-empty strings")
    if len(set(entity_mapping.values())) != len(entity_mapping):
        raise ValueError("entity mapping must be injective")
    if any(k not in source.state or v not in target.state for k, v in entity_mapping.items()):
        raise ValueError("entity mapping references unknown state entity")

    state_pairs = []
    for source_entity, target_entity in entity_mapping.items():
        left, right = source.state[source_entity], target.state[target_entity]
        state_pairs.append(left == right)
    state_precision = sum(state_pairs) / len(state_pairs) if state_pairs else 0.0

    def signatures(relations, mapping=None):
        result = Counter()
        for rel in relations:
            roles = tuple(sorted(
                (role, mapping.get(entity, "UNMAPPED::" + entity) if mapping is not None else entity)
                for role, entity in rel.roles
            ))
            result[(rel.kind, roles)] += 1
        return result

    expected = signatures(source.relations, entity_mapping)
    observed = signatures(target.relations)
    preserved_count = sum((expected & observed).values())
    observed_count = sum(observed.values())
    relation_precision = preserved_count / observed_count if observed_count else (1.0 if not expected else 0.0)
    context_match = []
    context_mismatch = []
    for key in required_context:
        if key not in source.context or key not in target.context:
            context_mismatch.append(key + ":missing")
        elif source.context[key] == target.context[key]:
            context_match.append(key)
        else:
            context_mismatch.append(key)
    position_match = source.position == target.position
    stage_match = source.stage == target.stage
    reasons = []
    if not source.evidence_refs or not target.evidence_refs:
        reasons.append("MISSING_EVIDENCE")
    if not entity_mapping:
        reasons.append("MISSING_ENTITY_MAPPING")
    if state_precision < 1.0:
        reasons.append("STATE_NOT_PRESERVED")
    if expected != observed:
        reasons.append("ROLE_RELATIONS_NOT_PRESERVED")
    if context_mismatch:
        reasons.append("CONTEXT_CONDITION_MISMATCH")
    if require_same_position and not position_match:
        reasons.append("POSITION_MISMATCH")
    if require_same_stage and not stage_match:
        reasons.append("STAGE_MISMATCH")
    return SituationComparison(
        accepted=not reasons,
        state_precision=state_precision,
        relation_precision=relation_precision,
        context_match=tuple(context_match),
        context_mismatch=tuple(context_mismatch),
        position_match=position_match,
        stage_match=stage_match,
        reason_codes=tuple(reasons),
    )
