"""Dynamic analogy evaluation by transition preservation.

The evaluator checks whether an explicit cross-domain entity/state mapping
preserves typed facts and directed state transitions. It is a finite symbolic
simulation check, not causal identification or a learned analogy model.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True, order=True)
class RelationAtom:
    source: str
    target: str
    kind: str


@dataclass(frozen=True)
class StateSnapshot:
    state_id: str
    step: int
    relations: tuple[RelationAtom, ...]


@dataclass(frozen=True)
class StateTransition:
    source_state: str
    target_state: str
    event_kind: str


@dataclass(frozen=True)
class TransitionSystem:
    domain: str
    entities: tuple[str, ...]
    snapshots: tuple[StateSnapshot, ...]
    transitions: tuple[StateTransition, ...]

    def validate(self) -> None:
        if not isinstance(self.domain, str) or not self.domain.strip():
            raise ValueError("domain must be a non-empty string")
        if not self.entities or any(not isinstance(x, str) or not x.strip() for x in self.entities):
            raise ValueError("entities must be non-empty strings")
        if len(set(self.entities)) != len(self.entities):
            raise ValueError("entity ids must be unique")
        state_ids = [s.state_id for s in self.snapshots]
        if not state_ids or any(not isinstance(x, str) or not x.strip() for x in state_ids):
            raise ValueError("snapshots must have unique non-empty state ids")
        if len(set(state_ids)) != len(state_ids):
            raise ValueError("state ids must be unique")
        steps = [s.step for s in self.snapshots]
        if any(type(step) is not int or step < 0 for step in steps):
            raise ValueError("snapshot steps must be non-negative integers")
        if len(set(steps)) != len(steps):
            raise ValueError("snapshot steps must be unique")
        entity_set, state_set = set(self.entities), set(state_ids)
        for snapshot in self.snapshots:
            if len(set(snapshot.relations)) != len(snapshot.relations):
                raise ValueError("duplicate relation atoms are not allowed in a snapshot")
            for relation in snapshot.relations:
                if (not isinstance(relation.source, str) or not relation.source.strip()
                        or not isinstance(relation.target, str) or not relation.target.strip()
                        or not isinstance(relation.kind, str) or not relation.kind.strip()
                        or relation.source not in entity_set
                        or relation.target not in entity_set):
                    raise ValueError("snapshot relation has an unknown entity or empty kind")
        transition_keys = set()
        step_by_id = {s.state_id: s.step for s in self.snapshots}
        for transition in self.transitions:
            if (not isinstance(transition.source_state, str)
                    or not isinstance(transition.target_state, str)
                    or transition.source_state not in state_set
                    or transition.target_state not in state_set):
                raise ValueError("transition references an unknown state")
            if (not isinstance(transition.event_kind, str)
                    or not transition.event_kind.strip()):
                raise ValueError("transition event_kind must be non-empty")
            if step_by_id[transition.source_state] >= step_by_id[transition.target_state]:
                raise ValueError("transitions must move strictly forward in time")
            key = (transition.source_state, transition.target_state, transition.event_kind)
            if key in transition_keys:
                raise ValueError("duplicate transitions are not allowed")
            transition_keys.add(key)


@dataclass(frozen=True)
class DynamicAnalogyCandidate:
    candidate_id: str
    source: TransitionSystem
    target: TransitionSystem
    entity_mapping: Mapping[str, str]
    state_alignment: tuple[tuple[str, str], ...]
    validity_scope: str


@dataclass(frozen=True)
class DynamicAnalogyAssessment:
    candidate_id: str
    accepted: bool
    reason_codes: tuple[str, ...]
    mapped_entity_coverage: float
    aligned_state_coverage: float
    state_precision: float
    state_recall: float
    state_f1: float
    transition_precision: float
    transition_recall: float
    transition_f1: float
    preserved_state_facts: int
    expected_state_facts: int
    observed_state_facts: int
    preserved_transitions: int
    expected_transitions: int
    observed_transitions: int


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall)


def _ratio(numerator: int, denominator: int, *, empty_value: float = 0.0) -> float:
    return numerator / denominator if denominator else empty_value


def assess_dynamic_analogy(
    candidate: DynamicAnalogyCandidate,
    *,
    min_state_f1: float = 0.8,
    min_transition_f1: float = 0.81,
    min_entity_coverage: float = 1.0,
) -> DynamicAnalogyAssessment:
    """Check state-fact preservation and a commuting transition mapping.

    State alignment is explicit and must preserve temporal order. Relation
    predicates and event kinds are exact-match labels in this baseline.
    Extra target facts/transitions lower precision; missing mapped facts or
    transitions lower recall. No causal equivalence is inferred.
    """
    for name, value in (
        ("min_state_f1", min_state_f1),
        ("min_transition_f1", min_transition_f1),
        ("min_entity_coverage", min_entity_coverage),
    ):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0.0 <= value <= 1.0):
            raise ValueError(f"{name} must be a finite number in [0, 1]")

    if not isinstance(candidate.candidate_id, str) or not candidate.candidate_id.strip():
        raise ValueError("candidate_id is required")
    if not isinstance(candidate.validity_scope, str) or not candidate.validity_scope.strip():
        raise ValueError("validity_scope is required")
    candidate.source.validate()
    candidate.target.validate()

    mapping = dict(candidate.entity_mapping)
    if not mapping or any(s not in candidate.source.entities for s in mapping):
        raise ValueError("entity mapping must reference known source entities")
    if any(t not in candidate.target.entities for t in mapping.values()):
        raise ValueError("entity mapping must reference known target entities")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("entity mapping must be one-to-one")
    entity_coverage = len(mapping) / len(candidate.source.entities)
    if entity_coverage < min_entity_coverage:
        raise ValueError("entity mapping is below the required coverage")

    source_states = {s.state_id: s for s in candidate.source.snapshots}
    target_states = {s.state_id: s for s in candidate.target.snapshots}
    alignment = dict(candidate.state_alignment)
    if len(candidate.state_alignment) < 2:
        raise ValueError("at least two aligned states are required to assess dynamics")
    if len(alignment) != len(candidate.state_alignment):
        raise ValueError("source state alignment ids must be unique")
    if len(set(alignment.values())) != len(alignment):
        raise ValueError("target state alignment ids must be unique")
    if any(s not in source_states for s in alignment):
        raise ValueError("alignment references an unknown source state")
    if any(t not in target_states for t in alignment.values()):
        raise ValueError("alignment references an unknown target state")
    ordered = sorted(
        ((source_states[s].step, target_states[t].step) for s, t in alignment.items()),
        key=lambda pair: pair[0],
    )
    if any(ordered[i][1] >= ordered[i + 1][1] for i in range(len(ordered) - 1)):
        raise ValueError("state alignment must preserve strict temporal order")

    expected_facts: set[tuple[str, str, str, str]] = set()
    observed_facts: set[tuple[str, str, str, str]] = set()
    for source_id, target_id in alignment.items():
        for fact in source_states[source_id].relations:
            if fact.source in mapping and fact.target in mapping:
                expected_facts.add((target_id, mapping[fact.source], mapping[fact.target], fact.kind))
        for fact in target_states[target_id].relations:
            if fact.source in mapped_targets and fact.target in mapped_targets:
                observed_facts.add((target_id, fact.source, fact.target, fact.kind))
    preserved_facts = len(expected_facts & observed_facts)
    state_precision = _ratio(preserved_facts, len(observed_facts), empty_value=1.0)
    state_recall = _ratio(preserved_facts, len(expected_facts), empty_value=1.0)
    state_f1 = _f1(state_precision, state_recall)

    expected_transitions: set[tuple[str, str, str]] = set()
    for edge in candidate.source.transitions:
        if edge.source_state in alignment and edge.target_state in alignment:
            expected_transitions.add((
                alignment[edge.source_state], alignment[edge.target_state], edge.event_kind
            ))
    aligned_targets = set(alignment.values())
    mapped_targets = set(mapping.values())
    observed_transitions = {
        (edge.source_state, edge.target_state, edge.event_kind)
        for edge in candidate.target.transitions
        if edge.source_state in aligned_targets and edge.target_state in aligned_targets
    }
    preserved_transitions = len(expected_transitions & observed_transitions)
    transition_precision = _ratio(
        preserved_transitions, len(observed_transitions), empty_value=1.0
    )
    transition_recall = _ratio(
        preserved_transitions, len(expected_transitions), empty_value=0.0
    )
    transition_f1 = _f1(transition_precision, transition_recall)

    aligned_state_coverage = len(alignment) / len(candidate.source.snapshots)
    reasons = []
    if not expected_facts:
        reasons.append("INSUFFICIENT_MAPPED_STATE_FACTS")
    if not expected_transitions:
        reasons.append("INSUFFICIENT_SOURCE_TRANSITIONS")
    if state_f1 < min_state_f1:
        reasons.append("STATE_STRUCTURE_NOT_PRESERVED")
    if transition_f1 < min_transition_f1:
        reasons.append("DYNAMIC_TRANSITION_NOT_PRESERVED")
    return DynamicAnalogyAssessment(
        candidate_id=candidate.candidate_id,
        accepted=not reasons,
        reason_codes=tuple(reasons),
        mapped_entity_coverage=entity_coverage,
        aligned_state_coverage=aligned_state_coverage,
        state_precision=state_precision,
        state_recall=state_recall,
        state_f1=state_f1,
        transition_precision=transition_precision,
        transition_recall=transition_recall,
        transition_f1=transition_f1,
        preserved_state_facts=preserved_facts,
        expected_state_facts=len(expected_facts),
        observed_state_facts=len(observed_facts),
        preserved_transitions=preserved_transitions,
        expected_transitions=len(expected_transitions),
        observed_transitions=len(observed_transitions),
    )
