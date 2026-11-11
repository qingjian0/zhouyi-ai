"""E13-C.2 finite multi-step transition systems for dynamic analogy.

A deterministic finite-state research DSL. It supports explicit state/action
mappings and trajectory comparison; it is not a general causal learner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class TransitionContractError(ValueError):
    pass


State = tuple[tuple[str, str], ...]


def _canonical_state(state: State) -> State:
    if len(dict(state)) != len(state):
        raise TransitionContractError("DUPLICATE_STATE_VARIABLE")
    return tuple(sorted(state))


@dataclass(frozen=True)
class TransitionRule:
    action: str
    state: State
    next_state: State


@dataclass(frozen=True)
class TransitionSystem:
    system_id: str
    state_variables: tuple[str, ...]
    actions: tuple[str, ...]
    rules: tuple[TransitionRule, ...]

    def __post_init__(self) -> None:
        if not self.system_id or not self.state_variables:
            raise TransitionContractError("SYSTEM_ID_AND_STATE_VARIABLES_REQUIRED")
        if len(set(self.state_variables)) != len(self.state_variables):
            raise TransitionContractError("DUPLICATE_STATE_VARIABLE")
        if len(set(self.actions)) != len(self.actions):
            raise TransitionContractError("DUPLICATE_ACTION")
        known = set(self.state_variables)
        seen = set()
        for rule in self.rules:
            if rule.action not in self.actions:
                raise TransitionContractError("UNKNOWN_ACTION")
            state = _canonical_state(rule.state)
            next_state = _canonical_state(rule.next_state)
            if set(dict(state)) != known or set(dict(next_state)) != known:
                raise TransitionContractError("STATE_MUST_ASSIGN_EVERY_VARIABLE")
            key = (rule.action, state)
            if key in seen:
                raise TransitionContractError("NON_DETERMINISTIC_TRANSITION")
            seen.add(key)

    def step(self, state: State, action: str) -> State | None:
        canonical = _canonical_state(state)
        matches = [r for r in self.rules
                   if r.action == action and _canonical_state(r.state) == canonical]
        if len(matches) != 1:
            return None
        return _canonical_state(matches[0].next_state)


@dataclass(frozen=True)
class TransitionMap:
    candidate_id: str
    state_variables: tuple[tuple[str, str], ...]
    state_values: tuple[tuple[str, str, str], ...]
    actions: tuple[tuple[str, str], ...]
    provenance: str
    rationale: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.provenance.strip() or not self.rationale.strip():
            raise TransitionContractError("CANDIDATE_PROVENANCE_RATIONALE_REQUIRED")
        for pairs in (self.state_variables, self.actions):
            source = [p[0] for p in pairs]
            target = [p[1] for p in pairs]
            if len(source) != len(set(source)) or len(target) != len(set(target)):
                raise TransitionContractError("MAPPING_MUST_BE_INJECTIVE")
        keys = [(v, value) for v, value, _ in self.state_values]
        targets = [(v, value) for v, _, value in self.state_values]
        if len(keys) != len(set(keys)) or len(targets) != len(set(targets)):
            raise TransitionContractError("STATE_VALUE_MAPPING_MUST_BE_INJECTIVE")


@dataclass(frozen=True)
class Trajectory:
    states: tuple[State, ...]
    status: str
    stopped_at_step: int | None = None


def _map_state(state: State, mapping: TransitionMap) -> State | None:
    variable_map = dict(mapping.state_variables)
    value_map = {(var, value): target for var, value, target in mapping.state_values}
    translated = []
    for variable, value in state:
        target_variable = variable_map.get(variable)
        target_value = value_map.get((variable, value))
        if target_variable is None or target_value is None:
            return None
        translated.append((target_variable, target_value))
    return _canonical_state(tuple(translated))


def _translate_actions(actions: Iterable[str], mapping: TransitionMap) -> tuple[str, ...] | None:
    action_map = dict(mapping.actions)
    translated = []
    for action in actions:
        target = action_map.get(action)
        if target is None:
            return None
        translated.append(target)
    return tuple(translated)


def rollout(system: TransitionSystem, initial_state: State,
            actions: tuple[str, ...]) -> Trajectory:
    state = _canonical_state(initial_state)
    if set(dict(state)) != set(system.state_variables):
        return Trajectory((state,), "INVALID_INITIAL_STATE", 0)
    states = [state]
    for index, action in enumerate(actions):
        next_state = system.step(state, action)
        if next_state is None:
            return Trajectory(tuple(states), "NO_TRANSITION", index)
        states.append(next_state)
        state = next_state
    return Trajectory(tuple(states), "COMPLETE")


@dataclass(frozen=True)
class TrajectoryValidation:
    status: str
    predicted: Trajectory
    observed: Trajectory
    mismatch_step: int | None = None
    reason: str | None = None


def forecast_target_trajectory(source: TransitionSystem, mapping: TransitionMap,
                               source_initial_state: State,
                               source_actions: tuple[str, ...]) -> Trajectory:
    source_trajectory = rollout(source, source_initial_state, source_actions)
    if source_trajectory.status != "COMPLETE":
        return Trajectory((), "SOURCE_" + source_trajectory.status,
                          source_trajectory.stopped_at_step)
    translated_states = []
    for state in source_trajectory.states:
        translated = _map_state(state, mapping)
        if translated is None:
            return Trajectory(tuple(translated_states), "UNMAPPED_STATE")
        translated_states.append(translated)
    return Trajectory(tuple(translated_states), "COMPLETE")


def observe_target_trajectory(target: TransitionSystem, mapping: TransitionMap,
                              target_initial_state: State,
                              source_actions: tuple[str, ...]) -> Trajectory:
    translated_actions = _translate_actions(source_actions, mapping)
    canonical_initial = _canonical_state(target_initial_state)
    if (translated_actions is None
            or set(dict(canonical_initial)) != set(target.state_variables)):
        return Trajectory((), "UNMAPPED_INITIAL_OR_ACTION")
    # The target initial state is already expressed in the target namespace.
    # Only actions are translated; applying the inverse map here would send
    # source-named variables into the target simulator.
    return rollout(target, canonical_initial, translated_actions)


def validate_trajectory(predicted: Trajectory,
                        observed: Trajectory) -> TrajectoryValidation:
    if predicted.status != "COMPLETE" or observed.status != "COMPLETE":
        return TrajectoryValidation("UNKNOWN", predicted, observed,
                                    reason="INCOMPLETE_OR_UNMAPPED_TRAJECTORY")
    if len(predicted.states) != len(observed.states):
        return TrajectoryValidation("REJECTED", predicted, observed,
                                    reason="TRAJECTORY_LENGTH_MISMATCH")
    for index, (expected, actual) in enumerate(zip(predicted.states, observed.states)):
        if expected != actual:
            return TrajectoryValidation("REJECTED", predicted, observed,
                                        mismatch_step=index,
                                        reason="STATE_TRAJECTORY_MISMATCH")
    return TrajectoryValidation("VALID_FOR_TRAJECTORY", predicted, observed)
