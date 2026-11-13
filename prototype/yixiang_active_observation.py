"""M5 active observation selection with transparent Bayesian information gain.

This ranks prospective, non-interventional observations. It does not execute
measurements, establish causal effects, or convert predicted likelihoods into
observed evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log2


@dataclass(frozen=True)
class HypothesisPrior:
    hypothesis_id: str
    probability: float

    def validate(self) -> None:
        if not isinstance(self.hypothesis_id, str) or not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")
        if isinstance(self.probability, bool) or not isinstance(self.probability, (int, float)):
            raise ValueError("prior probability must be numeric")
        if not isfinite(self.probability) or not 0.0 <= self.probability <= 1.0:
            raise ValueError("prior probability must be finite and in [0, 1]")


@dataclass(frozen=True)
class ObservationCandidate:
    observation_id: str
    measurement: str
    # Rows are (hypothesis_id, outcome_label, P(outcome | hypothesis)).
    likelihoods: tuple[tuple[str, str, float], ...]
    cost: float = 0.0
    risk: float = 0.0
    feasibility: float = 1.0
    selection_bias: float = 0.0

    def validate(self, hypothesis_ids: set[str]) -> None:
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise ValueError("observation_id is required")
        if not isinstance(self.measurement, str) or not self.measurement.strip():
            raise ValueError("measurement description is required")
        if not isinstance(self.likelihoods, tuple) or not self.likelihoods:
            raise ValueError("likelihoods must be a non-empty tuple")
        grouped: dict[str, dict[str, float]] = {}
        for row in self.likelihoods:
            if not isinstance(row, tuple) or len(row) != 3:
                raise ValueError("each likelihood row must be (hypothesis_id, outcome, probability)")
            hypothesis_id, outcome, probability = row
            if not isinstance(hypothesis_id, str) or hypothesis_id not in hypothesis_ids:
                raise ValueError("unknown or invalid hypothesis in likelihoods")
            if not isinstance(outcome, str) or not outcome.strip():
                raise ValueError("outcome labels must be non-empty strings")
            if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                raise ValueError("likelihood probability must be numeric")
            if not isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError("likelihood probability must be finite and in [0, 1]")
            outcomes = grouped.setdefault(hypothesis_id, {})
            if outcome in outcomes:
                raise ValueError("duplicate hypothesis/outcome likelihood")
            outcomes[outcome] = float(probability)
        if set(grouped) != hypothesis_ids:
            raise ValueError("every hypothesis must define an outcome distribution")
        for distribution in grouped.values():
            if abs(sum(distribution.values()) - 1.0) > 1e-9:
                raise ValueError("likelihoods for each hypothesis must sum to 1")
        for name, value in (("cost", self.cost), ("risk", self.risk),
                            ("feasibility", self.feasibility),
                            ("selection_bias", self.selection_bias)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if self.cost < 0:
            raise ValueError("cost must be non-negative")
        for name, value in (("risk", self.risk), ("feasibility", self.feasibility),
                            ("selection_bias", self.selection_bias)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class ObservationScore:
    observation_id: str
    information_gain_bits: float
    expected_posterior_entropy_bits: float
    expected_outcomes: tuple[tuple[str, float], ...]
    utility: float


@dataclass(frozen=True)
class ObservationSelection:
    selected: ObservationScore
    ranking: tuple[ObservationScore, ...]
    evidence_status: str = "prospective_only"


def _entropy(probabilities: tuple[float, ...]) -> float:
    return -sum(p * log2(p) for p in probabilities if p > 0.0)


def _validate_priors(priors: tuple[HypothesisPrior, ...]) -> tuple[str, ...]:
    if not isinstance(priors, tuple) or not priors:
        raise ValueError("at least one hypothesis prior is required")
    for prior in priors:
        if not isinstance(prior, HypothesisPrior):
            raise ValueError("priors must contain HypothesisPrior values")
        prior.validate()
    ids = tuple(prior.hypothesis_id for prior in priors)
    if len(ids) != len(set(ids)):
        raise ValueError("hypothesis ids must be unique")
    if abs(sum(prior.probability for prior in priors) - 1.0) > 1e-9:
        raise ValueError("prior probabilities must sum to 1")
    return ids


def score_observation(
    priors: tuple[HypothesisPrior, ...], candidate: ObservationCandidate
) -> ObservationScore:
    ids = _validate_priors(priors)
    if not isinstance(candidate, ObservationCandidate):
        raise ValueError("candidate must be an ObservationCandidate")
    candidate.validate(set(ids))

    prior_map = {prior.hypothesis_id: float(prior.probability) for prior in priors}
    likelihood_map: dict[str, dict[str, float]] = {}
    for hypothesis_id, outcome, probability in candidate.likelihoods:
        likelihood_map.setdefault(hypothesis_id, {})[outcome] = float(probability)

    outcome_names = sorted({outcome for _, outcome, _ in candidate.likelihoods})
    predictive = {
        outcome: sum(prior_map[h] * likelihood_map[h].get(outcome, 0.0) for h in ids)
        for outcome in outcome_names
    }
    expected_entropy = 0.0
    for outcome, outcome_probability in predictive.items():
        if outcome_probability == 0.0:
            continue
        posterior = tuple(
            prior_map[h] * likelihood_map[h].get(outcome, 0.0) / outcome_probability
            for h in ids
        )
        expected_entropy += outcome_probability * _entropy(posterior)

    prior_entropy = _entropy(tuple(prior_map[h] for h in ids))
    information_gain = max(0.0, prior_entropy - expected_entropy)
    utility = (
        information_gain * candidate.feasibility * (1.0 - candidate.risk)
        * (1.0 - candidate.selection_bias) / (1.0 + candidate.cost)
    )
    return ObservationScore(
        candidate.observation_id,
        information_gain,
        expected_entropy,
        tuple((name, predictive[name]) for name in outcome_names),
        utility,
    )


def select_observation(
    priors: tuple[HypothesisPrior, ...],
    candidates: tuple[ObservationCandidate, ...],
) -> ObservationSelection | None:
    """Choose the highest utility prospective observation; ties break by ID."""
    ids = _validate_priors(priors)
    if not isinstance(candidates, tuple):
        raise ValueError("candidates must be a tuple")
    if not candidates:
        return None
    for candidate in candidates:
        if not isinstance(candidate, ObservationCandidate):
            raise ValueError("candidates must contain ObservationCandidate values")
        candidate.validate(set(ids))
    candidate_ids = [candidate.observation_id for candidate in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("observation ids must be unique")
    ranking = tuple(sorted(
        (score_observation(priors, candidate) for candidate in candidates),
        key=lambda score: (-score.utility, -score.information_gain_bits, score.observation_id),
    ))
    return ObservationSelection(ranking[0], ranking)
