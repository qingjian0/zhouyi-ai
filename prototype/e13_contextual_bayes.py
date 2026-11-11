"""E13-C.3.6 exact Bayesian filtering over finite hidden-state candidates.

Each hypothesis is a joint mechanism + observation-channel candidate. The
filter maintains both its posterior model weight and its conditional latent
state distribution, so sequential evidence is not approximated by multiplying
unconditional per-time marginals.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from .e13_stochastic import (
    ObservationKernel, StochasticContractError, _prob, _state,
)
from .e13_contextual_stochastic import (
    Context, State, ContextualProbabilisticTransitionSystem, _context,
)


@dataclass(frozen=True)
class BayesianObservationCandidate:
    candidate_id: str
    system: ContextualProbabilisticTransitionSystem
    observation_channels: tuple[tuple[str, ObservationKernel], ...]


@dataclass(frozen=True)
class CandidateBelief:
    candidate_id: str
    posterior_weight: Fraction
    latent_state_distribution: tuple[tuple[State, Fraction], ...]


@dataclass(frozen=True)
class ObservationEvidenceStep:
    evidence_id: str
    sensor_id: str
    action: str | None
    observation: str


@dataclass(frozen=True)
class BayesianObservationBelief:
    status: str
    context: Context
    candidates: tuple[BayesianObservationCandidate, ...]
    candidate_beliefs: tuple[CandidateBelief, ...]
    evidence: tuple[ObservationEvidenceStep, ...]


@dataclass(frozen=True)
class BayesianUpdateResult:
    status: str
    belief: BayesianObservationBelief | None
    predictive_evidence_probability: Fraction | None
    candidate_likelihoods: tuple[tuple[str, Fraction], ...]
    reason: str | None = None


def _channel_for(candidate: BayesianObservationCandidate, sensor_id: str):
    matches = [kernel for key, kernel in candidate.observation_channels if key == sensor_id]
    if len(matches) != 1:
        return None
    return matches[0]


def _normalize_state_mass(items: Iterable[tuple[State, Fraction]]):
    merged: dict[State, Fraction] = {}
    for raw_state, raw_mass in items:
        state, mass = _state(raw_state), _prob(raw_mass)
        merged[state] = merged.get(state, Fraction(0)) + mass
    total = sum(merged.values(), Fraction(0))
    if total == 0:
        return ()
    return tuple((state, mass / total) for state, mass in sorted(merged.items()) if mass)


def _validated_initial_distribution(initial_distribution):
    items = tuple((_state(state), _prob(probability))
                  for state, probability in initial_distribution)
    if not items:
        raise StochasticContractError("INITIAL_DISTRIBUTION_REQUIRED")
    total = sum((p for _, p in items), Fraction(0))
    if total != 1:
        raise StochasticContractError("INITIAL_DISTRIBUTION_MUST_SUM_TO_ONE")
    return _normalize_state_mass(items)


def initialize_observation_belief(
    candidates: Iterable[BayesianObservationCandidate],
    prior_weights: Iterable[tuple[str, Fraction | int | str]],
    initial_distribution: Iterable[tuple[State, Fraction | int | str]],
    context: Context,
    sensor_id: str,
    initial_observation: str,
    evidence_id: str,
) -> BayesianUpdateResult:
    """Condition model priors and hidden states on the first observation."""
    candidate_list = tuple(candidates)
    priors = tuple((candidate_id, _prob(weight)) for candidate_id, weight in prior_weights)
    if not candidate_list:
        raise StochasticContractError("AT_LEAST_ONE_CANDIDATE_REQUIRED")
    ids = [item.candidate_id for item in candidate_list]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        raise StochasticContractError("CANDIDATE_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
    if len(priors) != len(candidate_list) or {key for key, _ in priors} != set(ids):
        raise StochasticContractError("PRIOR_WEIGHTS_MUST_COVER_CANDIDATES_EXACTLY")
    if sum((weight for _, weight in priors), Fraction(0)) != 1:
        raise StochasticContractError("PRIOR_WEIGHTS_MUST_SUM_TO_ONE")
    if not sensor_id or not initial_observation or not evidence_id:
        raise StochasticContractError("INITIAL_EVIDENCE_FIELDS_REQUIRED")
    fixed_context = _context(context)
    initial = _validated_initial_distribution(initial_distribution)
    prior_map = dict(priors)

    likelihoods: dict[str, Fraction] = {}
    state_posteriors: dict[str, tuple[tuple[State, Fraction], ...]] = {}
    for candidate in candidate_list:
        prior = prior_map[candidate.candidate_id]
        if prior == 0:
            likelihoods[candidate.candidate_id] = Fraction(0)
            state_posteriors[candidate.candidate_id] = ()
            continue
        channel = _channel_for(candidate, sensor_id)
        if channel is None:
            return BayesianUpdateResult(
                "UNKNOWN", None, None, (),
                f"MISSING_OR_AMBIGUOUS_OBSERVATION_CHANNEL:{candidate.candidate_id}",
            )
        weighted_states = []
        likelihood = Fraction(0)
        for state, mass in initial:
            distribution = channel.observe(state)
            if distribution is None:
                return BayesianUpdateResult(
                    "UNKNOWN", None, None, (),
                    f"MISSING_OBSERVATION_SUPPORT:{candidate.candidate_id}",
                )
            probability = dict(distribution).get(initial_observation, Fraction(0))
            likelihood += mass * probability
            if probability:
                weighted_states.append((state, mass * probability))
        likelihoods[candidate.candidate_id] = likelihood
        state_posteriors[candidate.candidate_id] = _normalize_state_mass(weighted_states)

    evidence_probability = sum(
        (prior_map[candidate_id] * likelihood
         for candidate_id, likelihood in likelihoods.items()),
        Fraction(0),
    )
    if evidence_probability == 0:
        return BayesianUpdateResult(
            "CONTRADICTION", None, Fraction(0),
            tuple(sorted(likelihoods.items())),
            "OBSERVATION_HAS_ZERO_PROBABILITY_UNDER_ALL_CANDIDATES",
        )

    beliefs = []
    for candidate in candidate_list:
        candidate_id = candidate.candidate_id
        weight = prior_map[candidate_id] * likelihoods[candidate_id] / evidence_probability
        beliefs.append(CandidateBelief(
            candidate_id, weight, state_posteriors[candidate_id]
        ))
    belief = BayesianObservationBelief(
        "ACTIVE", fixed_context, candidate_list, tuple(beliefs),
        (ObservationEvidenceStep(evidence_id, sensor_id, None, initial_observation),),
    )
    return BayesianUpdateResult(
        "UPDATED", belief, evidence_probability,
        tuple(sorted(likelihoods.items())),
    )


def advance_observation_belief(
    belief: BayesianObservationBelief,
    action: str,
    sensor_id: str,
    observation: str,
    evidence_id: str,
) -> BayesianUpdateResult:
    """Perform one exact Bayesian filter step with a new action/observation."""
    if belief.status != "ACTIVE":
        raise StochasticContractError("BELIEF_NOT_ACTIVE")
    if not action or not sensor_id or not observation or not evidence_id:
        raise StochasticContractError("EVIDENCE_STEP_FIELDS_REQUIRED")
    if any(step.evidence_id == evidence_id for step in belief.evidence):
        raise StochasticContractError("DUPLICATE_EVIDENCE_ID")

    beliefs_by_id = {item.candidate_id: item for item in belief.candidate_beliefs}
    candidate_likelihoods: dict[str, Fraction] = {}
    next_state_posteriors: dict[str, tuple[tuple[State, Fraction], ...]] = {}
    for candidate in belief.candidates:
        current = beliefs_by_id[candidate.candidate_id]
        if current.posterior_weight == 0:
            candidate_likelihoods[candidate.candidate_id] = Fraction(0)
            next_state_posteriors[candidate.candidate_id] = ()
            continue
        channel = _channel_for(candidate, sensor_id)
        if channel is None:
            return BayesianUpdateResult(
                "UNKNOWN", None, None, (),
                f"MISSING_OR_AMBIGUOUS_OBSERVATION_CHANNEL:{candidate.candidate_id}",
            )
        weighted_next_states = []
        predictive_likelihood = Fraction(0)
        for state, state_mass in current.latent_state_distribution:
            outcomes = candidate.system.transition(state, action, belief.context)
            if outcomes is None:
                return BayesianUpdateResult(
                    "UNKNOWN", None, None, (),
                    f"MISSING_CONTEXTUAL_TRANSITION_ROW:{candidate.candidate_id}",
                )
            for next_state, transition_probability in outcomes:
                observation_distribution = channel.observe(next_state)
                if observation_distribution is None:
                    return BayesianUpdateResult(
                        "UNKNOWN", None, None, (),
                        f"MISSING_OBSERVATION_SUPPORT:{candidate.candidate_id}",
                    )
                observation_probability = dict(observation_distribution).get(
                    observation, Fraction(0)
                )
                joint_mass = (
                    state_mass * transition_probability * observation_probability
                )
                predictive_likelihood += joint_mass
                if joint_mass:
                    weighted_next_states.append((next_state, joint_mass))
        candidate_likelihoods[candidate.candidate_id] = predictive_likelihood
        next_state_posteriors[candidate.candidate_id] = _normalize_state_mass(
            weighted_next_states
        )

    evidence_probability = sum((
        beliefs_by_id[candidate_id].posterior_weight * likelihood
        for candidate_id, likelihood in candidate_likelihoods.items()
    ), Fraction(0))
    if evidence_probability == 0:
        return BayesianUpdateResult(
            "CONTRADICTION", None, Fraction(0),
            tuple(sorted(candidate_likelihoods.items())),
            "OBSERVATION_HAS_ZERO_PREDICTIVE_PROBABILITY",
        )

    updated_beliefs = []
    for candidate in belief.candidates:
        candidate_id = candidate.candidate_id
        previous_weight = beliefs_by_id[candidate_id].posterior_weight
        posterior_weight = (
            previous_weight * candidate_likelihoods[candidate_id] / evidence_probability
        )
        updated_beliefs.append(CandidateBelief(
            candidate_id, posterior_weight, next_state_posteriors[candidate_id]
        ))
    updated = BayesianObservationBelief(
        "ACTIVE", belief.context, belief.candidates, tuple(updated_beliefs),
        belief.evidence + (
            ObservationEvidenceStep(evidence_id, sensor_id, action, observation),
        ),
    )
    return BayesianUpdateResult(
        "UPDATED", updated, evidence_probability,
        tuple(sorted(candidate_likelihoods.items())),
    )
