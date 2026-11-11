"""YJ-10.5: temporal symmetry evolution with hysteresis.

Exact slot groups are structural observations. This module detects persistent
group changes while treating context/domain shifts as boundaries rather than
as evidence of symmetry change. It does not infer semantic or causal meaning.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from prototype.yijing_hypergraph_slot_group_induction import ExactSlotGroupObservation


class SymmetryEvolutionError(ValueError):
    """Invalid temporal symmetry observations or evolution policy."""


class SymmetryEventType(str, Enum):
    PERSIST = "PERSIST"
    SYMMETRY_BREAK = "SYMMETRY_BREAK"
    SYMMETRY_EXPAND = "SYMMETRY_EXPAND"
    RECONFIGURE = "RECONFIGURE"
    CONTEXT_SHIFT = "CONTEXT_SHIFT"


class SymmetryEventStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class SymmetryEvolutionEvent:
    event_type: SymmetryEventType
    status: SymmetryEventStatus
    relation_type: str
    from_evidence_id: str
    to_evidence_id: str
    from_step: int
    to_step: int
    source_group: tuple[tuple[int, ...], ...]
    target_group: tuple[tuple[int, ...], ...]
    consecutive_target_snapshots: int
    context_changed: bool
    domain_changed: bool


@dataclass(frozen=True)
class SymmetryEvolutionReport:
    observations_seen: int
    lineages_seen: int
    events: tuple[SymmetryEvolutionEvent, ...]
    transitions_seen: int
    context_boundaries: int


def _compose(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(left[right[index]] for index in range(len(left)))


def _validate_group(group: tuple[tuple[int, ...], ...], arity: int) -> None:
    if not group or len(group) != len(set(group)):
        raise SymmetryEvolutionError("each exact group must be non-empty and duplicate-free")
    identity = tuple(range(arity))
    members = set(group)
    if identity not in members:
        raise SymmetryEvolutionError("exact group must contain the identity")
    for item in members:
        if len(item) != arity or set(item) != set(range(arity)):
            raise SymmetryEvolutionError("group element is not a valid slot permutation")
        inverse = tuple(item.index(index) for index in range(arity))
        if inverse not in members:
            raise SymmetryEvolutionError("exact group is not inverse-closed")
        for other in members:
            if _compose(item, other) not in members:
                raise SymmetryEvolutionError("exact group is not composition-closed")


def _lineage_key(row: ExactSlotGroupObservation) -> tuple:
    return (
        row.relation_type,
        row.arity,
        row.slot_frame,
        row.entity_type_frame,
        row.semantics,
    )


def _environment_key(row: ExactSlotGroupObservation) -> tuple:
    return (
        row.context,
        row.attributes,
        row.valid_from,
        row.valid_until,
        row.domain,
    )


def _change_type(
    before: frozenset[tuple[int, ...]],
    after: frozenset[tuple[int, ...]],
) -> SymmetryEventType:
    if before == after:
        return SymmetryEventType.PERSIST
    if after < before:
        return SymmetryEventType.SYMMETRY_BREAK
    if before < after:
        return SymmetryEventType.SYMMETRY_EXPAND
    return SymmetryEventType.RECONFIGURE


def analyze_symmetry_evolution(
    observations: Iterable[ExactSlotGroupObservation],
    *,
    min_consecutive_target_snapshots: int = 2,
) -> SymmetryEvolutionReport:
    """Analyze ordered exact slot-group snapshots with persistence hysteresis.

    A structural change is CONFIRMED only when the target group remains
    unchanged for the configured number of consecutive snapshots. A change in
    context, attributes, validity interval, or domain emits an UNCERTAIN
    CONTEXT_SHIFT boundary and suppresses a direct symmetry comparison across
    that boundary. Steps need only be strictly increasing, not numerically
    contiguous.
    """
    if (not isinstance(min_consecutive_target_snapshots, int)
            or isinstance(min_consecutive_target_snapshots, bool)
            or min_consecutive_target_snapshots < 1):
        raise SymmetryEvolutionError("min_consecutive_target_snapshots must be positive")

    rows = tuple(observations)
    if not rows:
        raise SymmetryEvolutionError("at least one exact slot-group observation is required")
    evidence_ids = [row.evidence_id for row in rows]
    if any(not item for item in evidence_ids) or len(evidence_ids) != len(set(evidence_ids)):
        raise SymmetryEvolutionError("observation evidence IDs must be non-empty and unique")

    lineages: dict[tuple, list[ExactSlotGroupObservation]] = defaultdict(list)
    for row in rows:
        if row.arity < 2 or len(row.slot_frame) != row.arity:
            raise SymmetryEvolutionError("slot frame must match relation arity")
        if len(row.entity_type_frame) != row.arity:
            raise SymmetryEvolutionError("entity type frame must match relation arity")
        if row.step < 0:
            raise SymmetryEvolutionError("snapshot step must be non-negative")
        _validate_group(row.exact_group, row.arity)
        lineages[_lineage_key(row)].append(row)

    events: list[SymmetryEvolutionEvent] = []
    transitions_seen = 0
    context_boundaries = 0
    for key, lineage in sorted(lineages.items(), key=lambda item: repr(item[0])):
        ordered = sorted(lineage, key=lambda item: item.step)
        steps = [row.step for row in ordered]
        if len(steps) != len(set(steps)):
            raise SymmetryEvolutionError(
                "multiple observations at one step share a relation lineage; "
                "split the lineage or provide an explicit coordinate frame"
            )

        for index, (before, after) in enumerate(zip(ordered, ordered[1:])):
            transitions_seen += 1
            context_changed = (
                before.context != after.context
                or before.attributes != after.attributes
                or before.valid_from != after.valid_from
                or before.valid_until != after.valid_until
            )
            domain_changed = before.domain != after.domain
            if context_changed or domain_changed:
                context_boundaries += 1
                events.append(SymmetryEvolutionEvent(
                    event_type=SymmetryEventType.CONTEXT_SHIFT,
                    status=SymmetryEventStatus.UNCERTAIN,
                    relation_type=before.relation_type,
                    from_evidence_id=before.evidence_id,
                    to_evidence_id=after.evidence_id,
                    from_step=before.step,
                    to_step=after.step,
                    source_group=before.exact_group,
                    target_group=after.exact_group,
                    consecutive_target_snapshots=1,
                    context_changed=context_changed,
                    domain_changed=domain_changed,
                ))
                continue

            before_group = frozenset(before.exact_group)
            after_group = frozenset(after.exact_group)
            event_type = _change_type(before_group, after_group)
            if event_type == SymmetryEventType.PERSIST:
                continue

            support = 0
            for candidate in ordered[index + 1:]:
                if (_environment_key(candidate) != _environment_key(after)
                        or candidate.exact_group != after.exact_group):
                    break
                support += 1
            status = (
                SymmetryEventStatus.CONFIRMED
                if support >= min_consecutive_target_snapshots
                else SymmetryEventStatus.CANDIDATE
            )
            events.append(SymmetryEvolutionEvent(
                event_type=event_type,
                status=status,
                relation_type=before.relation_type,
                from_evidence_id=before.evidence_id,
                to_evidence_id=after.evidence_id,
                from_step=before.step,
                to_step=after.step,
                source_group=before.exact_group,
                target_group=after.exact_group,
                consecutive_target_snapshots=support,
                context_changed=False,
                domain_changed=False,
            ))

    return SymmetryEvolutionReport(
        observations_seen=len(rows),
        lineages_seen=len(lineages),
        events=tuple(events),
        transitions_seen=transitions_seen,
        context_boundaries=context_boundaries,
    )
