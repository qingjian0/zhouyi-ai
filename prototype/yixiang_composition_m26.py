"""Auditable composition semantics and emergence claims (M26).

This module validates declared composition structure and evidence contracts.
It does not discover compositions or prove ontological emergence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


class CompositionKind(str, Enum):
    PARALLEL = "parallel"
    ORDERED = "ordered"
    CONTAINMENT = "containment"
    INTERACTION = "interaction"
    OPPOSITION = "opposition"
    TRANSFORMATION = "transformation"


class CompositionStatus(str, Enum):
    PROVISIONAL = "provisional"
    BLOCKED = "blocked"
    HUMAN_REVIEW = "human_review"


@dataclass(frozen=True)
class SymbolicElement:
    element_id: str
    category_id: str
    context_id: str
    context_version: int


@dataclass(frozen=True)
class CompositionNode:
    composition_id: str
    member_ids: Tuple[str, ...]
    kind: CompositionKind
    operation: str
    scope: str
    context_id: str
    context_version: int
    evidence_refs: Tuple[str, ...]
    rationale: str
    ordered: bool = False


@dataclass(frozen=True)
class CompositionEdge:
    edge_id: str
    source_id: str
    target_id: str
    kind: CompositionKind
    operation: str
    scope: str
    context_id: str
    context_version: int
    evidence_refs: Tuple[str, ...]
    rationale: str
    composition_id: str = ""


@dataclass(frozen=True)
class EmergentCategoryClaim:
    claim_id: str
    composition_id: str
    proposed_category_id: str
    candidate_properties: Tuple[str, ...]
    whole_level_evidence_refs: Tuple[str, ...]
    member_evidence_refs: Tuple[str, ...]
    non_reducibility_argument: str
    scope: str
    context_id: str
    context_version: int
    counterexample_refs: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class CompositionAudit:
    valid: bool
    status: CompositionStatus
    issues: Tuple[str, ...]


def audit_compositions(
    elements: Iterable[SymbolicElement],
    compositions: Iterable[CompositionNode],
    edges: Iterable[CompositionEdge] = (),
    emergence_claims: Iterable[EmergentCategoryClaim] = (),
) -> CompositionAudit:
    element_list = tuple(elements)
    composition_list = tuple(compositions)
    edge_list = tuple(edges)
    claim_list = tuple(emergence_claims)
    element_map = {item.element_id: item for item in element_list}
    composition_map = {item.composition_id: item for item in composition_list}
    issues: list[str] = []
    review_required = False

    if len(element_map) != len(element_list):
        issues.append("duplicate_element_id")
    for item in element_list:
        if not item.element_id or not item.category_id or not item.context_id or item.context_version < 1:
            issues.append(f"invalid_element:{item.element_id}")

    seen_compositions: set[str] = set()
    for comp in composition_list:
        if comp.composition_id in seen_compositions:
            issues.append(f"duplicate_composition_id:{comp.composition_id}")
        seen_compositions.add(comp.composition_id)
        if len(comp.member_ids) < 2:
            issues.append(f"composition_requires_two_members:{comp.composition_id}")
        if len(set(comp.member_ids)) != len(comp.member_ids):
            issues.append(f"duplicate_composition_member:{comp.composition_id}")
        for member_id in comp.member_ids:
            if member_id not in element_map:
                issues.append(f"unknown_composition_member:{comp.composition_id}:{member_id}")
            else:
                member = element_map[member_id]
                if member.context_id != comp.context_id or member.context_version != comp.context_version:
                    issues.append(f"composition_context_mismatch:{comp.composition_id}:{member_id}")
        if not comp.operation.strip() or not comp.scope.strip() or not comp.rationale.strip():
            issues.append(f"incomplete_composition_rule:{comp.composition_id}")
        if not comp.context_id or comp.context_version < 1:
            issues.append(f"invalid_composition_context:{comp.composition_id}")
        if not comp.evidence_refs:
            issues.append(f"missing_composition_evidence:{comp.composition_id}")
        if comp.kind == CompositionKind.ORDERED and not comp.ordered:
            issues.append(f"ordered_composition_requires_order:{comp.composition_id}")
        if comp.kind != CompositionKind.ORDERED and comp.ordered:
            review_required = True
            # An order declared for a non-ordered operation is retained for review.
    
    seen_edges: set[str] = set()
    adjacency: dict[str, list[str]] = {}
    for edge in edge_list:
        if edge.edge_id in seen_edges:
            issues.append(f"duplicate_edge_id:{edge.edge_id}")
        seen_edges.add(edge.edge_id)
        if edge.source_id not in element_map or edge.target_id not in element_map:
            issues.append(f"unknown_edge_endpoint:{edge.edge_id}")
        comp = composition_map.get(edge.composition_id)
        if comp is None:
            issues.append(f"unknown_edge_composition:{edge.edge_id}")
        elif edge.source_id not in comp.member_ids or edge.target_id not in comp.member_ids:
            issues.append(f"edge_endpoint_outside_composition:{edge.edge_id}")
        elif edge.scope != comp.scope or edge.context_id != comp.context_id or edge.context_version != comp.context_version:
            issues.append(f"edge_composition_scope_or_context_mismatch:{edge.edge_id}")
        if edge.source_id == edge.target_id:
            issues.append(f"self_edge:{edge.edge_id}")
        if not edge.operation.strip() or not edge.scope.strip() or not edge.rationale.strip():
            issues.append(f"incomplete_edge_rule:{edge.edge_id}")
        if not edge.context_id or edge.context_version < 1:
            issues.append(f"invalid_edge_context:{edge.edge_id}")
        if not edge.evidence_refs:
            issues.append(f"missing_edge_evidence:{edge.edge_id}")
        for endpoint in (edge.source_id, edge.target_id):
            item = element_map.get(endpoint)
            if item and (item.context_id != edge.context_id or item.context_version != edge.context_version):
                issues.append(f"edge_context_mismatch:{edge.edge_id}:{endpoint}")
        if edge.kind == CompositionKind.TRANSFORMATION and edge.source_id and edge.target_id:
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)

    # Transformation edges encode a directed state transition; cycles are not
    # automatically invalid, but require explicit human review as possible loops.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        cyclic = any(visit(child) for child in adjacency.get(node, ()))
        visiting.remove(node)
        visited.add(node)
        return cyclic

    if any(visit(node) for node in tuple(adjacency)):
        review_required = True

    seen_claims: set[str] = set()
    for claim in claim_list:
        if claim.claim_id in seen_claims:
            issues.append(f"duplicate_emergence_claim_id:{claim.claim_id}")
        seen_claims.add(claim.claim_id)
        comp = composition_map.get(claim.composition_id)
        if comp is None:
            issues.append(f"unknown_claim_composition:{claim.claim_id}")
            continue
        if not claim.proposed_category_id or not claim.candidate_properties:
            issues.append(f"missing_emergent_category_or_properties:{claim.claim_id}")
        if not claim.whole_level_evidence_refs:
            issues.append(f"missing_whole_level_evidence:{claim.claim_id}")
        if not claim.member_evidence_refs:
            issues.append(f"missing_member_evidence:{claim.claim_id}")
        if set(claim.whole_level_evidence_refs) & set(claim.member_evidence_refs):
            issues.append(f"whole_and_member_evidence_not_independent:{claim.claim_id}")
        if not claim.non_reducibility_argument.strip():
            issues.append(f"missing_non_reducibility_argument:{claim.claim_id}")
        if not claim.scope.strip() or not claim.rationale.strip():
            issues.append(f"incomplete_emergence_claim:{claim.claim_id}")
        if claim.context_id != comp.context_id or claim.context_version != comp.context_version:
            issues.append(f"emergence_context_mismatch:{claim.claim_id}")
        if claim.scope != comp.scope:
            issues.append(f"emergence_scope_mismatch:{claim.claim_id}")
        if not claim.counterexample_refs:
            review_required = True
            issues.append(f"missing_emergence_counterexamples:{claim.claim_id}")
        # The validator cannot establish that a property is genuinely novel.
        # A claim is always provisional and requires independent adjudication.
        review_required = True

    valid = not issues
    status = CompositionStatus.BLOCKED if not valid else (
        CompositionStatus.HUMAN_REVIEW if review_required else CompositionStatus.PROVISIONAL
    )
    return CompositionAudit(valid, status, tuple(sorted(set(issues))))
