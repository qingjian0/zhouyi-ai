"""Auditable inter-category relations and inference permissions.

This is a declaration/provenance validator, not an automatic analogy engine.
It never promotes similarity into causal identity or unrestricted transfer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


class RelationKind(str, Enum):
    SIMILARITY = "similarity"
    STRUCTURAL = "structural"
    FUNCTIONAL = "functional"
    CAUSAL = "causal"
    TEMPORAL = "temporal"
    CONTEXTUAL = "contextual"
    SYMBOLIC = "symbolic"
    HIERARCHICAL = "hierarchical"
    CONTRAST = "contrast"


class InferencePermission(str, Enum):
    COMPARE_ONLY = "compare_only"
    TRANSFER_FEATURE = "transfer_feature"
    TRANSFER_RELATION = "transfer_relation"
    CAUSAL_HYPOTHESIS = "causal_hypothesis"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CategoryRef:
    category_id: str
    axis: str


@dataclass(frozen=True)
class InterCategoryRelation:
    relation_id: str
    source_category_id: str
    target_category_id: str
    kind: RelationKind
    scope: str
    context_id: str
    context_version: int
    evidence_refs: Tuple[str, ...]
    rationale: str
    direction: str = "directed"


@dataclass(frozen=True)
class CrossAxisMapping:
    mapping_id: str
    source_axis: str
    target_axis: str
    source_category_id: str
    target_category_id: str
    mapping_rule: str
    scope: str
    context_id: str
    context_version: int
    evidence_refs: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class InferenceClaim:
    claim_id: str
    relation_id: str
    permission: InferencePermission
    conclusion: str
    scope: str
    evidence_refs: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class RelationAudit:
    valid: bool
    issues: Tuple[str, ...]


def audit_intercategory_relations(
    categories: Iterable[CategoryRef],
    relations: Iterable[InterCategoryRelation],
    mappings: Iterable[CrossAxisMapping] = (),
    claims: Iterable[InferenceClaim] = (),
) -> RelationAudit:
    category_list = tuple(categories)
    relation_list = tuple(relations)
    mapping_list = tuple(mappings)
    claim_list = tuple(claims)
    category_map = {c.category_id: c for c in category_list}
    relation_map = {r.relation_id: r for r in relation_list}
    issues: list[str] = []

    if len(category_map) != len(category_list):
        issues.append("duplicate_category_id")
    for c in category_list:
        if not c.category_id or not c.axis.strip():
            issues.append(f"invalid_category:{c.category_id}")

    seen_relations: set[str] = set()
    for r in relation_list:
        if r.relation_id in seen_relations:
            issues.append(f"duplicate_relation_id:{r.relation_id}")
        seen_relations.add(r.relation_id)
        if r.source_category_id not in category_map or r.target_category_id not in category_map:
            issues.append(f"unknown_relation_endpoint:{r.relation_id}")
        if r.source_category_id == r.target_category_id and r.kind != RelationKind.SIMILARITY:
            issues.append(f"self_relation_requires_review:{r.relation_id}")
        if not r.scope.strip():
            issues.append(f"missing_relation_scope:{r.relation_id}")
        if not r.context_id or r.context_version < 1:
            issues.append(f"invalid_relation_context:{r.relation_id}")
        if not r.evidence_refs:
            issues.append(f"missing_relation_evidence:{r.relation_id}")
        if not r.rationale.strip():
            issues.append(f"missing_relation_rationale:{r.relation_id}")
        if r.direction not in {"directed", "undirected"}:
            issues.append(f"invalid_relation_direction:{r.relation_id}")
        if r.kind == RelationKind.CAUSAL and r.direction != "directed":
            issues.append(f"causal_relation_must_be_directed:{r.relation_id}")

    seen_mappings: set[str] = set()
    for m in mapping_list:
        if m.mapping_id in seen_mappings:
            issues.append(f"duplicate_mapping_id:{m.mapping_id}")
        seen_mappings.add(m.mapping_id)
        source = category_map.get(m.source_category_id)
        target = category_map.get(m.target_category_id)
        if source is None or target is None:
            issues.append(f"unknown_mapping_endpoint:{m.mapping_id}")
        else:
            if source.axis != m.source_axis or target.axis != m.target_axis:
                issues.append(f"mapping_axis_endpoint_mismatch:{m.mapping_id}")
            if m.source_axis == m.target_axis:
                issues.append(f"mapping_not_cross_axis:{m.mapping_id}")
        if not m.mapping_rule.strip() or not m.scope.strip():
            issues.append(f"missing_mapping_rule_or_scope:{m.mapping_id}")
        if not m.context_id or m.context_version < 1:
            issues.append(f"invalid_mapping_context:{m.mapping_id}")
        if not m.evidence_refs:
            issues.append(f"missing_mapping_evidence:{m.mapping_id}")
        if not m.rationale.strip():
            issues.append(f"missing_mapping_rationale:{m.mapping_id}")

    seen_claims: set[str] = set()
    for claim in claim_list:
        if claim.claim_id in seen_claims:
            issues.append(f"duplicate_claim_id:{claim.claim_id}")
        seen_claims.add(claim.claim_id)
        relation = relation_map.get(claim.relation_id)
        if relation is None:
            issues.append(f"unknown_claim_relation:{claim.claim_id}")
            continue
        if not claim.conclusion.strip() or not claim.scope.strip() or not claim.rationale.strip():
            issues.append(f"incomplete_claim:{claim.claim_id}")
        if not claim.evidence_refs:
            issues.append(f"missing_claim_evidence:{claim.claim_id}")
        if claim.permission == InferencePermission.CAUSAL_HYPOTHESIS and relation.kind != RelationKind.CAUSAL:
            issues.append(f"causal_claim_without_causal_relation:{claim.claim_id}")
        if claim.permission == InferencePermission.TRANSFER_RELATION and relation.kind not in {
            RelationKind.STRUCTURAL, RelationKind.FUNCTIONAL, RelationKind.CAUSAL
        }:
            issues.append(f"relation_transfer_not_supported_by_relation_kind:{claim.claim_id}")
        if claim.permission == InferencePermission.TRANSFER_FEATURE and relation.kind not in {
            RelationKind.SIMILARITY, RelationKind.STRUCTURAL, RelationKind.FUNCTIONAL
        }:
            issues.append(f"feature_transfer_not_supported_by_relation_kind:{claim.claim_id}")
        if claim.permission == InferencePermission.BLOCKED:
            # A blocked claim is retained as an audit record; it is not a valid inference.
            if claim.conclusion.strip():
                issues.append(f"blocked_claim_must_not_assert_conclusion:{claim.claim_id}")
    return RelationAudit(not issues, tuple(sorted(set(issues))))
