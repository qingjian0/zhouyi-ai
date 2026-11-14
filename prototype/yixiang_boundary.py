"""Audit multi-membership, hierarchy and contextual category boundaries.

This prototype audits declarations and provenance only. It does not infer
membership, establish causal identity, or validate classical interpretations.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


class CategoryLifecycle(str, Enum):
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class BoundaryStatus(str, Enum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    UNDECIDED = "undecided"


@dataclass(frozen=True)
class CategoryDefinition:
    category_id: str
    name: str
    axis: str
    criterion: str
    parent_ids: Tuple[str, ...] = ()
    lifecycle: CategoryLifecycle = CategoryLifecycle.PROVISIONAL
    successor_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CategoryMembership:
    membership_id: str
    subject_id: str
    category_id: str
    context_id: str
    context_version: int
    status: BoundaryStatus
    feature_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class BoundaryCase:
    case_id: str
    subject_id: str
    category_id: str
    context_id: str
    context_version: int
    status: BoundaryStatus
    criterion_applied: str
    evidence_refs: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class CategoryAudit:
    valid: bool
    issues: Tuple[str, ...]
    multi_membership_groups: Tuple[Tuple[str, str, Tuple[str, ...]], ...]


def _has_cycle(categories: dict[str, CategoryDefinition]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for parent in categories[node].parent_ids:
            if parent in categories and visit(parent):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in categories if node not in visited)


def audit_categories(
    categories: Iterable[CategoryDefinition],
    memberships: Iterable[CategoryMembership],
    boundary_cases: Iterable[BoundaryCase] = (),
    known_features: Iterable[str] = (),
) -> CategoryAudit:
    category_list = tuple(categories)
    membership_list = tuple(memberships)
    boundary_list = tuple(boundary_cases)
    feature_ids = set(known_features)
    category_map = {item.category_id: item for item in category_list}
    issues: list[str] = []

    if len(category_map) != len(category_list):
        issues.append("duplicate_category_id")
    if any(not c.category_id or not c.name.strip() for c in category_list):
        issues.append("invalid_category_identity")

    for category in category_list:
        if not category.axis.strip():
            issues.append(f"missing_category_axis:{category.category_id}")
        if not category.criterion.strip():
            issues.append(f"missing_category_criterion:{category.category_id}")
        if category.category_id in category.parent_ids:
            issues.append(f"self_parent:{category.category_id}")
        for parent in category.parent_ids:
            if parent not in category_map:
                issues.append(f"unknown_parent:{category.category_id}:{parent}")
        if category.lifecycle == CategoryLifecycle.DEPRECATED and not category.successor_ids:
            issues.append(f"deprecated_without_successor:{category.category_id}")
        for successor in category.successor_ids:
            if successor not in category_map:
                issues.append(f"unknown_successor:{category.category_id}:{successor}")

    if _has_cycle(category_map):
        issues.append("category_hierarchy_cycle")

    seen_memberships: set[str] = set()
    grouped: dict[tuple[str, str], set[str]] = {}
    for item in membership_list:
        if item.membership_id in seen_memberships:
            issues.append(f"duplicate_membership_id:{item.membership_id}")
        seen_memberships.add(item.membership_id)
        if item.category_id not in category_map:
            issues.append(f"unknown_membership_category:{item.membership_id}")
            continue
        if not item.subject_id or not item.context_id or item.context_version < 1:
            issues.append(f"invalid_membership_context:{item.membership_id}")
        if not item.evidence_refs:
            issues.append(f"missing_membership_evidence:{item.membership_id}")
        if not item.rationale.strip():
            issues.append(f"missing_membership_rationale:{item.membership_id}")
        if feature_ids and any(ref not in feature_ids for ref in item.feature_refs):
            issues.append(f"unknown_feature_reference:{item.membership_id}")
        if item.status == BoundaryStatus.INCLUDED:
            grouped.setdefault((item.subject_id, item.context_id), set()).add(item.category_id)
        if category_map[item.category_id].lifecycle == CategoryLifecycle.DEPRECATED:
            issues.append(f"membership_in_deprecated_category:{item.membership_id}")

    seen_cases: set[str] = set()
    for case in boundary_list:
        if case.case_id in seen_cases:
            issues.append(f"duplicate_boundary_case_id:{case.case_id}")
        seen_cases.add(case.case_id)
        if case.category_id not in category_map:
            issues.append(f"unknown_boundary_category:{case.case_id}")
        if not case.criterion_applied.strip():
            issues.append(f"missing_boundary_criterion:{case.case_id}")
        if not case.evidence_refs:
            issues.append(f"missing_boundary_evidence:{case.case_id}")
        if not case.rationale.strip():
            issues.append(f"missing_boundary_rationale:{case.case_id}")

    multi = tuple(
        (subject, context, tuple(sorted(ids)))
        for (subject, context), ids in sorted(grouped.items())
        if len(ids) > 1
    )
    return CategoryAudit(not issues, tuple(sorted(set(issues))), multi)
