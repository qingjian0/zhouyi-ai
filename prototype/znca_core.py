"""ZNCA N1: dependency-free relational state dynamics reference core.

This is an executable symbolic substrate, not a trained neural network.
It deliberately keeps observations, evidence, state, and analogy proposals
separate so that later learned operators can be evaluated against it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class StateError(ValueError):
    """Invalid event, state transition, or structural mapping."""


class EventKind(str, Enum):
    OBSERVE = "observe"
    RETRACT = "retract"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_ref: str
    observed_at: int

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.source_ref.strip():
            raise StateError("evidence_id and source_ref are required")
        if self.observed_at < 0:
            raise StateError("observed_at must be non-negative")


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.entity_id.strip() or not self.entity_type.strip():
            raise StateError("entity_id and entity_type are required")
        keys = [key for key, _ in self.attributes]
        if len(keys) != len(set(keys)):
            raise StateError("entity attribute keys must be unique")


@dataclass(frozen=True)
class RoleBinding:
    role: str
    entity_id: str

    def __post_init__(self) -> None:
        if not self.role.strip() or not self.entity_id.strip():
            raise StateError("role and entity_id are required")


@dataclass(frozen=True)
class Relation:
    assertion_id: str
    relation_type: str
    participants: tuple[RoleBinding, ...]
    evidence_refs: tuple[str, ...]
    valid_from: int
    valid_until: int | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.assertion_id.strip() or not self.relation_type.strip():
            raise StateError("assertion_id and relation_type are required")
        if len(self.participants) < 2:
            raise StateError("a relation requires at least two participants")
        roles = [p.role for p in self.participants]
        if len(roles) != len(set(roles)):
            raise StateError("participant roles must be unique within a relation")
        if len(self.evidence_refs) != len(set(self.evidence_refs)) or not self.evidence_refs:
            raise StateError("relation requires unique evidence references")
        if self.valid_from < 0 or (self.valid_until is not None and self.valid_until < self.valid_from):
            raise StateError("invalid relation validity interval")
        if not 0.0 <= self.confidence <= 1.0:
            raise StateError("confidence must be in [0, 1]")

    def role_map(self) -> dict[str, str]:
        return {p.role: p.entity_id for p in self.participants}


@dataclass(frozen=True)
class ObservationEvent:
    event_id: str
    occurred_at: int
    evidence: tuple[Evidence, ...] = ()
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    retract_assertion_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id.strip() or self.occurred_at < 0:
            raise StateError("event_id and non-negative occurred_at are required")
        if self.relations and self.retract_assertion_ids:
            raise StateError("one event cannot both assert and retract relations")
        if len({e.evidence_id for e in self.evidence}) != len(self.evidence):
            raise StateError("duplicate evidence ids in event")
        if len({e.entity_id for e in self.entities}) != len(self.entities):
            raise StateError("duplicate entity ids in event")
        if len({r.assertion_id for r in self.relations}) != len(self.relations):
            raise StateError("duplicate assertion ids in event")


class QueryStatus(str, Enum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class QueryResult:
    status: QueryStatus
    relations: tuple[Relation, ...]
    scanned: int


@dataclass(frozen=True)
class RelationQuery:
    relation_type: str
    role_constraints: tuple[tuple[str, str], ...] = ()
    at_time: int | None = None
    limit: int = 32

    def __post_init__(self) -> None:
        if not self.relation_type.strip() or self.limit < 1:
            raise StateError("query relation_type and positive limit are required")
        roles = [role for role, _ in self.role_constraints]
        if len(roles) != len(set(roles)):
            raise StateError("query role constraints must be unique")
        if self.at_time is not None and self.at_time < 0:
            raise StateError("at_time must be non-negative")


@dataclass
class CognitiveState:
    """Event-sourced state with active assertions and explicit provenance."""

    entities: dict[str, Entity] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    assertions: dict[str, Relation] = field(default_factory=dict)
    retracted: set[str] = field(default_factory=set)
    event_ids: set[str] = field(default_factory=set)
    event_ledger: list[ObservationEvent] = field(default_factory=list)
    _by_relation_type: dict[str, set[str]] = field(default_factory=dict, init=False, repr=False)
    _by_role_entity: dict[tuple[str, str], set[str]] = field(default_factory=dict, init=False, repr=False)
    _assertion_order: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def apply(self, event: ObservationEvent) -> None:
        if event.event_id in self.event_ids:
            raise StateError("event_id already applied")
        new_evidence = {item.evidence_id for item in event.evidence}
        if new_evidence & self.evidence.keys():
            raise StateError("evidence_id already exists")
        new_entities = {item.entity_id for item in event.entities}
        if new_entities & self.entities.keys():
            raise StateError("entity_id already exists; use a versioned entity id")
        for relation in event.relations:
            if relation.assertion_id in self.assertions:
                raise StateError("assertion_id already exists")
            if not set(relation.evidence_refs) <= (self.evidence.keys() | new_evidence):
                raise StateError("relation references unknown evidence")
            if not {p.entity_id for p in relation.participants} <= (self.entities.keys() | new_entities):
                raise StateError("relation references unknown entity")
            if relation.valid_from > event.occurred_at:
                raise StateError("relation cannot become valid after its observation event")
        for assertion_id in event.retract_assertion_ids:
            if assertion_id not in self.assertions or assertion_id in self.retracted:
                raise StateError("cannot retract an unknown or already retracted assertion")
        self.evidence.update((item.evidence_id, item) for item in event.evidence)
        self.entities.update((item.entity_id, item) for item in event.entities)
        for relation in event.relations:
            self.assertions[relation.assertion_id] = relation
            self._assertion_order[relation.assertion_id] = len(self._assertion_order)
            self._by_relation_type.setdefault(relation.relation_type, set()).add(relation.assertion_id)
            for participant in relation.participants:
                self._by_role_entity.setdefault(
                    (participant.role, participant.entity_id), set()
                ).add(relation.assertion_id)
        self.retracted.update(event.retract_assertion_ids)
        self.event_ids.add(event.event_id)
        self.event_ledger.append(event)

    def query(self, query: RelationQuery, *, scan_budget: int = 10_000) -> QueryResult:
        if scan_budget < 1:
            raise StateError("scan_budget must be positive")
        matches: list[Relation] = []
        scanned = 0
        constraints = dict(query.role_constraints)
        candidate_ids = set(self._by_relation_type.get(query.relation_type, set()))
        for role, entity_id in constraints.items():
            candidate_ids.intersection_update(
                self._by_role_entity.get((role, entity_id), set())
            )
        ordered_ids = sorted(candidate_ids, key=self._assertion_order.__getitem__)
        for assertion_id in ordered_ids:
            if scanned >= scan_budget:
                return QueryResult(QueryStatus.BUDGET_EXHAUSTED, tuple(matches), scanned)
            scanned += 1
            assertion = self.assertions[assertion_id]
            if assertion_id in self.retracted:
                continue
            if query.at_time is not None:
                if assertion.valid_from > query.at_time:
                    continue
                if assertion.valid_until is not None and query.at_time > assertion.valid_until:
                    continue
            roles = assertion.role_map()
            if all(roles.get(role) == entity_id for role, entity_id in constraints.items()):
                matches.append(assertion)
                if len(matches) >= query.limit:
                    return QueryResult(QueryStatus.FOUND, tuple(matches), scanned)
        status = QueryStatus.FOUND if matches else QueryStatus.NOT_FOUND
        return QueryResult(status, tuple(matches), scanned)

    def source_refs(self, relation: Relation) -> tuple[str, ...]:
        return tuple(self.evidence[eid].source_ref for eid in relation.evidence_refs)


@dataclass(frozen=True)
class AnalogyMap:
    """A partial, typed structural map; it is not a truth-transfer rule."""

    entity_map: tuple[tuple[str, str], ...]
    relation_type_map: tuple[tuple[str, str], ...]
    role_map: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]
    scope: str

    def __post_init__(self) -> None:
        if not self.scope.strip() or not self.evidence_refs:
            raise StateError("analogy map requires scope and evidence")
        for pairs, label in ((self.entity_map, "entity"),
                             (self.relation_type_map, "relation type"),
                             (self.role_map, "role")):
            left = [a for a, _ in pairs]
            if len(left) != len(set(left)):
                raise StateError(f"duplicate source {label} in map")
        targets = [target for _, target in self.entity_map]
        if len(targets) != len(set(targets)):
            raise StateError("entity map must be injective in N1")
        if len({x for x in self.evidence_refs}) != len(self.evidence_refs):
            raise StateError("analogy evidence refs must be unique")


@dataclass(frozen=True)
class AnalogyAudit:
    mapped_relations: int
    preserved_relations: int
    unmapped_relations: int
    preservation_ratio: float
    violations: tuple[str, ...]


def audit_analogy(source: Iterable[Relation], target: Iterable[Relation],
                  mapping: AnalogyMap) -> AnalogyAudit:
    """Measure relation preservation against observed target structure.

    This function only audits structural correspondence. It does not infer
    that unobserved target facts are true or that a mapping is causally valid.
    """
    entity_map = dict(mapping.entity_map)
    relation_map = dict(mapping.relation_type_map)
    role_map = dict(mapping.role_map)
    target_signatures = {
        (rel.relation_type, tuple(sorted(rel.role_map().items())))
        for rel in target
    }
    mapped = preserved = unmapped = 0
    violations: list[str] = []
    for rel in source:
        if rel.relation_type not in relation_map:
            unmapped += 1
            continue
        roles = rel.role_map()
        if any(entity not in entity_map for entity in roles.values()):
            unmapped += 1
            continue
        if any(role not in role_map for role in roles):
            unmapped += 1
            continue
        mapped += 1
        signature = (
            relation_map[rel.relation_type],
            tuple(sorted((role_map[role], entity_map[entity])
                         for role, entity in roles.items())),
        )
        if signature in target_signatures:
            preserved += 1
        else:
            violations.append(f"{rel.assertion_id}: mapped relation not observed in target")
    ratio = preserved / mapped if mapped else 0.0
    return AnalogyAudit(mapped, preserved, unmapped, ratio, tuple(violations))
