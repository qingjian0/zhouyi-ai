"""YJ-09: typed, role-bound hypergraph representation and conservative lineage.

Hyperedges remain atomic n-ary relations. This module never projects them into
pairwise edges. Entity IDs support temporal correspondence only; structural
signatures are expressed through typed role slots and relation semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class HypergraphError(ValueError):
    """Invalid typed hypergraph, evidence, or episode."""


@dataclass(frozen=True, order=True)
class Entity:
    entity_id: str
    entity_type: str

    def __post_init__(self) -> None:
        if not self.entity_id or not self.entity_type:
            raise HypergraphError("entity_id and entity_type are required")


@dataclass(frozen=True, order=True)
class RoleBinding:
    role: str
    entity_id: str

    def __post_init__(self) -> None:
        if not self.role or not self.entity_id:
            raise HypergraphError("role and entity_id are required")


@dataclass(frozen=True)
class Hyperedge:
    edge_id: str
    relation_type: str
    bindings: tuple[RoleBinding, ...]
    evidence_ids: tuple[str, ...]
    context: tuple[tuple[str, str], ...] = ()
    valid_from: int | None = None
    valid_until: int | None = None
    attributes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.edge_id or not self.relation_type:
            raise HypergraphError("edge_id and relation_type are required")
        if len(self.bindings) < 2:
            raise HypergraphError("a hyperedge requires at least two role bindings")
        roles = [b.role for b in self.bindings]
        if len(roles) != len(set(roles)):
            raise HypergraphError("role names must be unique within a hyperedge")
        if len(set(self.evidence_ids)) != len(self.evidence_ids) or not self.evidence_ids:
            raise HypergraphError("hyperedges require unique evidence IDs")
        if tuple(sorted(self.context)) != self.context:
            raise HypergraphError("context must be sorted")
        if tuple(sorted(self.attributes)) != self.attributes:
            raise HypergraphError("attributes must be sorted")
        if self.valid_from is not None and self.valid_from < 0:
            raise HypergraphError("valid_from must be non-negative")
        if self.valid_until is not None and (
            self.valid_from is None or self.valid_until <= self.valid_from
        ):
            raise HypergraphError("valid_until must be greater than valid_from")


@dataclass(frozen=True)
class HypergraphState:
    entities: tuple[Entity, ...]
    hyperedges: tuple[Hyperedge, ...]
    context: tuple[tuple[str, str], ...] = ()
    step: int = 0
    evidence_id: str = ""
    domain: str = ""
    coverage_complete: bool = False

    def __post_init__(self) -> None:
        if self.step < 0:
            raise HypergraphError("step must be non-negative")
        if not self.evidence_id or not self.domain:
            raise HypergraphError("snapshot evidence_id and domain are required")
        ids = [e.entity_id for e in self.entities]
        edge_ids = [e.edge_id for e in self.hyperedges]
        if len(ids) != len(set(ids)) or len(edge_ids) != len(set(edge_ids)):
            raise HypergraphError("entity and hyperedge IDs must be unique")
        if tuple(sorted(self.context)) != self.context:
            raise HypergraphError("snapshot context must be sorted")
        known = set(ids)
        for edge in self.hyperedges:
            if any(binding.entity_id not in known for binding in edge.bindings):
                raise HypergraphError("hyperedge references an unknown entity")

    def entity_types(self) -> dict[str, str]:
        return {item.entity_id: item.entity_type for item in self.entities}


def structural_signature(edge: Hyperedge, state: HypergraphState) -> tuple:
    """Alpha-invariant signature retaining ordered semantic role slots.

    Concrete entity IDs and edge IDs are excluded. Role names and entity types
    are retained, so swapping actor/recipient is not treated as equivalent.
    """
    types = state.entity_types()
    return (
        edge.relation_type,
        tuple((binding.role, types[binding.entity_id]) for binding in edge.bindings),
        edge.context,
        edge.attributes,
        edge.valid_from is not None,
        edge.valid_until is not None,
    )


@dataclass(frozen=True)
class HyperedgeEvent:
    kind: str
    from_step: int
    to_step: int
    source_edge_ids: tuple[str, ...]
    target_edge_ids: tuple[str, ...]
    shared_entity_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class HypergraphEvolutionReport:
    events: tuple[HyperedgeEvent, ...]
    transitions_seen: int
    incomplete_absence_checks: int


class DynamicHypergraphEvolution:
    """Compare ordered snapshots without reducing n-ary edges to binary edges."""

    def __init__(self, *, min_shared_entities: int = 2,
                 min_consecutive_transitions: int = 2,
                 max_events: int = 1024) -> None:
        if min_shared_entities < 1 or min_consecutive_transitions < 1 or max_events < 1:
            raise HypergraphError("support, persistence and event budgets must be positive")
        self.min_shared_entities = min_shared_entities
        self.min_consecutive_transitions = min_consecutive_transitions
        self.max_events = max_events

    def analyze(self, snapshots: Iterable[HypergraphState]) -> HypergraphEvolutionReport:
        rows = tuple(snapshots)
        if len(rows) < 2:
            raise HypergraphError("at least two snapshots are required")
        if any(a.step >= b.step for a, b in zip(rows, rows[1:])):
            raise HypergraphError("snapshot steps must be strictly increasing")
        if len({row.evidence_id for row in rows}) != len(rows):
            raise HypergraphError("snapshot evidence IDs must be unique")
        events: list[HyperedgeEvent] = []
        incomplete = 0
        keys_by_transition: dict[int, set[tuple]] = {}

        for before, after in zip(rows, rows[1:]):
            old = {e.edge_id: e for e in before.hyperedges}
            new = {e.edge_id: e for e in after.hyperedges}
            old_to_new: dict[str, set[str]] = {}
            new_to_old: dict[str, set[str]] = {}
            overlaps: dict[tuple[str, str], set[str]] = {}
            for old_id, left in old.items():
                left_ids = {b.entity_id for b in left.bindings}
                for new_id, right in new.items():
                    shared = left_ids & {b.entity_id for b in right.bindings}
                    if len(shared) >= self.min_shared_entities:
                        overlaps[(old_id, new_id)] = shared
                        old_to_new.setdefault(old_id, set()).add(new_id)
                        new_to_old.setdefault(new_id, set()).add(old_id)

            emitted: set[tuple] = set()
            def emit(kind: str, sources: tuple[str, ...], targets: tuple[str, ...],
                     members: set[str]) -> None:
                key = (kind, sources, targets)
                if key in emitted:
                    return
                emitted.add(key)
                events.append(HyperedgeEvent(
                    kind, before.step, after.step, sources, targets,
                    tuple(sorted(members)), (before.evidence_id, after.evidence_id),
                    "CANDIDATE",
                ))

            for old_id, targets in sorted(old_to_new.items()):
                if len(targets) > 1:
                    shared = set().union(*(overlaps[(old_id, t)] for t in targets))
                    emit("SPLIT", (old_id,), tuple(sorted(targets)), shared)
            for new_id, sources in sorted(new_to_old.items()):
                if len(sources) > 1:
                    shared = set().union(*(overlaps[(s, new_id)] for s in sources))
                    emit("MERGE", tuple(sorted(sources)), (new_id,), shared)
            for old_id, targets in sorted(old_to_new.items()):
                if len(targets) != 1:
                    continue
                new_id = next(iter(targets))
                if len(new_to_old[new_id]) != 1:
                    continue
                left, right = old[old_id], new[new_id]
                if structural_signature(left, before) == structural_signature(right, after):
                    kind = "PERSIST"
                else:
                    kind = "TRANSFORM"
                emit(kind, (old_id,), (new_id,), overlaps[(old_id, new_id)])
            for new_id in sorted(set(new) - set(new_to_old)):
                emit("EMERGE", (), (new_id,), {b.entity_id for b in new[new_id].bindings})
            for old_id in sorted(set(old) - set(old_to_new)):
                members = {b.entity_id for b in old[old_id].bindings}
                present = {e.entity_id for e in after.entities}
                if members & present:
                    continue
                if not after.coverage_complete:
                    incomplete += 1
                    continue
                emit("DISSOLVE", (old_id,), (), members)

            keys_by_transition[before.step] = emitted
            if len(events) >= self.max_events:
                events = events[:self.max_events]
                break

        next_step = {a.step: b.step for a, b in zip(rows, rows[1:])}
        finalized = []
        for event in events:
            key = (event.kind, event.source_edge_ids, event.target_edge_ids)
            count = 1
            cursor = event.to_step
            if event.kind == "DISSOLVE":
                # Absence is supported by successive complete snapshots, not
                # by repeating a transition event that cannot recur once gone.
                members = set(event.shared_entity_ids)
                for future in (row for row in rows if row.step >= event.to_step):
                    present = {entity.entity_id for entity in future.entities}
                    if not future.coverage_complete or members & present:
                        break
                    count += 1
            else:
                while cursor in keys_by_transition and key in keys_by_transition[cursor] and cursor in next_step:
                    count += 1
                    cursor = next_step[cursor]
            status = "CONFIRMED" if count >= self.min_consecutive_transitions else "CANDIDATE"
            finalized.append(HyperedgeEvent(
                event.kind, event.from_step, event.to_step,
                event.source_edge_ids, event.target_edge_ids,
                event.shared_entity_ids, event.evidence_ids, status,
            ))
        return HypergraphEvolutionReport(tuple(finalized), len(rows) - 1, incomplete)
