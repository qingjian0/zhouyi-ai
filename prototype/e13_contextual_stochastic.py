"""E13-C.3.3 context-conditioned finite stochastic mechanisms.

Context is exogenous and fixed within a rollout. It is never silently folded
into endogenous state or inferred from variable names.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .e13_stochastic import (
    State, Distribution, StochasticContractError, _prob, _state,
    _normalize_states, total_variation_distance,
)


Context = tuple[tuple[str, str], ...]


def _context(value: Context) -> Context:
    if len(dict(value)) != len(value):
        raise StochasticContractError("DUPLICATE_CONTEXT_VARIABLE")
    return tuple(sorted(value))


@dataclass(frozen=True)
class ContextualTransitionRule:
    context: Context
    action: str
    state: State
    outcomes: tuple[tuple[State, Fraction], ...]


@dataclass(frozen=True)
class ContextualProbabilisticTransitionSystem:
    system_id: str
    state_variables: tuple[str, ...]
    context_variables: tuple[str, ...]
    actions: tuple[str, ...]
    rules: tuple[ContextualTransitionRule, ...]

    def __post_init__(self) -> None:
        if not self.system_id or not self.state_variables or not self.context_variables:
            raise StochasticContractError("SYSTEM_STATE_AND_CONTEXT_REQUIRED")
        if set(self.state_variables) & set(self.context_variables):
            raise StochasticContractError("CONTEXT_MUST_NOT_BE_ENDOGENOUS_STATE")
        if len(set(self.state_variables)) != len(self.state_variables):
            raise StochasticContractError("DUPLICATE_STATE_VARIABLE")
        if len(set(self.context_variables)) != len(self.context_variables):
            raise StochasticContractError("DUPLICATE_CONTEXT_VARIABLE")
        if len(set(self.actions)) != len(self.actions):
            raise StochasticContractError("DUPLICATE_ACTION")
        state_names, context_names = set(self.state_variables), set(self.context_variables)
        seen = set()
        for rule in self.rules:
            if rule.action not in self.actions:
                raise StochasticContractError("UNKNOWN_ACTION")
            state, context = _state(rule.state), _context(rule.context)
            if set(dict(state)) != state_names:
                raise StochasticContractError("STATE_MUST_ASSIGN_EVERY_VARIABLE")
            if set(dict(context)) != context_names:
                raise StochasticContractError("CONTEXT_MUST_ASSIGN_EVERY_VARIABLE")
            key = (context, rule.action, state)
            if key in seen:
                raise StochasticContractError("DUPLICATE_CONTEXTUAL_TRANSITION_ROW")
            seen.add(key)
            if not rule.outcomes:
                raise StochasticContractError("EMPTY_TRANSITION_OUTCOMES")
            total = Fraction(0)
            for next_state, probability in rule.outcomes:
                if set(dict(_state(next_state))) != state_names:
                    raise StochasticContractError("NEXT_STATE_MUST_ASSIGN_EVERY_VARIABLE")
                total += _prob(probability)
            if total != 1:
                raise StochasticContractError("TRANSITION_PROBABILITIES_MUST_SUM_TO_ONE")

    def transition(self, state: State, action: str, context: Context):
        current, fixed_context = _state(state), _context(context)
        if action not in self.actions:
            return None
        matches = [r for r in self.rules
                   if r.action == action and _state(r.state) == current
                   and _context(r.context) == fixed_context]
        if len(matches) != 1:
            return None
        merged: dict[State, Fraction] = {}
        for next_state, probability in matches[0].outcomes:
            key = _state(next_state)
            merged[key] = merged.get(key, Fraction(0)) + _prob(probability)
        return tuple(sorted(merged.items()))


@dataclass(frozen=True)
class ContextualKernelMap:
    state_variables: tuple[tuple[str, str], ...]
    state_values: tuple[tuple[str, str, str], ...]
    context_variables: tuple[tuple[str, str], ...]
    context_values: tuple[tuple[str, str, str], ...]
    actions: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        for pairs in (self.state_variables, self.context_variables, self.actions):
            left, right = [p[0] for p in pairs], [p[1] for p in pairs]
            if len(left) != len(set(left)) or len(right) != len(set(right)):
                raise StochasticContractError("MAPPING_MUST_BE_INJECTIVE")
        for rows, label in ((self.state_values, "STATE"), (self.context_values, "CONTEXT")):
            source = [(v, x) for v, x, _ in rows]
            target = [(v, y) for v, _, y in rows]
            if len(source) != len(set(source)) or len(target) != len(set(target)):
                raise StochasticContractError(label + "_VALUE_MAPPING_MUST_BE_INJECTIVE")


def _validate_context_map(source, target, mapping):
    if (dict(mapping.state_variables) != dict(zip(source.state_variables,
                                                   (dict(mapping.state_variables).get(v) for v in source.state_variables)))
            or set(dict(mapping.state_variables)) != set(source.state_variables)
            or set(dict(mapping.state_variables).values()) != set(target.state_variables)):
        raise StochasticContractError("STATE_VARIABLE_MAP_MUST_BE_COMPLETE_BIJECTION")
    if set(dict(mapping.context_variables)) != set(source.context_variables) or set(
        dict(mapping.context_variables).values()
    ) != set(target.context_variables):
        raise StochasticContractError("CONTEXT_VARIABLE_MAP_MUST_BE_COMPLETE_BIJECTION")
    if set(dict(mapping.actions)) != set(source.actions) or set(
        dict(mapping.actions).values()
    ) != set(target.actions):
        raise StochasticContractError("ACTION_MAP_MUST_BE_COMPLETE_BIJECTION")
    state_values = {(v, x): y for v, x, y in mapping.state_values}
    context_values = {(v, x): y for v, x, y in mapping.context_values}
    if len(state_values) != len(mapping.state_values) or len(context_values) != len(mapping.context_values):
        raise StochasticContractError("DUPLICATE_VALUE_MAPPING")
    for variable in source.state_variables:
        target_variable = dict(mapping.state_variables)[variable]
        source_values = {value for rule in source.rules for v, value in rule.state if v == variable}
        source_values |= {value for rule in source.rules for state in (rule.state,) + tuple(s for s, _ in rule.outcomes) for v, value in state if v == variable}
        target_values = {value for rule in target.rules for v, value in rule.state if v == target_variable}
        target_values |= {value for rule in target.rules for state in (rule.state,) + tuple(s for s, _ in rule.outcomes) for v, value in state if v == target_variable}
        if any((variable, value) not in state_values for value in source_values):
            raise StochasticContractError("STATE_VALUE_MAP_MUST_COVER_DECLARED_VALUES")
        if {state_values[(variable, value)] for value in source_values} != target_values:
            raise StochasticContractError("STATE_VALUE_MAP_MUST_BE_BIJECTIVE_ON_DECLARED_VALUES")
    for variable in source.context_variables:
        target_variable = dict(mapping.context_variables)[variable]
        source_values = {value for rule in source.rules for v, value in rule.context if v == variable}
        target_values = {value for rule in target.rules for v, value in rule.context if v == target_variable}
        if any((variable, value) not in context_values for value in source_values):
            raise StochasticContractError("CONTEXT_VALUE_MAP_MUST_COVER_DECLARED_VALUES")
        if {context_values[(variable, value)] for value in source_values} != target_values:
            raise StochasticContractError("CONTEXT_VALUE_MAP_MUST_BE_BIJECTIVE_ON_DECLARED_VALUES")


def _map_state(state: State, mapping: ContextualKernelMap) -> State | None:
    variables, values = dict(mapping.state_variables), {
        (v, x): y for v, x, y in mapping.state_values
    }
    result = []
    for variable, value in state:
        if variable not in variables or (variable, value) not in values:
            return None
        result.append((variables[variable], values[(variable, value)]))
    return _state(tuple(result))


def _map_context(context: Context, mapping: ContextualKernelMap) -> Context | None:
    variables, values = dict(mapping.context_variables), {
        (v, x): y for v, x, y in mapping.context_values
    }
    result = []
    for variable, value in context:
        if variable not in variables or (variable, value) not in values:
            return None
        result.append((variables[variable], values[(variable, value)]))
    return _context(tuple(result))


def propagate_contextual_distribution(system, initial: State, actions: tuple[str, ...],
                                       context: Context):
    """Propagate latent distributions while holding exogenous context fixed."""
    start, fixed_context = _state(initial), _context(context)
    if set(dict(start)) != set(system.state_variables):
        raise StochasticContractError("INVALID_INITIAL_STATE")
    if set(dict(fixed_context)) != set(system.context_variables):
        raise StochasticContractError("INVALID_CONTEXT")
    current = ((start, Fraction(1)),)
    history = [current]
    for action in actions:
        next_items = []
        for state, mass in current:
            outcomes = system.transition(state, action, fixed_context)
            if outcomes is None:
                raise StochasticContractError("MISSING_CONTEXTUAL_TRANSITION_ROW")
            next_items.extend((next_state, mass * probability)
                              for next_state, probability in outcomes)
        current = _normalize_states(next_items)
        history.append(current)
    return tuple(history)


@dataclass(frozen=True)
class ContextualTrajectoryCase:
    case_id: str
    source_initial: State
    target_initial: State
    source_context: Context
    target_context: Context
    source_actions: tuple[str, ...]


@dataclass(frozen=True)
class ContextualStepComparison:
    step: int
    total_variation_distance: Fraction | None
    status: str


@dataclass(frozen=True)
class ContextualTrajectoryReport:
    case_id: str
    status: str
    steps: tuple[ContextualStepComparison, ...]


def validate_contextual_trajectory(source, target, mapping, case,
                                   *, max_total_variation: Fraction = Fraction(0)):
    """Compare mapped trajectories under one explicitly aligned context pair."""
    threshold = _prob(max_total_variation)
    _validate_context_map(source, target, mapping)
    if not case.case_id:
        raise StochasticContractError("CASE_ID_REQUIRED")
    mapped_initial = _map_state(case.source_initial, mapping)
    mapped_context = _map_context(case.source_context, mapping)
    if mapped_initial is None or mapped_initial != _state(case.target_initial):
        return ContextualTrajectoryReport(case.case_id, "UNKNOWN_INITIAL_ALIGNMENT", ())
    if mapped_context is None or mapped_context != _context(case.target_context):
        return ContextualTrajectoryReport(case.case_id, "UNKNOWN_CONTEXT_ALIGNMENT", ())
    action_map = dict(mapping.actions)
    if any(a not in action_map for a in case.source_actions):
        return ContextualTrajectoryReport(case.case_id, "UNKNOWN_ACTION_MAPPING", ())
    try:
        source_history = propagate_contextual_distribution(
            source, case.source_initial, case.source_actions, case.source_context
        )
    except StochasticContractError as exc:
        if str(exc) == "MISSING_CONTEXTUAL_TRANSITION_ROW":
            return ContextualTrajectoryReport(case.case_id, "UNKNOWN_SOURCE_CONTEXT_SUPPORT", ())
        raise
    try:
        target_history = propagate_contextual_distribution(
            target, case.target_initial, tuple(action_map[a] for a in case.source_actions),
            case.target_context
        )
    except StochasticContractError as exc:
        if str(exc) == "MISSING_CONTEXTUAL_TRANSITION_ROW":
            return ContextualTrajectoryReport(case.case_id, "UNKNOWN_TARGET_CONTEXT_SUPPORT", ())
        raise
    comparisons = []
    for index, (left, right) in enumerate(zip(source_history, target_history)):
        mapped = []
        for state, mass in left:
            translated = _map_state(state, mapping)
            if translated is None:
                return ContextualTrajectoryReport(case.case_id, "UNKNOWN_STATE_VALUE_MAPPING", ())
            mapped.append((translated, mass))
        merged: dict[State, Fraction] = {}
        for state, mass in mapped:
            merged[state] = merged.get(state, Fraction(0)) + mass
        distance = total_variation_distance(tuple(sorted(merged.items())), right)
        comparisons.append(ContextualStepComparison(
            index, distance, "PASS" if distance <= threshold else "MISMATCH"
        ))
    status = ("MISMATCH" if any(s.status == "MISMATCH" for s in comparisons)
              else "PASS_ON_SUPPLIED_CONTEXTUAL_TRAJECTORY")
    return ContextualTrajectoryReport(case.case_id, status, tuple(comparisons))
