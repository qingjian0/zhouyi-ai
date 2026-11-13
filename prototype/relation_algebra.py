"""Explicit relation semantics for auditable analogy comparison.

Only declared symmetry and inverse rules are applied. No relation is assumed
symmetric, reversible, transitive, or causal by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RelationType:
    name: str
    symmetric: bool = False
    inverse_of: str | None = None


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class RelationScore:
    precision: float
    recall: float
    f1: float
    matched: tuple[tuple[str, str, str], ...]
    missing: tuple[tuple[str, str, str], ...]
    unexpected: tuple[tuple[str, str, str], ...]
    projected_source_count: int
    target_count: int


@dataclass(frozen=True)
class RelationOntology:
    """Versionable relation vocabulary with explicit algebraic properties."""
    types: Mapping[str, RelationType]
    ontology_id: str = "relation-ontology"
    version: str = "0.1"

    def __post_init__(self) -> None:
        if not isinstance(self.ontology_id, str) or not self.ontology_id.strip():
            raise ValueError("ontology_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.types, Mapping):
            raise ValueError("types must be a mapping")
        if not self.types:
            raise ValueError("relation ontology must define at least one type")
        for key, spec in self.types.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("relation type keys must be non-empty strings")
            if not isinstance(spec, RelationType) or spec.name != key:
                raise ValueError("relation type key must match RelationType.name")
            if type(spec.symmetric) is not bool:
                raise ValueError("symmetric must be a boolean")
            if spec.inverse_of is not None and (not isinstance(spec.inverse_of, str) or not spec.inverse_of):
                raise ValueError("inverse_of must be a non-empty relation type name")
            if spec.symmetric and spec.inverse_of is not None:
                raise ValueError("a symmetric relation cannot also declare inverse_of")
            if spec.inverse_of is not None:
                if spec.inverse_of == key or spec.inverse_of not in self.types:
                    raise ValueError(f"invalid inverse relation for {key!r}")
                counterpart = self.types[spec.inverse_of]
                if counterpart.inverse_of != key or counterpart.symmetric:
                    raise ValueError("inverse relation declarations must be reciprocal")
        object.__setattr__(self, "types", MappingProxyType(dict(self.types)))

    def normalize(self, edge: Edge) -> tuple[str, str, str]:
        if not isinstance(edge, Edge):
            raise ValueError("all relations must be Edge instances")
        if any(not isinstance(value, str) or not value for value in (edge.source, edge.target, edge.kind)):
            raise ValueError("edge endpoints and kind must be non-empty strings")
        if edge.kind not in self.types:
            raise ValueError(f"unknown relation kind: {edge.kind}")
        spec = self.types[edge.kind]
        source, target, kind = edge.source, edge.target, edge.kind
        if spec.symmetric:
            if target < source:
                source, target = target, source
        elif spec.inverse_of is not None and kind > spec.inverse_of:
            source, target = target, source
            kind = spec.inverse_of
        return source, target, kind

    def normalize_many(self, edges: Sequence[Edge]) -> frozenset[tuple[str, str, str]]:
        normalized = [self.normalize(edge) for edge in edges]
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate semantic relations after normalization")
        return frozenset(normalized)


def compare_relations(
    *,
    source_relations: Sequence[Edge],
    target_relations: Sequence[Edge],
    mapping: Mapping[str, str],
    ontology: RelationOntology,
) -> RelationScore:
    """Score mapped source edges against target edges under declared semantics.

    Every source edge endpoint must be mapped. Mapping is required to be
    injective so distinct source entities cannot collapse into one target node.
    """
    if not mapping:
        raise ValueError("entity mapping must not be empty")
    if any(not isinstance(s, str) or not s or not isinstance(t, str) or not t
           for s, t in mapping.items()):
        raise ValueError("mapping entity identifiers must be non-empty strings")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("entity mapping must be injective")

    projected = []
    for edge in source_relations:
        if edge.source not in mapping or edge.target not in mapping:
            raise ValueError("every source relation endpoint must be mapped")
        projected.append(Edge(mapping[edge.source], mapping[edge.target], edge.kind))

    expected = ontology.normalize_many(projected)
    observed = ontology.normalize_many(target_relations)
    matched = expected & observed
    missing = expected - observed
    unexpected = observed - expected
    precision = len(matched) / len(observed) if observed else (1.0 if not expected else 0.0)
    recall = len(matched) / len(expected) if expected else (1.0 if not observed else 0.0)
    f1 = 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)
    return RelationScore(
        precision=precision, recall=recall, f1=f1,
        matched=tuple(sorted(matched)), missing=tuple(sorted(missing)),
        unexpected=tuple(sorted(unexpected)),
        projected_source_count=len(expected), target_count=len(observed),
    )
