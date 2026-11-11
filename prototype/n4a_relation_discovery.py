"""N4-A: bounded, evidence-audited relational motif discovery.

This is a deterministic structural miner, not a learned semantic parser.
Cases provide abstract role features and relation families; the miner finds
recurrent connected motifs, tracks counterexamples, and evaluates held-out
support before emitting candidate proposals. It never mutates canonical state.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


class DiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    node_id: str
    surface_type: str
    role_features: tuple[str, ...]


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation_family: str
    surface_relation: str = ""


@dataclass(frozen=True)
class RelationalCase:
    case_id: str
    domain: str
    scope: str
    partition: str
    outcome: bool
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class MotifInstance:
    case_id: str
    domain: str
    node_ids_by_role: tuple[str, ...]
    mapping_ambiguous: bool


@dataclass(frozen=True)
class RelationCandidate:
    candidate_id: str
    signature: str
    role_count: int
    support_case_ids: tuple[str, ...]
    counterexample_case_ids: tuple[str, ...]
    validation_positive_ids: tuple[str, ...]
    validation_negative_ids: tuple[str, ...]
    domains: tuple[str, ...]
    instances: tuple[MotifInstance, ...]
    train_precision: float
    validation_precision: float
    validation_base_rate: float
    validation_lift: float
    posterior_mean: float


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[RelationCandidate, ...]
    cases_seen: int
    motifs_seen: int
    motifs_over_budget: int
    rejected_low_support: int
    rejected_validation: int


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DiscoveryError(f"{field} must be a non-empty string")


def derive_structural_role_features(
    nodes: tuple[Node, ...], edges: tuple[Edge, ...], *, rounds: int = 2,
    node_ids: tuple[str, ...] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Infer ID- and surface-type-independent roles by relational color refinement.

    This is a structural descriptor, not semantic understanding. It starts
    from supplied abstract features when present, otherwise from one shared
    untyped color, then repeatedly hashes directed relation neighborhoods.
    """
    if rounds < 0:
        raise DiscoveryError("role refinement rounds cannot be negative")
    selected = set(node_ids) if node_ids is not None else {n.node_id for n in nodes}
    active_nodes = tuple(node for node in nodes if node.node_id in selected)
    active_edges = tuple(edge for edge in edges
                         if edge.source in selected and edge.target in selected)
    if len(active_nodes) != len(selected) or len(active_nodes) < 1:
        raise DiscoveryError("role refinement node selection is invalid")
    supplied = [bool(node.role_features) for node in active_nodes]
    if any(supplied) and not all(supplied):
        raise DiscoveryError("role_features must be supplied for all nodes or none")
    labels = {
        node.node_id: json.dumps(
            sorted(node.role_features) if all(supplied) else ["untyped"],
            ensure_ascii=False, separators=(",", ":"),
        )
        for node in active_nodes
    }
    for _ in range(rounds):
        updated: dict[str, str] = {}
        for node in nodes:
            incoming = sorted(
                (edge.relation_family, labels[edge.source])
                for edge in active_edges if edge.target == node.node_id
            )
            outgoing = sorted(
                (edge.relation_family, labels[edge.target])
                for edge in active_edges if edge.source == node.node_id
            )
            payload = {
                "self": labels[node.node_id],
                "incoming": incoming,
                "outgoing": outgoing,
            }
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"))
            updated[node.node_id] = hashlib.sha256(
                encoded.encode("utf-8")
            ).hexdigest()
        labels = updated
    return {
        node.node_id: tuple(sorted(node.role_features or ("untyped",)))
        + ("wl:" + labels[node.node_id],)
        for node in active_nodes
    }


def _canonical_motif(nodes: tuple[Node, ...], edges: tuple[Edge, ...],
                     subset: tuple[str, ...]) -> tuple[str, tuple[str, ...], bool]:
    """Return an ID-invariant signature and IDs ordered by canonical role."""
    by_id = {node.node_id: node for node in nodes}
    inferred_roles = derive_structural_role_features(nodes, edges, node_ids=subset)
    selected = set(subset)
    edge_labels = [
        (edge.source, edge.target, edge.relation_family)
        for edge in edges
        if edge.source in selected and edge.target in selected
    ]
    best_signature: str | None = None
    best_order: tuple[str, ...] | None = None
    best_count = 0
    for order in itertools.permutations(subset):
        position = {node_id: i for i, node_id in enumerate(order)}
        role_labels = [list(inferred_roles[node_id]) for node_id in order]
        relation_labels = sorted(
            (position[source], position[target], relation)
            for source, target, relation in edge_labels
        )
        payload = {"roles": role_labels, "relations": relation_labels}
        signature = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"))
        if best_signature is None or signature < best_signature:
            best_signature, best_order, best_count = signature, order, 1
        elif signature == best_signature:
            best_count += 1
    assert best_signature is not None and best_order is not None
    return best_signature, best_order, best_count > 1


def _is_connected(subset: tuple[str, ...], edges: tuple[Edge, ...]) -> bool:
    selected = set(subset)
    adjacency = {node_id: set() for node_id in subset}
    for edge in edges:
        if edge.source in selected and edge.target in selected:
            adjacency[edge.source].add(edge.target)
            adjacency[edge.target].add(edge.source)
    reached = {subset[0]}
    frontier = [subset[0]]
    while frontier:
        current = frontier.pop()
        for neighbor in adjacency[current] - reached:
            reached.add(neighbor)
            frontier.append(neighbor)
    return len(reached) == len(subset)


def _validate_case(case: RelationalCase) -> None:
    for value, field in (
        (case.case_id, "case_id"), (case.domain, "domain"),
        (case.scope, "scope"),
    ):
        _require_text(value, field)
    if case.partition not in ("train", "validation"):
        raise DiscoveryError("partition must be train or validation")
    if not isinstance(case.outcome, bool):
        raise DiscoveryError("outcome must be boolean")
    node_ids = [node.node_id for node in case.nodes]
    if len(node_ids) != len(set(node_ids)):
        raise DiscoveryError("node ids must be unique within a case")
    if len(node_ids) < 2:
        raise DiscoveryError("each case requires at least two nodes")
    for node in case.nodes:
        _require_text(node.node_id, "node_id")
        _require_text(node.surface_type, "surface_type")
        if any(not x.strip() for x in node.role_features):
            raise DiscoveryError("role_features cannot contain empty values")
    for edge in case.edges:
        if edge.source not in set(node_ids) or edge.target not in set(node_ids):
            raise DiscoveryError("edge endpoint is not present in its case")
        if edge.source == edge.target:
            raise DiscoveryError("self loops are not supported in N4-A motifs")
        _require_text(edge.relation_family, "relation_family")


def _case_motifs(case: RelationalCase, *, max_nodes: int,
                 max_subsets: int) -> tuple[dict[str, tuple[tuple[str, ...], bool]], int]:
    nodes = tuple(sorted(case.nodes, key=lambda node: node.node_id))
    ids = tuple(node.node_id for node in nodes)
    motifs: dict[str, tuple[str, ...]] = {}
    visited = 0
    for size in range(2, min(max_nodes, len(ids)) + 1):
        for subset in itertools.combinations(ids, size):
            visited += 1
            if visited > max_subsets:
                return {}, 1
            if not _is_connected(subset, case.edges):
                continue
            signature, canonical_order, mapping_ambiguous = _canonical_motif(
                nodes, case.edges, subset
            )
            motifs.setdefault(signature, (canonical_order, mapping_ambiguous))
    return motifs, 0


def discover_relations(
    cases: Iterable[RelationalCase],
    *,
    min_train_support: int = 3,
    min_validation_support: int = 2,
    min_validation_lift: float = 0.10,
    max_nodes: int = 4,
    max_subsets_per_case: int = 20_000,
    max_candidates: int = 2_000,
) -> DiscoveryResult:
    """Mine recurring connected motifs and require held-out validation.

    A candidate is a structural hypothesis only. Abstract role features and
    relation families are supplied abstractions, not inferred semantics.
    """
    if min_train_support < 1 or min_validation_support < 1:
        raise DiscoveryError("support thresholds must be positive")
    if max_nodes < 2 or max_subsets_per_case < 1 or max_candidates < 1:
        raise DiscoveryError("motif and candidate budgets must be positive")
    if min_validation_lift < 0:
        raise DiscoveryError("min_validation_lift cannot be negative")

    case_list = tuple(cases)
    if not case_list:
        raise DiscoveryError("at least one case is required")
    seen_ids: set[str] = set()
    train_base: dict[str, list[bool]] = defaultdict(list)
    validation_base: dict[str, list[bool]] = defaultdict(list)
    aggregate: dict[tuple[str, str], dict] = {}
    motifs_seen = 0
    over_budget = 0

    for case in case_list:
        _validate_case(case)
        if case.case_id in seen_ids:
            raise DiscoveryError("case_id values must be globally unique")
        seen_ids.add(case.case_id)
        base = train_base if case.partition == "train" else validation_base
        base[case.scope].append(case.outcome)
        motifs, exceeded = _case_motifs(
            case, max_nodes=max_nodes, max_subsets=max_subsets_per_case
        )
        over_budget += exceeded
        motifs_seen += len(motifs)
        for signature, (ordered_ids, mapping_ambiguous) in motifs.items():
            key = (case.scope, signature)
            record = aggregate.setdefault(key, {
                "train_pos": set(), "train_neg": set(),
                "valid_pos": set(), "valid_neg": set(),
                "domains": set(), "instances": [],
                "role_count": len(ordered_ids),
            })
            bucket = (
                "train_pos" if case.partition == "train" and case.outcome else
                "train_neg" if case.partition == "train" else
                "valid_pos" if case.outcome else "valid_neg"
            )
            record[bucket].add(case.case_id)
            record["domains"].add(case.domain)
            record["instances"].append(
                MotifInstance(case.case_id, case.domain, ordered_ids, mapping_ambiguous)
            )

    candidates: list[RelationCandidate] = []
    low_support = 0
    validation_rejected = 0
    for (scope, signature), record in sorted(aggregate.items()):
        train_pos = record["train_pos"]
        train_neg = record["train_neg"]
        valid_pos = record["valid_pos"]
        valid_neg = record["valid_neg"]
        if len(train_pos) < min_train_support:
            low_support += 1
            continue
        valid_total = len(valid_pos) + len(valid_neg)
        if len(valid_pos) < min_validation_support or valid_total == 0:
            validation_rejected += 1
            continue
        base_values = validation_base.get(scope, [])
        base_rate = sum(base_values) / len(base_values) if base_values else 0.0
        precision = len(valid_pos) / valid_total
        lift = precision - base_rate
        if lift < min_validation_lift:
            validation_rejected += 1
            continue
        candidate_id = hashlib.sha256(
            (scope + "\n" + signature).encode("utf-8")
        ).hexdigest()[:16]
        train_total = len(train_pos) + len(train_neg)
        posterior = (len(train_pos) + 1) / (train_total + 2)
        candidates.append(RelationCandidate(
            candidate_id=candidate_id, signature=signature,
            role_count=record["role_count"],
            support_case_ids=tuple(sorted(train_pos)),
            counterexample_case_ids=tuple(sorted(train_neg)),
            validation_positive_ids=tuple(sorted(valid_pos)),
            validation_negative_ids=tuple(sorted(valid_neg)),
            domains=tuple(sorted(record["domains"])),
            instances=tuple(sorted(record["instances"], key=lambda x: x.case_id)),
            train_precision=len(train_pos) / train_total if train_total else 0.0,
            validation_precision=precision,
            validation_base_rate=base_rate,
            validation_lift=lift,
            posterior_mean=posterior,
        ))

    candidates.sort(
        key=lambda item: (-item.validation_lift, -item.validation_precision,
                          -len(item.support_case_ids), item.candidate_id)
    )
    if len(candidates) > max_candidates:
        over_budget += len(candidates) - max_candidates
        candidates = candidates[:max_candidates]
    return DiscoveryResult(
        tuple(candidates), len(case_list), motifs_seen, over_budget,
        low_support, validation_rejected,
    )
