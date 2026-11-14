"""Deterministic typed-analogy bridge validator (XSL-1 reference MVP).

This module validates an explicitly supplied partial structure mapping. It does
not discover analogies, infer causal equivalence, authenticate evidence, or
establish that a traditional symbolic correspondence is universally true.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _sorted_unique(values: tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple) or values != tuple(sorted(set(values))):
        raise ValueError(f"{field} must be a sorted, unique tuple")
    for value in values:
        _text(value, field)


class MappingKind(str, Enum):
    MORPHOLOGY = "morphology"
    FUNCTION = "function"
    ROLE = "role"
    RELATION = "relation"
    DYNAMICS = "dynamics"
    SPATIOTEMPORAL = "spatiotemporal"
    CONVENTIONAL = "conventional"
    INTERPRETIVE = "interpretive"


class BridgeStatus(str, Enum):
    STRUCTURALLY_PRESERVED = "structurally_preserved"
    PARTIAL = "partial"
    COUNTEREXAMPLE = "counterexample"
    UNTESTABLE = "untestable"


@dataclass(frozen=True, order=True)
class Node:
    node_id: str
    node_type: str

    def __post_init__(self) -> None:
        _text(self.node_id, "node_id")
        _text(self.node_type, "node_type")


@dataclass(frozen=True, order=True)
class Relation:
    relation_type: str
    arguments: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.relation_type, "relation_type")
        if not isinstance(self.arguments, tuple) or not self.arguments:
            raise ValueError("relation arguments must be a non-empty tuple")
        for argument in self.arguments:
            _text(argument, "relation argument")


@dataclass(frozen=True)
class RelationalGraph:
    graph_id: str
    nodes: tuple[Node, ...]
    relations: tuple[Relation, ...]

    def __post_init__(self) -> None:
        _text(self.graph_id, "graph_id")
        if not isinstance(self.nodes, tuple) or not self.nodes or any(not isinstance(node, Node) for node in self.nodes):
            raise ValueError("graph must contain a non-empty tuple of Node values")
        if self.nodes != tuple(sorted(self.nodes)):
            raise ValueError("nodes must be sorted by (node_id, node_type)")
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node IDs must be unique")
        if not isinstance(self.relations, tuple) or any(not isinstance(relation, Relation) for relation in self.relations):
            raise ValueError("relations must be a tuple of Relation values")
        if self.relations != tuple(sorted(self.relations)):
            raise ValueError("relations must be a sorted tuple")
        if len(self.relations) != len(set(self.relations)):
            raise ValueError("duplicate relations are not allowed")
        known = set(node_ids)
        for relation in self.relations:
            if any(argument not in known for argument in relation.arguments):
                raise ValueError("relation references an unknown node")


@dataclass(frozen=True)
class AnalogyBridge:
    bridge_id: str
    source: RelationalGraph
    target: RelationalGraph
    mapping_kind: MappingKind
    node_mapping: tuple[tuple[str, str], ...]
    node_type_mapping: tuple[tuple[str, str], ...]
    relation_mapping: tuple[tuple[str, str], ...]
    scope_conditions: tuple[str, ...] = ()
    predicted_consequences: tuple[str, ...] = ()
    counterexamples: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.bridge_id, "bridge_id")
        if not isinstance(self.mapping_kind, MappingKind):
            raise ValueError("mapping_kind must be a MappingKind")
        for field, pairs in (
            ("node_mapping", self.node_mapping),
            ("node_type_mapping", self.node_type_mapping),
            ("relation_mapping", self.relation_mapping),
        ):
            if not isinstance(pairs, tuple):
                raise ValueError(f"{field} must be a tuple of pairs")
            if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs):
                raise ValueError(f"{field} entries must be pairs")
            for left, right in pairs:
                _text(left, field)
                _text(right, field)
            if pairs != tuple(sorted(set(pairs))):
                raise ValueError(f"{field} must be sorted and unique")
            if len({left for left, _ in pairs}) != len(pairs):
                raise ValueError(f"{field} source keys must be unique")
            if field != "node_type_mapping" and len({right for _, right in pairs}) != len(pairs):
                raise ValueError(f"{field} target values must be unique")
        for field in ("scope_conditions", "predicted_consequences", "counterexamples", "evidence_refs"):
            _sorted_unique(getattr(self, field), field)
        source_nodes = {node.node_id: node.node_type for node in self.source.nodes}
        target_nodes = {node.node_id: node.node_type for node in self.target.nodes}
        for source_id, target_id in self.node_mapping:
            if source_id not in source_nodes or target_id not in target_nodes:
                raise ValueError("node mapping references a node outside its graph")
        type_map = dict(self.node_type_mapping)
        for source_id, target_id in self.node_mapping:
            if type_map.get(source_nodes[source_id]) != target_nodes[target_id]:
                raise ValueError("mapped node types require an explicit compatible type mapping")
        source_relation_types = {r.relation_type for r in self.source.relations}
        target_relation_types = {r.relation_type for r in self.target.relations}
        for source_type, target_type in self.relation_mapping:
            if source_type not in source_relation_types or target_type not in target_relation_types:
                raise ValueError("relation mapping references a relation type outside its graph")


@dataclass(frozen=True)
class BridgeValidation:
    status: BridgeStatus
    total_source_relations: int
    mapped_relations: int
    preserved_relations: tuple[Relation, ...]
    violated_relations: tuple[Relation, ...]
    unmapped_relations: tuple[Relation, ...]
    unmatched_target_relations: tuple[Relation, ...]
    mapping_coverage: float
    preservation_rate: float | None
    bridge_digest: str


def _canonical_bridge_payload(bridge: AnalogyBridge) -> dict[str, Any]:
    def graph_payload(graph: RelationalGraph) -> dict[str, Any]:
        return {
            "graph_id": graph.graph_id,
            "nodes": [[n.node_id, n.node_type] for n in graph.nodes],
            "relations": [[r.relation_type, list(r.arguments)] for r in graph.relations],
        }

    return {
        "bridge_id": bridge.bridge_id,
        "mapping_kind": bridge.mapping_kind.value,
        "source": graph_payload(bridge.source),
        "target": graph_payload(bridge.target),
        "node_mapping": [list(pair) for pair in bridge.node_mapping],
        "node_type_mapping": [list(pair) for pair in bridge.node_type_mapping],
        "relation_mapping": [list(pair) for pair in bridge.relation_mapping],
        "scope_conditions": list(bridge.scope_conditions),
        "predicted_consequences": list(bridge.predicted_consequences),
        "counterexamples": list(bridge.counterexamples),
        "evidence_refs": list(bridge.evidence_refs),
    }


def validate_bridge(bridge: AnalogyBridge) -> BridgeValidation:
    """Check ordered relation preservation for an explicit partial node mapping.

    A missing mapping is UNMAPPED, not a contradiction. A mapped source
    relation absent from the target graph is a counterexample to this bridge.
    Extra target relations are reported but do not invalidate a partial map.
    """
    if not isinstance(bridge, AnalogyBridge):
        raise ValueError("bridge must be an AnalogyBridge")
    node_map = dict(bridge.node_mapping)
    relation_map = dict(bridge.relation_mapping)
    target_relations = set(bridge.target.relations)
    preserved: list[Relation] = []
    violated: list[Relation] = []
    unmapped: list[Relation] = []
    matched_targets: set[Relation] = set()

    for relation in bridge.source.relations:
        if relation.relation_type not in relation_map or any(
            node_id not in node_map for node_id in relation.arguments
        ):
            unmapped.append(relation)
            continue
        mapped = Relation(
            relation_map[relation.relation_type],
            tuple(node_map[node_id] for node_id in relation.arguments),
        )
        if mapped in target_relations:
            preserved.append(relation)
            matched_targets.add(mapped)
        else:
            violated.append(relation)

    total = len(bridge.source.relations)
    mapped_count = len(preserved) + len(violated)
    coverage = mapped_count / total if total else 0.0
    preservation = len(preserved) / mapped_count if mapped_count else None
    if not mapped_count:
        status = BridgeStatus.UNTESTABLE
    elif violated:
        status = BridgeStatus.COUNTEREXAMPLE
    elif unmapped:
        status = BridgeStatus.PARTIAL
    else:
        status = BridgeStatus.STRUCTURALLY_PRESERVED

    payload = json.dumps(
        _canonical_bridge_payload(bridge),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return BridgeValidation(
        status=status,
        total_source_relations=total,
        mapped_relations=mapped_count,
        preserved_relations=tuple(sorted(preserved)),
        violated_relations=tuple(sorted(violated)),
        unmapped_relations=tuple(sorted(unmapped)),
        unmatched_target_relations=tuple(sorted(target_relations - matched_targets)),
        mapping_coverage=coverage,
        preservation_rate=preservation,
        bridge_digest=digest,
    )
