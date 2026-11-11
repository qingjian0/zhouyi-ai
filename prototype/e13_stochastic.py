"""E13-C.3 exact finite stochastic mechanisms and observation channels."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import log2
from typing import Iterable

State = tuple[tuple[str, str], ...]
Distribution = tuple[tuple[str, Fraction], ...]


class StochasticContractError(ValueError):
    pass


def _prob(value: Fraction | int | str) -> Fraction:
    if isinstance(value, (bool, float)):
        raise StochasticContractError("PROBABILITY_MUST_BE_EXACT_RATIONAL")
    try:
        result = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise StochasticContractError("INVALID_PROBABILITY") from exc
    if result < 0 or result > 1:
        raise StochasticContractError("PROBABILITY_OUT_OF_RANGE")
    return result


def _state(value: State) -> State:
    if len(dict(value)) != len(value):
        raise StochasticContractError("DUPLICATE_STATE_VARIABLE")
    return tuple(sorted(value))


def _distribution(items: Iterable[tuple[str, Fraction | int | str]]) -> Distribution:
    merged: dict[str, Fraction] = {}
    for outcome, probability in items:
        if not outcome:
            raise StochasticContractError("EMPTY_OUTCOME")
        merged[outcome] = merged.get(outcome, Fraction(0)) + _prob(probability)
    if not merged or sum(merged.values(), Fraction(0)) != 1:
        raise StochasticContractError("PROBABILITIES_MUST_SUM_TO_ONE")
    return tuple(sorted(merged.items()))


@dataclass(frozen=True)
class ProbabilisticTransitionRule:
    action: str
    state: State
    outcomes: tuple[tuple[State, Fraction], ...]


@dataclass(frozen=True)
class ProbabilisticTransitionSystem:
    system_id: str
    state_variables: tuple[str, ...]
    actions: tuple[str, ...]
    rules: tuple[ProbabilisticTransitionRule, ...]

    def __post_init__(self) -> None:
        if not self.system_id or not self.state_variables:
            raise StochasticContractError("SYSTEM_ID_AND_STATE_VARIABLES_REQUIRED")
        if len(set(self.state_variables)) != len(self.state_variables):
            raise StochasticContractError("DUPLICATE_STATE_VARIABLE")
        if len(set(self.actions)) != len(self.actions):
            raise StochasticContractError("DUPLICATE_ACTION")
        known, seen = set(self.state_variables), set()
        for rule in self.rules:
            if rule.action not in self.actions:
                raise StochasticContractError("UNKNOWN_ACTION")
            current = _state(rule.state)
            if set(dict(current)) != known:
                raise StochasticContractError("STATE_MUST_ASSIGN_EVERY_VARIABLE")
            key = (rule.action, current)
            if key in seen:
                raise StochasticContractError("DUPLICATE_TRANSITION_ROW")
            seen.add(key)
            if not rule.outcomes:
                raise StochasticContractError("EMPTY_TRANSITION_OUTCOMES")
            total = Fraction(0)
            for next_state, probability in rule.outcomes:
                if set(dict(_state(next_state))) != known:
                    raise StochasticContractError("NEXT_STATE_MUST_ASSIGN_EVERY_VARIABLE")
                total += _prob(probability)
            if total != 1:
                raise StochasticContractError("TRANSITION_PROBABILITIES_MUST_SUM_TO_ONE")

    def transition(self, state: State, action: str):
        current = _state(state)
        matches = [r for r in self.rules
                   if r.action == action and _state(r.state) == current]
        if len(matches) != 1:
            return None
        merged: dict[State, Fraction] = {}
        for next_state, probability in matches[0].outcomes:
            key = _state(next_state)
            merged[key] = merged.get(key, Fraction(0)) + _prob(probability)
        return tuple(sorted(merged.items()))


@dataclass(frozen=True)
class ObservationRule:
    latent_state: State
    observations: tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True)
class ObservationKernel:
    channel_id: str
    rules: tuple[ObservationRule, ...]

    def __post_init__(self) -> None:
        if not self.channel_id:
            raise StochasticContractError("CHANNEL_ID_REQUIRED")
        seen = set()
        for rule in self.rules:
            latent = _state(rule.latent_state)
            if latent in seen:
                raise StochasticContractError("DUPLICATE_OBSERVATION_ROW")
            seen.add(latent)
            _distribution(rule.observations)

    def observe(self, latent_state: State):
        latent = _state(latent_state)
        matches = [r for r in self.rules if _state(r.latent_state) == latent]
        return _distribution(matches[0].observations) if len(matches) == 1 else None


@dataclass(frozen=True)
class DistributionStep:
    step: int
    latent: tuple[tuple[State, Fraction], ...]
    observed: Distribution | None
    status: str


def _normalize_states(items):
    merged: dict[State, Fraction] = {}
    for state, probability in items:
        p, key = _prob(probability), _state(state)
        merged[key] = merged.get(key, Fraction(0)) + p
    result = tuple(sorted((s, p) for s, p in merged.items() if p > 0))
    if not result or sum((p for _, p in result), Fraction(0)) != 1:
        raise StochasticContractError("LATENT_DISTRIBUTION_MUST_SUM_TO_ONE")
    return result


def propagate_latent_distribution(system, initial: State, actions: tuple[str, ...]):
    start = _state(initial)
    if set(dict(start)) != set(system.state_variables):
        raise StochasticContractError("INVALID_INITIAL_STATE")
    current = ((start, Fraction(1)),)
    history = [current]
    for action in actions:
        next_items = []
        for state, mass in current:
            outcomes = system.transition(state, action)
            if outcomes is None:
                raise StochasticContractError("MISSING_TRANSITION_ROW")
            next_items.extend((next_state, mass * probability)
                              for next_state, probability in outcomes)
        current = _normalize_states(next_items)
        history.append(current)
    return tuple(history)


def observation_distribution(latent, channel: ObservationKernel):
    observed: dict[str, Fraction] = {}
    for state, mass in latent:
        outcomes = channel.observe(state)
        if outcomes is None:
            return None
        for symbol, probability in outcomes:
            observed[symbol] = observed.get(symbol, Fraction(0)) + mass * probability
    return _distribution(observed.items())


def run_stochastic_trajectory(system, channel, initial, actions):
    return tuple(
        DistributionStep(i, latent, observation_distribution(latent, channel),
                         "COMPLETE" if observation_distribution(latent, channel) is not None
                         else "UNKNOWN_OBSERVATION_CHANNEL")
        for i, latent in enumerate(
            propagate_latent_distribution(system, initial, actions)
        )
    )


def jensen_shannon_divergence(left: Distribution, right: Distribution) -> float:
    """Candidate predictive disagreement in bits; not Bayesian expected information gain."""
    p, q = dict((k, float(v)) for k, v in left), dict((k, float(v)) for k, v in right)
    keys = set(p) | set(q)
    midpoint = {k: (p.get(k, 0.0) + q.get(k, 0.0)) / 2 for k in keys}
    def kl(source):
        return sum(mass * log2(mass / midpoint[key])
                   for key, mass in source.items() if mass > 0)
    return (kl(p) + kl(q)) / 2


@dataclass(frozen=True)
class RiskAwareQuery:
    query_id: str
    predictions: tuple[tuple[str, Distribution], ...]
    authorized: bool
    risk: Fraction
    cost: Fraction


@dataclass(frozen=True)
class RiskQueryScore:
    query_id: str
    mean_pairwise_js_bits: float
    risk: Fraction
    cost: Fraction
    utility: float


@dataclass(frozen=True)
class RiskQuerySelection:
    status: str
    selected: RiskQueryScore | None
    scores: tuple[RiskQueryScore, ...]
    rejected: tuple[tuple[str, str], ...]


def select_risk_aware_query(queries: Iterable[RiskAwareQuery],
                            candidate_ids: Iterable[str], *,
                            max_risk: Fraction,
                            cost_weight: Fraction = Fraction(0),
                            risk_weight: Fraction = Fraction(0)) -> RiskQuerySelection:
    """Hard authorization/risk gates run before candidate disagreement ranking."""
    limit, c_weight, r_weight = _prob(max_risk), _prob(cost_weight), _prob(risk_weight)
    candidates = tuple(sorted(set(candidate_ids)))
    if len(candidates) < 2:
        return RiskQuerySelection("INSUFFICIENT_CANDIDATES", None, (), ())
    accepted, rejected, seen = [], [], set()
    for query in queries:
        if not query.query_id or query.query_id in seen:
            raise StochasticContractError("QUERY_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
        seen.add(query.query_id)
        risk, cost = _prob(query.risk), _prob(query.cost)
        if not query.authorized:
            rejected.append((query.query_id, "UNAUTHORIZED"))
            continue
        if risk > limit:
            rejected.append((query.query_id, "HARD_RISK_LIMIT_EXCEEDED"))
            continue
        predictions = dict(query.predictions)
        if len(predictions) != len(query.predictions) or set(predictions) != set(candidates):
            rejected.append((query.query_id, "INCOMPLETE_CANDIDATE_PREDICTIONS"))
            continue
        for distribution in predictions.values():
            _distribution(distribution)
        pair_scores = [jensen_shannon_divergence(predictions[a], predictions[b])
                       for a, b in combinations(candidates, 2)]
        disagreement = sum(pair_scores) / len(pair_scores)
        utility = disagreement - float(c_weight * cost) - float(r_weight * risk)
        accepted.append(RiskQueryScore(query.query_id, disagreement, risk, cost, utility))
    accepted.sort(key=lambda x: (-x.utility, -x.mean_pairwise_js_bits, x.query_id))
    if not accepted:
        return RiskQuerySelection("NO_SAFE_QUERY", None, (), tuple(rejected))
    return RiskQuerySelection("SELECTED", accepted[0], tuple(accepted), tuple(rejected))



@dataclass(frozen=True)
class StochasticKernelMap:
    """Explicit source-to-target vocabulary map; no inferred renaming is allowed."""
    source_to_target_variables: tuple[tuple[str, str], ...]
    source_to_target_values: tuple[tuple[str, str, str], ...]
    source_to_target_actions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class KernelValidationCase:
    case_id: str
    source_state: State
    source_action: str
    target_state: State
    target_action: str


@dataclass(frozen=True)
class KernelCaseResult:
    case_id: str
    status: str
    total_variation_distance: Fraction | None
    source_prediction: tuple[tuple[State, Fraction], ...] | None
    target_prediction: tuple[tuple[State, Fraction], ...] | None


@dataclass(frozen=True)
class KernelValidationReport:
    status: str
    cases: tuple[KernelCaseResult, ...]


def _validate_kernel_map(source: ProbabilisticTransitionSystem,
                         target: ProbabilisticTransitionSystem,
                         mapping: StochasticKernelMap) -> None:
    variable_map = dict(mapping.source_to_target_variables)
    action_map = dict(mapping.source_to_target_actions)
    if (len(variable_map) != len(mapping.source_to_target_variables)
            or set(variable_map) != set(source.state_variables)
            or set(variable_map.values()) != set(target.state_variables)
            or len(set(variable_map.values())) != len(variable_map)):
        raise StochasticContractError("VARIABLE_MAP_MUST_BE_COMPLETE_BIJECTION")
    if (len(action_map) != len(mapping.source_to_target_actions)
            or set(action_map) != set(source.actions)
            or not set(action_map.values()).issubset(set(target.actions))
            or len(set(action_map.values())) != len(action_map)):
        raise StochasticContractError("ACTION_MAP_MUST_BE_COMPLETE_INJECTION")
    value_keys = [(var, value) for var, value, _ in mapping.source_to_target_values]
    if len(set(value_keys)) != len(value_keys):
        raise StochasticContractError("DUPLICATE_VALUE_MAPPING")
    for source_var, target_var in variable_map.items():
        mapped_values = [target_value for var, _, target_value
                         in mapping.source_to_target_values if var == source_var]
        if len(set(mapped_values)) != len(mapped_values):
            raise StochasticContractError("VALUE_MAP_MUST_BE_INJECTIVE_PER_VARIABLE")
        if not target_var:
            raise StochasticContractError("EMPTY_TARGET_VARIABLE")


def map_source_state(source_state: State, mapping: StochasticKernelMap) -> State | None:
    variable_map = dict(mapping.source_to_target_variables)
    value_map = {(var, source_value): target_value
                 for var, source_value, target_value in mapping.source_to_target_values}
    mapped = []
    for variable, value in source_state:
        if variable not in variable_map or (variable, value) not in value_map:
            return None
        mapped.append((variable_map[variable], value_map[(variable, value)]))
    if len(mapped) != len(variable_map):
        return None
    return tuple(sorted(mapped))


def map_source_transition_distribution(
    source: ProbabilisticTransitionSystem,
    source_state: State,
    source_action: str,
    mapping: StochasticKernelMap,
) -> tuple[tuple[State, Fraction], ...] | None:
    action_map = dict(mapping.source_to_target_actions)
    outcomes = source.transition(source_state, source_action)
    if outcomes is None or source_action not in action_map:
        return None
    mapped = []
    for next_state, probability in outcomes:
        mapped_state = map_source_state(next_state, mapping)
        if mapped_state is None:
            return None
        mapped.append((mapped_state, probability))
    merged: dict[State, Fraction] = {}
    for state, probability in mapped:
        merged[state] = merged.get(state, Fraction(0)) + probability
    return tuple(sorted(merged.items()))


def total_variation_distance(
    left: tuple[tuple[State, Fraction], ...],
    right: tuple[tuple[State, Fraction], ...],
) -> Fraction:
    p, q = dict(left), dict(right)
    return sum((abs(p.get(state, Fraction(0)) - q.get(state, Fraction(0)))
                for state in set(p) | set(q)), Fraction(0)) / 2


def validate_stochastic_kernel_mapping(
    source: ProbabilisticTransitionSystem,
    target: ProbabilisticTransitionSystem,
    mapping: StochasticKernelMap,
    cases: Iterable[KernelValidationCase],
    *,
    max_total_variation: Fraction = Fraction(0),
) -> KernelValidationReport:
    """Validate explicit kernel mappings on supplied held-out intervention rows.

    PASS means agreement only on these cases, not global causal equivalence.
    Missing support/mappings produce UNKNOWN, never a fabricated mismatch/pass.
    """
    threshold = _prob(max_total_variation)
    _validate_kernel_map(source, target, mapping)
    case_results = []
    seen = set()
    for case in cases:
        if not case.case_id or case.case_id in seen:
            raise StochasticContractError("KERNEL_CASE_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
        seen.add(case.case_id)
        mapped_initial = map_source_state(case.source_state, mapping)
        mapped_action = dict(mapping.source_to_target_actions).get(case.source_action)
        if mapped_initial is None or mapped_action is None or mapped_initial != _state(case.target_state) or mapped_action != case.target_action:
            case_results.append(KernelCaseResult(
                case.case_id, "UNKNOWN_MAPPING_OR_CASE_ALIGNMENT", None, None, None
            ))
            continue
        source_prediction = map_source_transition_distribution(
            source, case.source_state, case.source_action, mapping
        )
        target_prediction = target.transition(case.target_state, case.target_action)
        if source_prediction is None or target_prediction is None:
            case_results.append(KernelCaseResult(
                case.case_id, "UNKNOWN_MISSING_SUPPORT_OR_VALUE_MAP", None,
                source_prediction, target_prediction
            ))
            continue
        distance = total_variation_distance(source_prediction, target_prediction)
        case_results.append(KernelCaseResult(
            case.case_id,
            "PASS" if distance <= threshold else "MISMATCH",
            distance, source_prediction, target_prediction
        ))
    if not case_results:
        status = "NO_VALIDATION_CASES"
    elif any(item.status == "MISMATCH" for item in case_results):
        status = "MISMATCH"
    elif any(item.status.startswith("UNKNOWN") for item in case_results):
        status = "INCOMPLETE"
    else:
        status = "PASS_ON_SUPPLIED_CASES"
    return KernelValidationReport(status, tuple(case_results))
