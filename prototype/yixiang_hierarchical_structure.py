"""Typed hierarchical relation graph for whole-part yixiang research.

This is an explicit structural baseline. It does not infer relations or claim
that a historical analogy is valid.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RelationKind(str, Enum):
    PART_OF = "part_of"
    FUNCTIONAL_PARTICIPATION = "functional_participation"
    CAUSAL_INFLUENCE = "causal_influence"
    SPATIAL_ADJACENCY = "spatial_adjacency"
    TAXONOMIC_MEMBER = "taxonomic_member"


@dataclass(frozen=True)
class StructureNode:
    node_id: str
    level: str
    label: str = ""


@dataclass(frozen=True)
class StructureEdge:
    edge_id: str
    source_id: str
    target_id: str
    kind: RelationKind
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class HierarchicalStructure:
    nodes: tuple[StructureNode, ...]
    edges: tuple[StructureEdge, ...]

    def validate(self) -> None:
        node_ids: set[str] = set()
        for node in self.nodes:
            if not isinstance(node, StructureNode):
                raise ValueError("nodes must contain StructureNode values")
            if not node.node_id.strip() or not node.level.strip():
                raise ValueError("node id and level are required")
            if node.node_id in node_ids:
                raise ValueError("node ids must be unique")
            node_ids.add(node.node_id)

        edge_ids: set[str] = set()
        acyclic: dict[RelationKind, dict[str, list[str]]] = {
            RelationKind.PART_OF: {},
            RelationKind.TAXONOMIC_MEMBER: {},
        }
        for edge in self.edges:
            if not isinstance(edge, StructureEdge):
                raise ValueError("edges must contain StructureEdge values")
            if not edge.edge_id.strip() or edge.edge_id in edge_ids:
                raise ValueError("edge ids must be non-empty and unique")
            edge_ids.add(edge.edge_id)
            if edge.source_id not in node_ids or edge.target_id not in node_ids:
                raise ValueError("edge endpoints must reference existing nodes")
            if edge.source_id == edge.target_id:
                raise ValueError("self-relations are not allowed")
            if not isinstance(edge.kind, RelationKind):
                raise ValueError("edge kind must be a RelationKind")
            if not isinstance(edge.evidence_refs, tuple) or not edge.evidence_refs:
                raise ValueError("each edge requires evidence references")
            if any(not isinstance(ref, str) or not ref.strip()
                   for ref in edge.evidence_refs):
                raise ValueError("evidence references must be non-empty strings")
            if edge.kind in acyclic:
                acyclic[edge.kind].setdefault(edge.source_id, []).append(edge.target_id)

        # Only strict hierarchy relations are required to be acyclic.
        # Causal and functional feedback loops may be legitimate and are preserved.
        for kind, adjacency in acyclic.items():
            visiting: set[str] = set()
            visited: set[str] = set()

            def visit(node_id: str) -> None:
                if node_id in visiting:
                    raise ValueError(f"{kind.value} hierarchy contains a cycle")
                if node_id in visited:
                    return
                visiting.add(node_id)
                for target_id in adjacency.get(node_id, ()):
                    visit(target_id)
                visiting.remove(node_id)
                visited.add(node_id)

            for node_id in node_ids:
                visit(node_id)

    def edges_of(self, kind: RelationKind) -> tuple[StructureEdge, ...]:
        return tuple(edge for edge in self.edges if edge.kind is kind)

    def neighbors(self, node_id: str, kind: RelationKind) -> tuple[str, ...]:
        if node_id not in {node.node_id for node in self.nodes}:
            raise KeyError(node_id)
        return tuple(edge.target_id for edge in self.edges
                     if edge.source_id == node_id and edge.kind is kind)
