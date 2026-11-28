"""Native classiang structure substrate: evidence-bound symbols and bounded composition.

This module is deliberately backend-neutral and does not use token attention.
It is an executable symbolic-computational substrate, not a trained foundation
model or an autonomous perception system. Upstream adapters must supply reviewed
observations and feature proposals with evidence provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Iterable


class Decision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    ABSTAIN = "abstain"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _unique(values: tuple[str, ...], name: str, *, minimum: int = 0) -> None:
    if not isinstance(values, tuple) or any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"{name} must be a tuple of non-empty strings")
    if len(values) != len(set(values)) or len(values) < minimum:
        raise ValueError(f"{name} must contain unique values (minimum {minimum})")


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source_id: str
    source_family: str
    locator: str
    license_id: str
    reviewed: bool

    def validate(self) -> None:
        for key in ("evidence_id", "source_id", "source_family", "locator", "license_id"):
            _text(getattr(self, key), key)
        if not isinstance(self.reviewed, bool):
            raise ValueError("reviewed must be boolean")


@dataclass(frozen=True)
class Symbol:
    symbol_id: str
    domain: str
    symbol_type: str
    attributes: tuple[tuple[str, str], ...]
    evidence_ids: tuple[str, ...]
    context: tuple[str, ...] = ()
    version: int = 1

    def validate(self, evidence_ids: set[str]) -> None:
        for key in ("symbol_id", "domain", "symbol_type"):
            _text(getattr(self, key), key)
        _unique(self.evidence_ids, "symbol evidence_ids", minimum=1)
        _unique(self.context, "symbol context")
        if not set(self.evidence_ids) <= evidence_ids:
            raise ValueError("symbol references unknown evidence")
        if not isinstance(self.attributes, tuple):
            raise ValueError("attributes must be a tuple")
        keys: set[str] = set()
        for pair in self.attributes:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError("each attribute must be a (key, value) pair")
            key, value = pair
            _text(key, "attribute key")
            _text(value, "attribute value")
            if key in keys:
                raise ValueError("attribute keys must be unique")
            keys.add(key)
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("symbol version must be a positive integer")


@dataclass(frozen=True)
class Relation:
    relation_id: str
    relation_type: str
    roles: tuple[tuple[str, str], ...]
    evidence_ids: tuple[str, ...]
    conditions: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    version: int = 1

    def validate(self, symbols: set[str], evidence_ids: set[str]) -> None:
        for key in ("relation_id", "relation_type"):
            _text(getattr(self, key), key)
        if not isinstance(self.roles, tuple) or len(self.roles) < 2:
            raise ValueError("a relation needs at least two ordered roles")
        role_names: set[str] = set()
        for pair in self.roles:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ValueError("each role must be a (role_name, symbol_id) pair")
            role, symbol_id = pair
            _text(role, "role")
            _text(symbol_id, "symbol_id")
            if role in role_names:
                raise ValueError("role names must be unique within a relation")
            if symbol_id not in symbols:
                raise ValueError("relation references unknown symbol")
            role_names.add(role)
        _unique(self.evidence_ids, "relation evidence_ids", minimum=1)
        _unique(self.conditions, "relation conditions")
        _unique(self.context, "relation context")
        if not set(self.evidence_ids) <= evidence_ids:
            raise ValueError("relation references unknown evidence")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("relation version must be a positive integer")


@dataclass(frozen=True)
class SymbolGraph:
    evidence: tuple[EvidenceRef, ...]
    symbols: tuple[Symbol, ...]
    relations: tuple[Relation, ...]
    schema_version: int = 1

    def validate(self, *, require_reviewed: bool = True) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported graph schema_version")
        if not isinstance(self.evidence, tuple) or not isinstance(self.symbols, tuple) or not isinstance(self.relations, tuple):
            raise ValueError("graph collections must be tuples")
        for item in self.evidence:
            if not isinstance(item, EvidenceRef):
                raise ValueError("evidence must contain EvidenceRef")
            item.validate()
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence IDs must be unique")
        if require_reviewed and any(not item.reviewed for item in self.evidence):
            raise ValueError("unreviewed evidence cannot enter the trusted graph")
        symbol_ids = [item.symbol_id for item in self.symbols]
        if len(symbol_ids) != len(set(symbol_ids)):
            raise ValueError("symbol IDs must be unique")
        for item in self.symbols:
            item.validate(set(evidence_ids))
        relation_ids = [item.relation_id for item in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise ValueError("relation IDs must be unique")
        for item in self.relations:
            item.validate(set(symbol_ids), set(evidence_ids))


@dataclass(frozen=True)
class Composition:
    relation_ids: tuple[str, ...]
    symbol_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    shared_symbols: tuple[str, ...]
    depth: int


@dataclass(frozen=True)
class CompositionResult:
    candidates: tuple[Composition, ...]
    evaluated_pairs: int
    truncated: bool
    reason: str


def compose_relations(
    graph: SymbolGraph,
    *,
    max_depth: int = 2,
    max_candidates: int = 1000,
    require_shared_symbol: bool = True,
) -> CompositionResult:
    """Enumerate bounded relation compositions, retaining evidence lineage.

    The operator composes relation structures only when their symbol sets
    intersect (unless explicitly disabled). It does not assert that a path is
    semantically valid or causal; downstream constraints must verify it.
    """
    graph.validate()
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 2:
        raise ValueError("max_depth must be an integer >= 2")
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")
    relation_by_id = {item.relation_id: item for item in graph.relations}
    symbol_sets = {
        item.relation_id: {symbol_id for _, symbol_id in item.roles}
        for item in graph.relations
    }
    evidence_by_relation = {
        item.relation_id: set(item.evidence_ids) for item in graph.relations
    }
    found: dict[tuple[str, ...], Composition] = {}
    evaluated = 0
    truncated = False
    max_size = min(max_depth, len(graph.relations))
    for size in range(2, max_size + 1):
        for group in combinations(graph.relations, size):
            evaluated += 1
            ids = tuple(sorted(item.relation_id for item in group))
            union_symbols: set[str] = set()
            shared: set[str] = set()
            for item in group:
                current = symbol_sets[item.relation_id]
                shared = shared | (union_symbols & current)
                union_symbols |= current
            if require_shared_symbol and not shared:
                continue
            evidence = set().union(*(evidence_by_relation[item.relation_id] for item in group))
            if ids not in found and len(found) >= max_candidates:
                truncated = True
                break
            found[ids] = Composition(
                relation_ids=ids,
                symbol_ids=tuple(sorted(union_symbols)),
                evidence_ids=tuple(sorted(evidence)),
                shared_symbols=tuple(sorted(shared)),
                depth=size,
            )
        if truncated:
            break
    candidates = tuple(found[key] for key in sorted(found))
    return CompositionResult(
        candidates=candidates,
        evaluated_pairs=evaluated,
        truncated=truncated,
        reason="BUDGET_EXHAUSTED" if truncated else "SEARCH_COMPLETED_WITHIN_DECLARED_BOUND",
    )


@dataclass(frozen=True)
class StructuralAssessment:
    decision: Decision
    matched_roles: tuple[tuple[str, str], ...]
    missing_roles: tuple[str, ...]
    extra_roles: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


def assess_relation_mapping(
    source: Relation,
    target: Relation,
    *,
    role_mapping: tuple[tuple[str, str], ...],
    evidence_ids: Iterable[str],
) -> StructuralAssessment:
    """Check an explicit role mapping; no mapping is inferred from similarity."""
    if not isinstance(source, Relation) or not isinstance(target, Relation):
        raise ValueError("source and target must be Relation")
    evidence = tuple(evidence_ids)
    _unique(evidence, "assessment evidence_ids", minimum=1)
    allowed_evidence = set(source.evidence_ids) | set(target.evidence_ids)
    if not set(evidence) <= allowed_evidence:
        raise ValueError("assessment evidence must come from the supplied relations")
    mapping: dict[str, str] = {}
    targets: set[str] = set()
    for pair in role_mapping:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("role_mapping entries must be pairs")
        left, right = pair
        _text(left, "source role")
        _text(right, "target role")
        if left in mapping or right in targets:
            raise ValueError("role mapping must be injective")
        mapping[left] = right
        targets.add(right)
    source_roles = {role for role, _ in source.roles}
    target_roles = {role for role, _ in target.roles}
    if not set(mapping) <= source_roles or not targets <= target_roles:
        raise ValueError("role mapping references an unknown role")
    missing = tuple(sorted(source_roles - set(mapping)))
    extra = tuple(sorted(target_roles - targets))
    matched = tuple(sorted(mapping.items()))
    if source.relation_type != target.relation_type or missing or extra:
        return StructuralAssessment(
            Decision.ABSTAIN, matched, missing, extra, tuple(sorted(set(evidence))),
            ("RELATION_TYPE_OR_ROLE_STRUCTURE_NOT_PRESERVED",),
        )
    return StructuralAssessment(
        Decision.ACCEPT, matched, (), (), tuple(sorted(set(evidence))),
        ("EXPLICIT_ROLE_STRUCTURE_PRESERVED_ONLY",),
    )
