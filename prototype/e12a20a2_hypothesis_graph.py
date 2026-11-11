"""E12-A20-2: typed, evidence-linked hypothesis relation graph."""
from __future__ import annotations

from dataclasses import dataclass


_EVIDENCE_KINDS = {"OBSERVATION", "MEASUREMENT_RECEIPT", "SIGNED_EVALUATOR_RECEIPT"}
_EDGE_KINDS = {"SUPPORTS", "CONTRADICTS", "REFINES", "ALTERNATIVE", "DERIVED_FROM"}


def _non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " must be a non-empty string")


def _sorted_unique(values: tuple[str, ...], name: str) -> None:
    if tuple(sorted(set(values))) != values:
        raise ValueError(name + " must be sorted and unique")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(name + " must contain non-empty strings")


@dataclass(frozen=True)
class EvidenceNode:
    evidence_id: str
    evidence_ref: str
    query_id: str
    scope: str
    kind: str
    content_digest: str | None = None

    def __post_init__(self):
        for name in ("evidence_id", "evidence_ref", "query_id", "scope"):
            _non_empty(getattr(self, name), name)
        if self.kind not in _EVIDENCE_KINDS:
            raise ValueError("unsupported evidence kind")
        if self.content_digest is not None:
            _non_empty(self.content_digest, "content_digest")


@dataclass(frozen=True)
class HypothesisNode:
    hypothesis_id: str
    query_id: str
    scope: str
    assignments: tuple[tuple[str, str], ...]
    factor_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    parent_ids: tuple[str, ...] = ()
    competition_set_id: str | None = None

    def __post_init__(self):
        for name in ("hypothesis_id", "query_id", "scope"):
            _non_empty(getattr(self, name), name)
        if not self.assignments:
            raise ValueError("hypothesis requires at least one partial assignment")
        if tuple(sorted(self.assignments)) != self.assignments:
            raise ValueError("assignments must be sorted by variable ID and value")
        variable_ids = [variable_id for variable_id, _ in self.assignments]
        if len(variable_ids) != len(set(variable_ids)):
            raise ValueError("duplicate variable assignment")
        for variable_id, value in self.assignments:
            _non_empty(variable_id, "assignment variable ID")
            _non_empty(value, "assignment value")
        _sorted_unique(self.factor_ids, "factor_ids")
        _sorted_unique(self.evidence_ids, "evidence_ids")
        _sorted_unique(self.parent_ids, "parent_ids")
        if self.competition_set_id is not None:
            _non_empty(self.competition_set_id, "competition_set_id")


@dataclass(frozen=True, order=True)
class RelationEdge:
    kind: str
    source_id: str
    target_id: str

    def __post_init__(self):
        if self.kind not in _EDGE_KINDS:
            raise ValueError("unsupported relation edge kind")
        for name in ("source_id", "target_id"):
            _non_empty(getattr(self, name), name)
        if self.source_id == self.target_id:
            raise ValueError("self edges are not allowed")


@dataclass(frozen=True)
class HypothesisGraph:
    hypotheses: tuple[HypothesisNode, ...]
    evidence: tuple[EvidenceNode, ...]
    edges: tuple[RelationEdge, ...]


def _has_cycle(parent_map: dict[str, tuple[str, ...]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for parent in parent_map[node]:
            if visit(parent):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(parent_map))


def _assignments_conflict(left: HypothesisNode, right: HypothesisNode) -> bool:
    a, b = dict(left.assignments), dict(right.assignments)
    return any(variable_id in b and b[variable_id] != value
               for variable_id, value in a.items())


def _strictly_refines(specific: HypothesisNode, general: HypothesisNode) -> bool:
    specific_map, general_map = dict(specific.assignments), dict(general.assignments)
    return (len(specific_map) > len(general_map)
            and all(specific_map.get(key) == value for key, value in general_map.items()))


def build_hypothesis_graph(
    hypotheses: tuple[HypothesisNode, ...],
    evidence: tuple[EvidenceNode, ...],
) -> HypothesisGraph:
    """Build deterministic typed edges; never infer support without an evidence node."""
    hypothesis_map = {item.hypothesis_id: item for item in hypotheses}
    evidence_map = {item.evidence_id: item for item in evidence}
    if len(hypothesis_map) != len(hypotheses):
        raise ValueError("duplicate hypothesis IDs")
    if len(evidence_map) != len(evidence):
        raise ValueError("duplicate evidence IDs")
    if set(hypothesis_map) & set(evidence_map):
        raise ValueError("hypothesis and evidence IDs must be globally unique")

    for hypothesis in hypotheses:
        for evidence_id in hypothesis.evidence_ids:
            if evidence_id not in evidence_map:
                raise ValueError("hypothesis references unknown evidence")
            item = evidence_map[evidence_id]
            if (item.query_id, item.scope) != (hypothesis.query_id, hypothesis.scope):
                raise ValueError("evidence scope/query mismatch")
        for parent_id in hypothesis.parent_ids:
            if parent_id not in hypothesis_map:
                raise ValueError("hypothesis references unknown parent")
            parent = hypothesis_map[parent_id]
            if (parent.query_id, parent.scope) != (hypothesis.query_id, hypothesis.scope):
                raise ValueError("parent scope/query mismatch")

    parent_map = {item.hypothesis_id: item.parent_ids for item in hypotheses}
    if _has_cycle(parent_map):
        raise ValueError("derived-from lineage must be acyclic")

    edges: set[RelationEdge] = set()
    for hypothesis in hypotheses:
        for evidence_id in hypothesis.evidence_ids:
            edges.add(RelationEdge("SUPPORTS", evidence_id, hypothesis.hypothesis_id))
        for parent_id in hypothesis.parent_ids:
            # Child -> parent: the edge states that the source was derived from the target.
            edges.add(RelationEdge("DERIVED_FROM", hypothesis.hypothesis_id, parent_id))

    ordered = tuple(sorted(hypotheses, key=lambda item: item.hypothesis_id))
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            if (left.query_id, left.scope) != (right.query_id, right.scope):
                continue
            if _assignments_conflict(left, right):
                edges.add(RelationEdge("CONTRADICTS", left.hypothesis_id, right.hypothesis_id))
            if (left.competition_set_id is not None
                    and left.competition_set_id == right.competition_set_id):
                edges.add(RelationEdge("ALTERNATIVE", left.hypothesis_id, right.hypothesis_id))
            if _strictly_refines(left, right):
                edges.add(RelationEdge("REFINES", left.hypothesis_id, right.hypothesis_id))
            elif _strictly_refines(right, left):
                edges.add(RelationEdge("REFINES", right.hypothesis_id, left.hypothesis_id))

    return HypothesisGraph(
        tuple(sorted(hypotheses, key=lambda item: item.hypothesis_id)),
        tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        tuple(sorted(edges)),
    )
