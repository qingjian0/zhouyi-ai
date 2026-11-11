"""YJ-08: bounded dynamic structural-role evolution over ordered snapshots.

Identity correspondence is used only to connect observations across time. Entity IDs
never enter YJ-07 structural role fingerprints. Incomplete observation cannot prove
role dissolution; context changes are annotations, not automatic role changes.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from prototype.yijing_operator_induction import RelationalState
from prototype.yijing_role_schema_induction import infer_structural_roles


class RoleEvolutionError(ValueError):
    """Invalid episode, evidence, or evolution budget."""


class RoleEventType(str, Enum):
    PERSIST = "PERSIST"
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    TRANSFORM = "TRANSFORM"
    EMERGE = "EMERGE"
    DISSOLVE = "DISSOLVE"


class EvolutionStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class EpisodeSnapshot:
    episode_id: str
    step: int
    state: RelationalState
    evidence_id: str
    domain: str
    # True means the snapshot is a closed-world observation for this episode.
    # Only then can complete absence support a DISSOLVE candidate.
    coverage_complete: bool = False
    intervention: str | None = None

    def __post_init__(self) -> None:
        if not self.episode_id or not self.evidence_id or not self.domain:
            raise RoleEvolutionError("episode_id, evidence_id and domain are required")
        if self.step < 0:
            raise RoleEvolutionError("snapshot step must be non-negative")


@dataclass(frozen=True)
class RoleEvent:
    event_type: RoleEventType
    episode_id: str
    from_step: int
    to_step: int
    source_role_ids: tuple[str, ...]
    target_role_ids: tuple[str, ...]
    supporting_entity_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    domain: str
    context_changed: bool
    intervention_pair: tuple[str | None, str | None]
    confidence: float
    status: EvolutionStatus = EvolutionStatus.CANDIDATE
    consecutive_support: int = 1


@dataclass(frozen=True)
class EvolutionReport:
    events: tuple[RoleEvent, ...]
    snapshots_seen: int
    transitions_seen: int
    transitions_skipped: int
    incomplete_absence_checks: int
    budget_exhausted: bool


def _role_members(snapshot: EpisodeSnapshot, max_rounds: int) -> dict[str, set[str]]:
    inferred = infer_structural_roles(snapshot.state, max_rounds=max_rounds)
    groups: dict[str, set[str]] = defaultdict(set)
    for assignment in inferred.assignments:
        groups[assignment.role_id].add(assignment.entity_id)
    return dict(groups)


def _context_changed(left: RelationalState, right: RelationalState) -> bool:
    return left.context != right.context


class DynamicRoleEvolution:
    """Infer conservative role-lineage events from an ordered episode."""

    def __init__(
        self,
        *,
        min_shared_entities: int = 1,
        min_confidence: float = 0.5,
        max_rounds: int = 3,
        max_events: int = 512,
        min_consecutive_transitions: int = 2,
    ) -> None:
        if min_shared_entities < 1 or max_events < 1 or min_consecutive_transitions < 1:
            raise RoleEvolutionError("entity support, persistence and event budgets must be positive")
        if not 0.0 <= min_confidence <= 1.0:
            raise RoleEvolutionError("min_confidence must be within [0, 1]")
        if not 0 <= max_rounds <= 8:
            raise RoleEvolutionError("max_rounds must be between 0 and 8")
        self.min_shared_entities = min_shared_entities
        self.min_confidence = min_confidence
        self.max_rounds = max_rounds
        self.max_events = max_events
        self.min_consecutive_transitions = min_consecutive_transitions

    def analyze(self, snapshots: Iterable[EpisodeSnapshot]) -> EvolutionReport:
        rows = tuple(snapshots)
        if len(rows) < 2:
            raise RoleEvolutionError("at least two snapshots are required")
        episode_ids = {row.episode_id for row in rows}
        if len(episode_ids) != 1:
            raise RoleEvolutionError("all snapshots must belong to one episode")
        if any(a.step >= b.step for a, b in zip(rows, rows[1:])):
            raise RoleEvolutionError("snapshot steps must be strictly increasing")
        evidence_ids = [row.evidence_id for row in rows]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise RoleEvolutionError("snapshot evidence IDs must be unique")

        events: list[RoleEvent] = []
        skipped = 0
        incomplete_absence = 0
        for before, after in zip(rows, rows[1:]):
            old = _role_members(before, self.max_rounds)
            new = _role_members(after, self.max_rounds)
            old_to_new: dict[str, set[str]] = defaultdict(set)
            new_to_old: dict[str, set[str]] = defaultdict(set)
            overlaps: dict[tuple[str, str], set[str]] = {}
            for old_role, old_ids in old.items():
                for new_role, new_ids in new.items():
                    shared = old_ids & new_ids
                    if len(shared) >= self.min_shared_entities:
                        overlaps[(old_role, new_role)] = shared
                        old_to_new[old_role].add(new_role)
                        new_to_old[new_role].add(old_role)

            emitted: set[tuple[RoleEventType, tuple[str, ...], tuple[str, ...]]] = set()

            def emit(kind: RoleEventType, sources: tuple[str, ...], targets: tuple[str, ...],
                     members: set[str], confidence: float) -> None:
                key = (kind, sources, targets)
                if key in emitted or confidence < self.min_confidence:
                    return
                emitted.add(key)
                events.append(RoleEvent(
                    event_type=kind,
                    episode_id=before.episode_id,
                    from_step=before.step,
                    to_step=after.step,
                    source_role_ids=sources,
                    target_role_ids=targets,
                    supporting_entity_ids=tuple(sorted(members)),
                    evidence_ids=(before.evidence_id, after.evidence_id),
                    domain=after.domain,
                    context_changed=_context_changed(before.state, after.state),
                    intervention_pair=(before.intervention, after.intervention),
                    confidence=round(min(1.0, max(0.0, confidence)), 6),
                ))

            # Split and merge are based on tracked entity correspondence, not
            # on time labels or caller-supplied role names.
            for old_role, targets in sorted(old_to_new.items()):
                if len(targets) > 1:
                    members = set().union(*(overlaps[(old_role, t)] for t in targets))
                    confidence = len(members) / max(1, len(old[old_role]))
                    emit(RoleEventType.SPLIT, (old_role,), tuple(sorted(targets)),
                         members, confidence)

            for new_role, sources in sorted(new_to_old.items()):
                if len(sources) > 1:
                    members = set().union(*(overlaps[(s, new_role)] for s in sources))
                    confidence = len(members) / max(1, len(new[new_role]))
                    emit(RoleEventType.MERGE, tuple(sorted(sources)), (new_role,),
                         members, confidence)

            for old_role, targets in sorted(old_to_new.items()):
                if len(targets) != 1:
                    continue
                new_role = next(iter(targets))
                if len(new_to_old[new_role]) != 1:
                    continue
                shared = overlaps[(old_role, new_role)]
                if old_role == new_role:
                    kind = RoleEventType.PERSIST
                else:
                    kind = RoleEventType.TRANSFORM
                confidence = len(shared) / max(1, len(old[old_role] | new[new_role]))
                emit(kind, (old_role,), (new_role,), shared, confidence)

            for new_role, members in sorted(new.items()):
                if not new_to_old.get(new_role):
                    # New means structurally novel in this transition, not
                    # metaphysically created; support is current membership.
                    emit(RoleEventType.EMERGE, (), (new_role,), members, 1.0)

            for old_role, members in sorted(old.items()):
                if old_to_new.get(old_role):
                    continue
                if members & {n.entity_id for n in after.state.nodes}:
                    # The entities remain but their structural correspondence
                    # is below threshold: do not call this a dissolution.
                    skipped += 1
                    continue
                if not after.coverage_complete:
                    incomplete_absence += 1
                    continue
                emit(RoleEventType.DISSOLVE, (old_role,), (), members, 1.0)

            if len(events) > self.max_events:
                return EvolutionReport(
                    tuple(events[:self.max_events]), len(rows), len(rows) - 1,
                    skipped, incomplete_absence, True,
                )

        # Hysteresis: an event is confirmed only when the same lineage event
        # recurs over adjacent transitions. A one-step topology fluctuation
        # remains a candidate rather than changing the durable role lineage.
        finalized: list[RoleEvent] = []
        for index, event in enumerate(events):
            key = (event.event_type, event.source_role_ids, event.target_role_ids)
            consecutive = 1
            expected_step = event.to_step
            for later in events[index + 1:]:
                later_key = (later.event_type, later.source_role_ids, later.target_role_ids)
                if later.from_step < expected_step:
                    continue
                if later.from_step > expected_step:
                    break
                if later_key == key:
                    consecutive += 1
                    expected_step = later.to_step
                else:
                    break
            if event.event_type == RoleEventType.DISSOLVE:
                # Dissolution requires repeated complete-coverage absence.
                members = set(event.supporting_entity_ids)
                absent_count = 0
                for future in (row for row in rows if row.step >= event.to_step):
                    present = {node.entity_id for node in future.state.nodes}
                    if not future.coverage_complete or members & present:
                        break
                    absent_count += 1
                consecutive = max(consecutive, absent_count)
            status = (
                EvolutionStatus.CONFIRMED
                if consecutive >= self.min_consecutive_transitions
                else EvolutionStatus.CANDIDATE
            )
            finalized.append(RoleEvent(
                event_type=event.event_type,
                episode_id=event.episode_id,
                from_step=event.from_step,
                to_step=event.to_step,
                source_role_ids=event.source_role_ids,
                target_role_ids=event.target_role_ids,
                supporting_entity_ids=event.supporting_entity_ids,
                evidence_ids=event.evidence_ids,
                domain=event.domain,
                context_changed=event.context_changed,
                intervention_pair=event.intervention_pair,
                confidence=event.confidence,
                status=status,
                consecutive_support=consecutive,
            ))
        return EvolutionReport(
            tuple(finalized), len(rows), len(rows) - 1, skipped,
            incomplete_absence, False,
        )
