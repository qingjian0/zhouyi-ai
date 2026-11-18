"""Unified claim dependency graph and selective invalidation (M27).

The graph tracks declared dependencies. It does not decide whether a source
revision is textually correct or whether a claim is semantically true.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Tuple


class NodeKind(str, Enum):
    OBSERVATION = "observation"
    FEATURE = "feature"
    CATEGORY = "category"
    RELATION = "relation"
    MAPPING = "mapping"
    COMPOSITION = "composition"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    CONTEXT = "context"


class DependencyStrength(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class NodeDisposition(str, Enum):
    STALE = "stale"
    REVIEW = "review"
    UNAFFECTED = "unaffected"


@dataclass(frozen=True)
class ClaimNode:
    node_id: str
    kind: NodeKind
    evidence_refs: Tuple[str, ...] = ()
    context_id: str = ""
    context_version: int = 0


@dataclass(frozen=True)
class Dependency:
    dependency_id: str
    source_id: str
    target_id: str
    strength: DependencyStrength = DependencyStrength.HARD
    relation: str = "derived_from"


@dataclass(frozen=True)
class ContextChange:
    context_id: str
    old_version: int
    new_version: int


@dataclass(frozen=True)
class RevisionEvent:
    event_id: str
    changed_node_ids: Tuple[str, ...]
    revoked_evidence_refs: Tuple[str, ...]
    context_changes: Tuple[ContextChange, ...]
    revalidated_node_ids: Tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class InvalidationResult:
    valid_graph: bool
    stale_node_ids: Tuple[str, ...]
    review_node_ids: Tuple[str, ...]
    unaffected_node_ids: Tuple[str, ...]
    seed_reasons: Tuple[Tuple[str, str], ...]
    issues: Tuple[str, ...]
    propagation_trace: Tuple[Tuple[str, str, str], ...]
    semantic_validity_established: bool = False


def audit_dependency_graph(
    nodes: Iterable[ClaimNode],
    dependencies: Iterable[Dependency],
    event: RevisionEvent,
) -> InvalidationResult:
    node_list = tuple(nodes)
    edge_list = tuple(dependencies)
    issues: list[str] = []
    node_map = {node.node_id: node for node in node_list}

    if len(node_map) != len(node_list):
        issues.append("duplicate_node_id")
    for node in node_list:
        if not node.node_id:
            issues.append("empty_node_id")
        if not isinstance(node.kind, NodeKind):
            issues.append(f"invalid_node_kind:{node.node_id}")
        if len(node.evidence_refs) != len(set(node.evidence_refs)):
            issues.append(f"duplicate_node_evidence:{node.node_id}")
        if node.context_version < 0:
            issues.append(f"invalid_node_context_version:{node.node_id}")
        if bool(node.context_id) != (node.context_version > 0):
            issues.append(f"incomplete_node_context:{node.node_id}")

    edge_ids: set[str] = set()
    adjacency: dict[str, list[Dependency]] = {}
    for edge in edge_list:
        if edge.dependency_id in edge_ids:
            issues.append(f"duplicate_dependency_id:{edge.dependency_id}")
        edge_ids.add(edge.dependency_id)
        if edge.source_id not in node_map or edge.target_id not in node_map:
            issues.append(f"unknown_dependency_endpoint:{edge.dependency_id}")
            continue
        if edge.source_id == edge.target_id:
            issues.append(f"self_dependency:{edge.dependency_id}")
        if not isinstance(edge.strength, DependencyStrength):
            issues.append(f"invalid_dependency_strength:{edge.dependency_id}")
        if not edge.relation.strip():
            issues.append(f"missing_dependency_relation:{edge.dependency_id}")
        adjacency.setdefault(edge.source_id, []).append(edge)

    # Dependencies are directed from prerequisite to dependent; cycles make
    # selective invalidation ambiguous and are rejected.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        cyclic = any(visit(edge.target_id) for edge in adjacency.get(node_id, ()))
        visiting.remove(node_id)
        visited.add(node_id)
        return cyclic

    if any(visit(node_id) for node_id in node_map if node_id not in visited):
        issues.append("dependency_cycle")

    if not isinstance(event, RevisionEvent):
        raise ValueError("event must be RevisionEvent")
    if not event.event_id.strip() or not event.reason.strip():
        issues.append("invalid_revision_event")
    for field_name, values in (
        ("changed_node_ids", event.changed_node_ids),
        ("revoked_evidence_refs", event.revoked_evidence_refs),
        ("revalidated_node_ids", event.revalidated_node_ids),
    ):
        if len(values) != len(set(values)):
            issues.append(f"duplicate_event_{field_name}")
    for node_id in event.changed_node_ids + event.revalidated_node_ids:
        if node_id not in node_map:
            issues.append(f"unknown_event_node:{node_id}")
    for change in event.context_changes:
        if not change.context_id or change.old_version < 1 or change.new_version <= change.old_version:
            issues.append(f"invalid_context_change:{change.context_id}")

    if issues:
        return InvalidationResult(False, (), (), tuple(sorted(node_map)), (), tuple(sorted(set(issues))), ())

    seeds: dict[str, str] = {}
    for node_id in event.changed_node_ids:
        seeds[node_id] = "node_changed"
    revoked = set(event.revoked_evidence_refs)
    for node in node_list:
        if revoked.intersection(node.evidence_refs):
            seeds[node.node_id] = "evidence_revoked"
    changes = {(c.context_id, c.old_version) for c in event.context_changes}
    for node in node_list:
        if (node.context_id, node.context_version) in changes:
            seeds.setdefault(node.node_id, "context_version_retired")

    revalidated = set(event.revalidated_node_ids)
    dispositions: dict[str, NodeDisposition] = {}
    queue = deque()
    trace: list[Tuple[str, str, str]] = []
    for node_id, reason in seeds.items():
        if node_id in revalidated:
            trace.append((node_id, "revalidated_barrier", reason))
            continue
        dispositions[node_id] = NodeDisposition.STALE
        queue.append(node_id)
        trace.append((node_id, "seed_stale", reason))

    while queue:
        source_id = queue.popleft()
        for edge in adjacency.get(source_id, ()):
            target_id = edge.target_id
            if target_id in revalidated:
                trace.append((target_id, "revalidated_barrier", edge.dependency_id))
                continue
            next_state = NodeDisposition.STALE if edge.strength == DependencyStrength.HARD else NodeDisposition.REVIEW
            current = dispositions.get(target_id)
            # Stale dominates review, and a previously stale node is not downgraded.
            if current == NodeDisposition.STALE or current == next_state:
                continue
            if current == NodeDisposition.REVIEW and next_state == NodeDisposition.REVIEW:
                continue
            dispositions[target_id] = next_state
            trace.append((target_id, next_state.value, edge.dependency_id))
            if next_state == NodeDisposition.STALE:
                queue.append(target_id)

    stale = tuple(sorted(k for k, v in dispositions.items() if v == NodeDisposition.STALE))
    review = tuple(sorted(k for k, v in dispositions.items() if v == NodeDisposition.REVIEW))
    unaffected = tuple(sorted(set(node_map) - set(stale) - set(review)))
    return InvalidationResult(
        True, stale, review, unaffected, tuple(sorted(seeds.items())), (),
        tuple(trace),
    )
