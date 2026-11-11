"""Bounded exact candidate enumeration for typed relational analogies (XSL-2)."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from prototype.yixiang_analogy import AnalogyBridge, BridgeValidation, MappingKind, RelationalGraph, validate_bridge

@dataclass(frozen=True)
class AnalogyCandidate:
    bridge: AnalogyBridge
    validation: BridgeValidation
    ordering_key: tuple[int, int, int]  # Retrieval order only, not confidence.

@dataclass(frozen=True)
class EnumerationResult:
    candidates: tuple[AnalogyCandidate, ...]
    candidate_count: int
    results_truncated: bool
    states_visited: int
    search_complete: bool
    max_search_states: int

def _validate_pairs(pairs, field):
    if not isinstance(pairs, tuple):
        raise ValueError(f"{field} must be a tuple of pairs")
    if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in pairs):
        raise ValueError(f"{field} entries must be pairs")
    for left, right in pairs:
        if not isinstance(left, str) or not left.strip() or not isinstance(right, str) or not right.strip():
            raise ValueError(f"{field} values must be non-empty strings")
    if pairs != tuple(sorted(set(pairs))):
        raise ValueError(f"{field} must be sorted and unique")
    if len({left for left, _ in pairs}) != len(pairs):
        raise ValueError(f"{field} source keys must be unique")
    if len({right for _, right in pairs}) != len(pairs):
        raise ValueError(f"{field} target values must be unique")

def enumerate_candidate_bridges(
    source: RelationalGraph,
    target: RelationalGraph,
    *,
    mapping_kind: MappingKind,
    node_type_mapping: tuple[tuple[str, str], ...],
    relation_mapping: tuple[tuple[str, str], ...],
    scope_conditions: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
    min_mapped_relations: int = 1,
    max_search_states: int = 100_000,
    max_candidates: int = 256,
) -> EnumerationResult:
    """Enumerate injective partial node mappings under explicit type/relation maps."""
    if not isinstance(source, RelationalGraph) or not isinstance(target, RelationalGraph):
        raise ValueError("source and target must be RelationalGraph values")
    if not isinstance(mapping_kind, MappingKind):
        raise ValueError("mapping_kind must be a MappingKind")
    _validate_pairs(node_type_mapping, "node_type_mapping")
    _validate_pairs(relation_mapping, "relation_mapping")
    for name, value in (("min_mapped_relations", min_mapped_relations),
                        ("max_search_states", max_search_states),
                        ("max_candidates", max_candidates)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be an integer >= 1")

    scopes = tuple(sorted(set(scope_conditions)))
    refs = tuple(sorted(set(evidence_refs)))
    AnalogyBridge(
        bridge_id="xsl2-input-validation", source=source, target=target,
        mapping_kind=mapping_kind, node_mapping=(),
        node_type_mapping=node_type_mapping, relation_mapping=relation_mapping,
        scope_conditions=scopes, evidence_refs=refs,
    )

    target_by_type = {}
    for node in target.nodes:
        target_by_type.setdefault(node.node_type, []).append(node.node_id)
    type_map = dict(node_type_mapping)
    source_ids = tuple(node.node_id for node in source.nodes)
    options = {}
    for node in source.nodes:
        compatible_type = type_map.get(node.node_type)
        compatible = target_by_type.get(compatible_type, []) if compatible_type else []
        options[node.node_id] = tuple(compatible) + (None,)

    found = {}
    current = {}
    used_targets = set()
    states_visited = 0
    exhausted = False

    def visit(index):
        nonlocal states_visited, exhausted
        if exhausted:
            return
        if states_visited >= max_search_states:
            exhausted = True
            return
        states_visited += 1
        if index == len(source_ids):
            node_mapping = tuple(sorted(current.items()))
            probe = AnalogyBridge(
                bridge_id="probe", source=source, target=target,
                mapping_kind=mapping_kind, node_mapping=node_mapping,
                node_type_mapping=node_type_mapping, relation_mapping=relation_mapping,
                scope_conditions=scopes, evidence_refs=refs,
            )
            validation = validate_bridge(probe)
            if validation.mapped_relations < min_mapped_relations:
                return
            signature = json.dumps(node_mapping, separators=(",", ":"), ensure_ascii=False)
            bridge_id = "xsl2-" + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
            bridge = AnalogyBridge(
                bridge_id=bridge_id, source=source, target=target,
                mapping_kind=mapping_kind, node_mapping=node_mapping,
                node_type_mapping=node_type_mapping, relation_mapping=relation_mapping,
                scope_conditions=scopes, evidence_refs=refs,
            )
            validation = validate_bridge(bridge)
            key = (len(validation.preserved_relations),
                   validation.mapped_relations, -len(validation.violated_relations))
            found[node_mapping] = AnalogyCandidate(bridge, validation, key)
            return
        source_id = source_ids[index]
        for target_id in options[source_id]:
            if target_id is None:
                visit(index + 1)
            elif target_id not in used_targets:
                current[source_id] = target_id
                used_targets.add(target_id)
                visit(index + 1)
                used_targets.remove(target_id)
                del current[source_id]
            if exhausted:
                return

    visit(0)
    ordered = sorted(found.values(), key=lambda c: (
        -c.ordering_key[0], -c.ordering_key[1], -c.ordering_key[2],
        c.bridge.node_mapping,
    ))
    return EnumerationResult(
        candidates=tuple(ordered[:max_candidates]),
        candidate_count=len(ordered),
        results_truncated=len(ordered) > max_candidates,
        states_visited=states_visited,
        search_complete=not exhausted,
        max_search_states=max_search_states,
    )
