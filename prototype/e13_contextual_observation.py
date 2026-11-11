"""E13-C.3.5 active selection in observation space.

The selector sees only projected observation distributions. Latent mechanism
forecasts remain internal to the projection function and are not returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Iterable

from .e13_stochastic import (
    Distribution, ObservationKernel, StochasticContractError, _prob,
    observation_distribution, total_variation_distance,
)
from .e13_contextual_stochastic import (
    Context, State, ContextualProbabilisticTransitionSystem,
    propagate_contextual_distribution,
)


@dataclass(frozen=True)
class ContextualObservationCandidate:
    candidate_id: str
    system: ContextualProbabilisticTransitionSystem
    # Each candidate supplies its own hypothesized channel for a sensor/query.
    # Reusing the same kernel across candidates isolates mechanism differences.
    observation_channels: tuple[tuple[str, ObservationKernel], ...]


@dataclass(frozen=True)
class ContextualObservationQuery:
    query_id: str
    sensor_id: str
    actions: tuple[str, ...]
    authorized: bool
    risk: Fraction
    cost: Fraction


@dataclass(frozen=True)
class ObservationCandidateForecast:
    candidate_id: str
    # Observation-space distributions only; latent states are never returned.
    observed_trajectory: tuple[Distribution, ...]


@dataclass(frozen=True)
class ContextualObservationQueryScore:
    query_id: str
    sensor_id: str
    status: str
    pairwise_observation_tv_disagreement: Fraction | None
    utility: Fraction | None
    forecasts: tuple[ObservationCandidateForecast, ...]


@dataclass(frozen=True)
class ContextualObservationSelection:
    status: str
    selected: ContextualObservationQueryScore | None
    ranked: tuple[ContextualObservationQueryScore, ...]
    rejected: tuple[tuple[str, str], ...]


def project_contextual_observation_trajectory(
    system: ContextualProbabilisticTransitionSystem,
    channel: ObservationKernel,
    initial_state: State,
    actions: tuple[str, ...],
    context: Context,
) -> tuple[Distribution, ...] | None:
    """Propagate latent state internally, then expose only sensor predictions."""
    latent_history = propagate_contextual_distribution(
        system, initial_state, actions, context
    )
    projected = []
    for latent_distribution in latent_history:
        observed = observation_distribution(latent_distribution, channel)
        if observed is None:
            return None
        projected.append(observed)
    return tuple(projected)


def _observation_trajectory_disagreement(
    left: tuple[Distribution, ...],
    right: tuple[Distribution, ...],
) -> Fraction:
    if len(left) != len(right):
        raise StochasticContractError("OBSERVATION_TRAJECTORY_LENGTH_MISMATCH")
    if not left:
        return Fraction(0)
    return sum(
        (total_variation_distance(a, b) for a, b in zip(left, right)),
        Fraction(0),
    ) / len(left)


def select_contextual_observation_query(
    candidates: Iterable[ContextualObservationCandidate],
    queries: Iterable[ContextualObservationQuery],
    initial_state: State,
    context: Context,
    *,
    max_risk: Fraction = Fraction(1),
    max_cost: Fraction | None = None,
    risk_weight: Fraction = Fraction(0),
    cost_weight: Fraction = Fraction(0),
) -> ContextualObservationSelection:
    """Rank authorized sensor/action queries by observable candidate disagreement.

    The score is exact pairwise TV in observation space, averaged over time and
    candidate pairs. It is not Bayesian EIG and performs no posterior update.
    Missing transition or observation support makes a query UNKNOWN.
    """
    candidate_list, query_list = tuple(candidates), tuple(queries)
    risk_limit = _prob(max_risk)
    cost_limit = None if max_cost is None else _prob(max_cost)
    rw, cw = _prob(risk_weight), _prob(cost_weight)
    if not candidate_list:
        raise StochasticContractError("AT_LEAST_ONE_CANDIDATE_REQUIRED")
    candidate_ids = [c.candidate_id for c in candidate_list]
    query_ids = [q.query_id for q in query_list]
    if any(not value for value in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids):
        raise StochasticContractError("CANDIDATE_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
    if any(not value for value in query_ids) or len(set(query_ids)) != len(query_ids):
        raise StochasticContractError("QUERY_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
    if rw < 0 or cw < 0:
        raise StochasticContractError("UTILITY_WEIGHTS_MUST_BE_NONNEGATIVE")

    ranked: list[ContextualObservationQueryScore] = []
    rejected: list[tuple[str, str]] = []
    for query in query_list:
        risk, cost = _prob(query.risk), _prob(query.cost)
        if not query.sensor_id:
            rejected.append((query.query_id, "MISSING_SENSOR_ID"))
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

        forecasts: list[ObservationCandidateForecast] = []
        complete = True
        for candidate in candidate_list:
            channels = [kernel for sensor_id, kernel in candidate.observation_channels
                        if sensor_id == query.sensor_id]
            if len(channels) != 1:
                complete = False
                break
            try:
                trajectory = project_contextual_observation_trajectory(
                    candidate.system, channels[0], initial_state,
                    query.actions, context,
                )
            except StochasticContractError as exc:
                if str(exc) in (
                    "MISSING_CONTEXTUAL_TRANSITION_ROW", "INVALID_INITIAL_STATE",
                    "INVALID_CONTEXT",
                ):
                    complete = False
                    break
                raise
            if trajectory is None:
                complete = False
                break
            forecasts.append(ObservationCandidateForecast(
                candidate.candidate_id, trajectory
            ))
        if not complete:
            rejected.append((query.query_id, "UNKNOWN_INCOMPLETE_OBSERVATION_FORECAST"))
            continue

        if len(forecasts) < 2:
            disagreement = Fraction(0)
        else:
            pairs = tuple(combinations(forecasts, 2))
            disagreement = sum((
                _observation_trajectory_disagreement(
                    left.observed_trajectory, right.observed_trajectory
                ) for left, right in pairs
            ), Fraction(0)) / len(pairs)
        utility = disagreement - rw * risk - cw * cost
        ranked.append(ContextualObservationQueryScore(
            query.query_id, query.sensor_id, "SCORED",
            disagreement, utility, tuple(forecasts),
        ))

    ranked.sort(key=lambda item: (
        -item.utility, -item.pairwise_observation_tv_disagreement, item.query_id
    ))
    if not ranked:
        return ContextualObservationSelection(
            "NO_SAFE_COMPLETE_OBSERVATION_QUERY", None, (), tuple(rejected)
        )
    if all(item.pairwise_observation_tv_disagreement == 0 for item in ranked):
        return ContextualObservationSelection(
            "OBSERVATIONALLY_NON_DISCRIMINATING", ranked[0],
            tuple(ranked), tuple(rejected)
        )
    return ContextualObservationSelection(
        "SELECTED", ranked[0], tuple(ranked), tuple(rejected)
    )
