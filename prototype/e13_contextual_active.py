"""E13-C.3.4 active action-sequence selection for contextual mechanisms.

This is finite exact disagreement search, not Bayesian EIG. Every candidate
must forecast every step of a query; incomplete forecasts are UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Iterable

from .e13_stochastic import StochasticContractError, _prob
from .e13_contextual_stochastic import (
    Context, State, ContextualProbabilisticTransitionSystem,
    propagate_contextual_distribution,
)
from .e13_stochastic import total_variation_distance


@dataclass(frozen=True)
class ContextualMechanismCandidate:
    candidate_id: str
    system: ContextualProbabilisticTransitionSystem


@dataclass(frozen=True)
class ContextualSequenceQuery:
    query_id: str
    actions: tuple[str, ...]
    authorized: bool
    risk: Fraction
    cost: Fraction


@dataclass(frozen=True)
class ContextualCandidateForecast:
    candidate_id: str
    trajectory: tuple[tuple[tuple[State, Fraction], ...], ...]


@dataclass(frozen=True)
class ContextualQueryScore:
    query_id: str
    status: str
    pairwise_tv_disagreement: Fraction | None
    utility: Fraction | None
    forecasts: tuple[ContextualCandidateForecast, ...]


@dataclass(frozen=True)
class ContextualQuerySelection:
    status: str
    selected: ContextualQueryScore | None
    ranked: tuple[ContextualQueryScore, ...]
    rejected: tuple[tuple[str, str], ...]


def _trajectory_disagreement(
    left: tuple[tuple[tuple[State, Fraction], ...], ...],
    right: tuple[tuple[tuple[State, Fraction], ...], ...],
) -> Fraction:
    if len(left) != len(right):
        raise StochasticContractError("CANDIDATE_TRAJECTORY_LENGTH_MISMATCH")
    if not left:
        return Fraction(0)
    return sum((total_variation_distance(a, b) for a, b in zip(left, right)),
               Fraction(0)) / len(left)


def select_contextual_discriminating_sequence(
    candidates: Iterable[ContextualMechanismCandidate],
    queries: Iterable[ContextualSequenceQuery],
    initial_state: State,
    context: Context,
    *,
    max_risk: Fraction = Fraction(1),
    max_cost: Fraction | None = None,
    risk_weight: Fraction = Fraction(0),
    cost_weight: Fraction = Fraction(0),
) -> ContextualQuerySelection:
    """Select the safest affordable query with greatest exact model disagreement.

    Hard authorization/risk/cost gates precede scoring. Utility is a ranking
    heuristic, not expected information gain. No posterior is updated here.
    """
    candidate_list, query_list = tuple(candidates), tuple(queries)
    risk_limit = _prob(max_risk)
    cost_limit = None if max_cost is None else _prob(max_cost)
    rw, cw = _prob(risk_weight), _prob(cost_weight)
    if not candidate_list:
        raise StochasticContractError("AT_LEAST_ONE_CANDIDATE_REQUIRED")
    ids = [c.candidate_id for c in candidate_list]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise StochasticContractError("CANDIDATE_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
    qids = [q.query_id for q in query_list]
    if any(not x for x in qids) or len(set(qids)) != len(qids):
        raise StochasticContractError("QUERY_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
    if rw < 0 or cw < 0:
        raise StochasticContractError("UTILITY_WEIGHTS_MUST_BE_NONNEGATIVE")

    ranked, rejected = [], []
    for query in query_list:
        risk, cost = _prob(query.risk), _prob(query.cost)
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
        for candidate in candidate_list:
            try:
                trajectory = propagate_contextual_distribution(
                    candidate.system, initial_state, query.actions, context
                )
            except StochasticContractError as exc:
                if str(exc) in ("MISSING_CONTEXTUAL_TRANSITION_ROW",
                                "INVALID_INITIAL_STATE", "INVALID_CONTEXT"):
                    complete = False
                    break
                raise
            forecasts.append(ContextualCandidateForecast(
                candidate.candidate_id, trajectory
            ))
        if not complete:
            rejected.append((query.query_id, "UNKNOWN_INCOMPLETE_CANDIDATE_FORECAST"))
            continue
        if len(forecasts) < 2:
            disagreement = Fraction(0)
        else:
            pairs = tuple(combinations(forecasts, 2))
            disagreement = sum((
                _trajectory_disagreement(a.trajectory, b.trajectory)
                for a, b in pairs
            ), Fraction(0)) / len(pairs)
        utility = disagreement - rw * risk - cw * cost
        ranked.append(ContextualQueryScore(
            query.query_id, "SCORED", disagreement, utility, tuple(forecasts)
        ))

    ranked.sort(key=lambda item: (-item.utility, -item.pairwise_tv_disagreement,
                                  item.query_id))
    if not ranked:
        return ContextualQuerySelection("NO_SAFE_COMPLETE_QUERY", None, (), tuple(rejected))
    if len(ranked) == 1 or all(item.pairwise_tv_disagreement == 0 for item in ranked):
        return ContextualQuerySelection("NO_DISAGREEMENT", ranked[0], tuple(ranked), tuple(rejected))
    return ContextualQuerySelection("SELECTED", ranked[0], tuple(ranked), tuple(rejected))
