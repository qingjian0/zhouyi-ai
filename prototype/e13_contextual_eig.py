"""E13-C.3.7 Bayesian expected-information-gain query selection.

Predictive sequence probabilities are exact Fractions. Entropy uses log2 and
is therefore a floating-point estimate in bits. Forecasts expose observations,
not latent states.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import log2
from typing import Iterable

from .e13_stochastic import StochasticContractError, _prob
from .e13_contextual_stochastic import State
from .e13_contextual_bayes import (
    BayesianObservationBelief, BayesianObservationCandidate, CandidateBelief,
)


@dataclass(frozen=True)
class BayesianExperimentQuery:
    query_id: str
    actions: tuple[str, ...]
    sensor_ids: tuple[str, ...]
    target: str = "candidate"  # candidate | mechanism | channel
    authorized: bool = True
    risk: Fraction = Fraction(0)
    cost: Fraction = Fraction(0)


@dataclass(frozen=True)
class CandidateObservationSequenceForecast:
    candidate_id: str
    probabilities: tuple[tuple[tuple[str, ...], Fraction], ...]


@dataclass(frozen=True)
class BayesianExperimentQueryScore:
    query_id: str
    target: str
    status: str
    expected_information_gain_bits: float | None
    utility: float | None
    forecasts: tuple[CandidateObservationSequenceForecast, ...]


@dataclass(frozen=True)
class BayesianExperimentSelection:
    status: str
    selected: BayesianExperimentQueryScore | None
    ranked: tuple[BayesianExperimentQueryScore, ...]
    rejected: tuple[tuple[str, str], ...]


def _nonnegative_fraction(value, error_code: str) -> Fraction:
    try:
        result = value if isinstance(value, Fraction) else Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise StochasticContractError(error_code) from exc
    if result < 0:
        raise StochasticContractError(error_code)
    return result


def _channel(candidate: BayesianObservationCandidate, sensor_id: str):
    matches = [kernel for key, kernel in candidate.observation_channels
               if key == sensor_id]
    return matches[0] if len(matches) == 1 else None


def _forecast_sequences(
    candidate: BayesianObservationCandidate,
    candidate_belief: CandidateBelief,
    context,
    actions: tuple[str, ...],
    sensor_ids: tuple[str, ...],
):
    """Exact forward enumeration of the joint future observation sequence."""
    # (latent state, observation prefix) -> joint probability mass
    frontier: dict[tuple[State, tuple[str, ...]], Fraction] = {
        (state, ()): mass
        for state, mass in candidate_belief.latent_state_distribution
    }
    for action, sensor_id in zip(actions, sensor_ids):
        channel = _channel(candidate, sensor_id)
        if channel is None:
            return None
        next_frontier: dict[tuple[State, tuple[str, ...]], Fraction] = {}
        for (state, prefix), state_mass in frontier.items():
            outcomes = candidate.system.transition(state, action, context)
            if outcomes is None:
                return None
            for next_state, transition_probability in outcomes:
                observation_distribution = channel.observe(next_state)
                if observation_distribution is None:
                    return None
                for observation, observation_probability in observation_distribution:
                    key = (next_state, prefix + (observation,))
                    next_frontier[key] = (
                        next_frontier.get(key, Fraction(0))
                        + state_mass * transition_probability * observation_probability
                    )
        frontier = next_frontier
        if not frontier:
            return None

    sequence_mass: dict[tuple[str, ...], Fraction] = {}
    for (_, sequence), mass in frontier.items():
        sequence_mass[sequence] = sequence_mass.get(sequence, Fraction(0)) + mass
    total = sum(sequence_mass.values(), Fraction(0))
    if total != 1:
        return None
    return tuple(sorted(sequence_mass.items()))


def _entropy(distribution: dict[object, Fraction]) -> float:
    return -sum(
        float(probability) * log2(float(probability))
        for probability in distribution.values() if probability > 0
    )


def _mutual_information(
    candidate_forecasts: tuple[CandidateObservationSequenceForecast, ...],
    weights: dict[str, Fraction],
    group_by_candidate: dict[str, str],
) -> float:
    """I(group; observation sequence), with exact mixture probabilities."""
    grouped: dict[str, dict[tuple[str, ...], Fraction]] = {}
    group_weights: dict[str, Fraction] = {}
    marginal: dict[tuple[str, ...], Fraction] = {}
    for forecast in candidate_forecasts:
        candidate_id = forecast.candidate_id
        weight = weights[candidate_id]
        group = group_by_candidate[candidate_id]
        group_weights[group] = group_weights.get(group, Fraction(0)) + weight
        for sequence, conditional_probability in forecast.probabilities:
            weighted = weight * conditional_probability
            marginal[sequence] = marginal.get(sequence, Fraction(0)) + weighted
            table = grouped.setdefault(group, {})
            table[sequence] = table.get(sequence, Fraction(0)) + weighted

    marginal_entropy = _entropy(marginal)
    conditional_entropy = 0.0
    for group, table in grouped.items():
        group_weight = group_weights[group]
        conditional = {
            sequence: joint_mass / group_weight
            for sequence, joint_mass in table.items()
        }
        conditional_entropy += float(group_weight) * _entropy(conditional)
    return max(0.0, marginal_entropy - conditional_entropy)


def _validate_belief(belief: BayesianObservationBelief):
    if belief.status != "ACTIVE":
        raise StochasticContractError("BELIEF_NOT_ACTIVE")
    candidate_ids = [candidate.candidate_id for candidate in belief.candidates]
    belief_ids = [item.candidate_id for item in belief.candidate_beliefs]
    if (len(set(candidate_ids)) != len(candidate_ids)
            or set(candidate_ids) != set(belief_ids)
            or len(belief_ids) != len(set(belief_ids))):
        raise StochasticContractError("BELIEF_CANDIDATE_SET_MISMATCH")
    weights = {item.candidate_id: _prob(item.posterior_weight)
               for item in belief.candidate_beliefs}
    if sum(weights.values(), Fraction(0)) != 1:
        raise StochasticContractError("BELIEF_POSTERIOR_MUST_SUM_TO_ONE")
    return weights, {item.candidate_id: item for item in belief.candidate_beliefs}


def select_bayesian_experiment(
    belief: BayesianObservationBelief,
    queries: Iterable[BayesianExperimentQuery],
    *,
    max_risk: Fraction = Fraction(1),
    max_cost: Fraction | None = None,
    risk_weight: Fraction = Fraction(0),
    cost_weight: Fraction = Fraction(0),
) -> BayesianExperimentSelection:
    """Select a finite action/sensor sequence by genuine Bayesian EIG.

    EIG is mutual information between the requested hypothesis label and the
    future observation sequence, under the current posterior and supplied
    generative models. Candidate forecasts remain in observation space.
    """
    weights, beliefs = _validate_belief(belief)
    query_list = tuple(queries)
    query_ids = [query.query_id for query in query_list]
    if any(not item for item in query_ids) or len(set(query_ids)) != len(query_ids):
        raise StochasticContractError("QUERY_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
    risk_limit = _prob(max_risk)
    cost_limit = None if max_cost is None else _nonnegative_fraction(
        max_cost, "MAX_COST_MUST_BE_NONNEGATIVE"
    )
    rw = _nonnegative_fraction(risk_weight, "UTILITY_WEIGHTS_MUST_BE_NONNEGATIVE")
    cw = _nonnegative_fraction(cost_weight, "UTILITY_WEIGHTS_MUST_BE_NONNEGATIVE")

    ranked: list[BayesianExperimentQueryScore] = []
    rejected: list[tuple[str, str]] = []
    candidates = {candidate.candidate_id: candidate for candidate in belief.candidates}

    for query in query_list:
        risk = _prob(query.risk)
        cost = _nonnegative_fraction(query.cost, "QUERY_COST_MUST_BE_NONNEGATIVE")
        if not query.actions or len(query.actions) != len(query.sensor_ids):
            rejected.append((query.query_id, "ACTION_SENSOR_HORIZON_MISMATCH"))
            continue
        if query.target not in ("candidate", "mechanism", "channel"):
            rejected.append((query.query_id, "UNKNOWN_INFORMATION_TARGET"))
            continue
        if not query.authorized:
            rejected.append((query.query_id, "UNAUTHORIZED"))
            continue
        if risk > risk_limit:
            rejected.append((query.query_id, "RISK_LIMIT_EXCEEDED"))
            continue
        if cost_limit is not None and cost > cost_limit:
            rejected.append((query.query_id, "COST_LIMIT_EXCEEDED"))
            continue

        forecasts = []
        complete = True
        for candidate_id, candidate in candidates.items():
            if weights[candidate_id] == 0:
                continue
            forecast = _forecast_sequences(
                candidate, beliefs[candidate_id], belief.context,
                query.actions, query.sensor_ids,
            )
            if forecast is None:
                complete = False
                break
            forecasts.append(CandidateObservationSequenceForecast(
                candidate_id, forecast
            ))
        if not complete:
            rejected.append((query.query_id, "UNKNOWN_INCOMPLETE_PREDICTIVE_SUPPORT"))
            continue
        if not forecasts:
            rejected.append((query.query_id, "NO_POSITIVE_POSTERIOR_CANDIDATES"))
            continue

        if query.target == "candidate":
            groups = {candidate_id: candidate_id for candidate_id in weights
                      if weights[candidate_id] > 0}
        elif query.target == "mechanism":
            groups = {}
            for candidate_id, candidate in candidates.items():
                if weights[candidate_id] == 0:
                    continue
                if not candidate.mechanism_hypothesis_id:
                    complete = False
                    break
                groups[candidate_id] = candidate.mechanism_hypothesis_id
        else:
            groups = {}
            for candidate_id, candidate in candidates.items():
                if weights[candidate_id] == 0:
                    continue
                if not candidate.channel_hypothesis_id:
                    complete = False
                    break
                groups[candidate_id] = candidate.channel_hypothesis_id
        if not complete:
            rejected.append((query.query_id, f"MISSING_{query.target.upper()}_HYPOTHESIS_ID"))
            continue

        eig = _mutual_information(tuple(forecasts), weights, groups)
        utility = eig - float(rw * risk) - float(cw * cost)
        ranked.append(BayesianExperimentQueryScore(
            query.query_id, query.target, "SCORED", eig, utility, tuple(forecasts)
        ))

    ranked.sort(key=lambda item: (
        -item.utility, -item.expected_information_gain_bits, item.query_id
    ))
    if not ranked:
        return BayesianExperimentSelection(
            "NO_SAFE_COMPLETE_QUERY", None, (), tuple(rejected)
        )
    if all(item.expected_information_gain_bits <= 1e-12 for item in ranked):
        return BayesianExperimentSelection(
            "NO_EXPECTED_INFORMATION_GAIN", ranked[0], tuple(ranked), tuple(rejected)
        )
    return BayesianExperimentSelection(
        "SELECTED", ranked[0], tuple(ranked), tuple(rejected)
    )
