"""E12-A2-M: finite-hypothesis active measurement selection.

The learner receives only candidate likelihoods, declared priors, action costs,
and a remaining budget. Environment truth is intentionally absent from this API.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from typing import Literal

DecisionStatus = Literal[
    "SELECTED", "NO_DISCRIMINATING_ACTION", "BUDGET_EXHAUSTED", "INVALID_ACTION_SET"
]
UpdateStatus = Literal["UPDATED", "INCONSISTENT"]


@dataclass(frozen=True, order=True)
class Hypothesis:
    hypothesis_id: str
    prior: float


@dataclass(frozen=True, order=True)
class OutcomeLikelihood:
    outcome: str
    probability: float


@dataclass(frozen=True, order=True)
class HypothesisPrediction:
    hypothesis_id: str
    likelihoods: tuple[OutcomeLikelihood, ...]


@dataclass(frozen=True, order=True)
class MeasurementAction:
    action_id: str
    cost: float
    predictions: tuple[HypothesisPrediction, ...]


@dataclass(frozen=True)
class SelectionResult:
    status: DecisionStatus
    selected_action_id: str | None
    information_gain_bits: float | None
    utility_bits_per_cost: float | None
    eligible_action_count: int
    reason: str


@dataclass(frozen=True)
class PosteriorResult:
    status: UpdateStatus
    weights: tuple[tuple[str, float], ...]
    reason: str


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def entropy_bits(weights: tuple[float, ...] | list[float]) -> float:
    """Shannon entropy in bits; zero-weight terms contribute zero."""
    if any(not _finite_number(weight) or weight < 0 for weight in weights):
        raise ValueError("weights must be finite and non-negative")
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must have positive total mass")
    normalized = [weight / total for weight in weights]
    return -sum(p * math.log2(p) for p in normalized if p > 0)


def _validate_hypotheses(hypotheses: tuple[Hypothesis, ...]) -> None:
    if not hypotheses:
        raise ValueError("hypotheses must be non-empty")
    ids = [item.hypothesis_id for item in hypotheses]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("hypothesis IDs must be non-empty and unique")
    if any(not _finite_number(item.prior) or item.prior < 0 for item in hypotheses):
        raise ValueError("prior weights must be finite and non-negative")
    if not math.isclose(sum(item.prior for item in hypotheses), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("prior weights must sum to 1")


def _validate_actions(
    hypotheses: tuple[Hypothesis, ...], actions: tuple[MeasurementAction, ...]
) -> None:
    if not actions:
        raise ValueError("action set must be non-empty")
    action_ids = [action.action_id for action in actions]
    if any(not item for item in action_ids) or len(action_ids) != len(set(action_ids)):
        raise ValueError("action IDs must be non-empty and unique")
    expected_ids = {item.hypothesis_id for item in hypotheses}
    for action in actions:
        if not _finite_number(action.cost) or action.cost <= 0:
            raise ValueError("action costs must be finite and positive")
        prediction_ids = [item.hypothesis_id for item in action.predictions]
        if set(prediction_ids) != expected_ids or len(prediction_ids) != len(expected_ids):
            raise ValueError(f"{action.action_id}: predictions must cover each hypothesis exactly once")
        for prediction in action.predictions:
            if not prediction.likelihoods:
                raise ValueError(f"{action.action_id}/{prediction.hypothesis_id}: empty outcome support")
            outcomes = [item.outcome for item in prediction.likelihoods]
            if any(not item for item in outcomes) or len(outcomes) != len(set(outcomes)):
                raise ValueError("outcome names must be non-empty and unique per hypothesis")
            probabilities = [item.probability for item in prediction.likelihoods]
            if any(not _finite_number(p) or p < 0 for p in probabilities):
                raise ValueError("likelihoods must be finite and non-negative")
            if not math.isclose(sum(probabilities), 1.0, rel_tol=0, abs_tol=1e-9):
                raise ValueError("likelihoods for each hypothesis/action must sum to 1")


def _information_gain(
    hypotheses: tuple[Hypothesis, ...], action: MeasurementAction
) -> float:
    priors = {item.hypothesis_id: item.prior for item in hypotheses}
    predictions = {item.hypothesis_id: item for item in action.predictions}
    outcomes = sorted({
        likelihood.outcome
        for prediction in action.predictions
        for likelihood in prediction.likelihoods
    })
    prior_entropy = entropy_bits([item.prior for item in hypotheses])
    expected_posterior_entropy = 0.0
    for outcome in outcomes:
        joint = {
            hypothesis_id: priors[hypothesis_id] * next(
                (item.probability for item in predictions[hypothesis_id].likelihoods
                 if item.outcome == outcome), 0.0
            )
            for hypothesis_id in priors
        }
        outcome_probability = sum(joint.values())
        if outcome_probability <= 0:
            continue
        posterior = [mass / outcome_probability for mass in joint.values()]
        expected_posterior_entropy += outcome_probability * entropy_bits(posterior)
    # Floating point round-off must not create negative information.
    return max(0.0, prior_entropy - expected_posterior_entropy)


def select_measurement(
    hypotheses: tuple[Hypothesis, ...],
    actions: tuple[MeasurementAction, ...],
    remaining_budget: float,
    epsilon: float = 1e-12,
    tie_tolerance: float = 1e-12,
) -> SelectionResult:
    """Select the highest cost-normalized expected-IG action, or abstain."""
    try:
        _validate_hypotheses(hypotheses)
        _validate_actions(hypotheses, actions)
        if not _finite_number(remaining_budget) or remaining_budget < 0:
            raise ValueError("remaining_budget must be finite and non-negative")
        if not _finite_number(epsilon) or epsilon <= 0:
            raise ValueError("epsilon must be finite and positive")
        if not _finite_number(tie_tolerance) or tie_tolerance < 0:
            raise ValueError("tie_tolerance must be finite and non-negative")
    except (TypeError, ValueError) as exc:
        return SelectionResult("INVALID_ACTION_SET", None, None, None, 0, str(exc))

    eligible = [action for action in actions if action.cost <= remaining_budget]
    if not eligible:
        return SelectionResult(
            "BUDGET_EXHAUSTED", None, None, None, 0,
            "No permitted measurement fits the remaining acquisition budget",
        )

    scored = []
    for action in eligible:
        gain = _information_gain(hypotheses, action)
        utility = gain / (action.cost + epsilon)
        scored.append((action, gain, utility))
    if all(gain <= tie_tolerance for _, gain, _ in scored):
        return SelectionResult(
            "NO_DISCRIMINATING_ACTION", None, 0.0, 0.0, len(eligible),
            "Every eligible action has zero expected information gain",
        )

    best_utility = max(item[2] for item in scored)
    tied = [
        item for item in scored
        if best_utility - item[2] <= tie_tolerance
    ]
    # Stable, truth-independent tie-break: lower cost, then canonical action ID.
    selected, gain, utility = min(tied, key=lambda item: (item[0].cost, item[0].action_id))
    return SelectionResult(
        "SELECTED", selected.action_id, gain, utility, len(eligible),
        "Selected the eligible action with highest expected information gain per unit cost",
    )


def update_after_observation(
    hypotheses: tuple[Hypothesis, ...],
    action: MeasurementAction,
    observed_outcome: str,
) -> PosteriorResult:
    """Bayesian update using only a revealed observation, never evaluator truth."""
    try:
        _validate_hypotheses(hypotheses)
        _validate_actions(hypotheses, (action,))
        if not isinstance(observed_outcome, str) or not observed_outcome:
            raise ValueError("observed_outcome must be a non-empty string")
    except (TypeError, ValueError) as exc:
        return PosteriorResult("INCONSISTENT", (), str(exc))

    prior = {item.hypothesis_id: item.prior for item in hypotheses}
    likelihoods = {
        item.hypothesis_id: next(
            (entry.probability for entry in item.likelihoods if entry.outcome == observed_outcome),
            0.0,
        )
        for item in action.predictions
    }
    unnormalized = {
        hypothesis_id: prior[hypothesis_id] * likelihoods[hypothesis_id]
        for hypothesis_id in prior
    }
    evidence = sum(unnormalized.values())
    if evidence <= 0:
        return PosteriorResult(
            "INCONSISTENT", (),
            "Observed outcome has zero likelihood under every candidate hypothesis",
        )
    posterior = tuple(
        (hypothesis_id, unnormalized[hypothesis_id] / evidence)
        for hypothesis_id in sorted(unnormalized)
    )
    return PosteriorResult("UPDATED", posterior, "Posterior updated from the revealed observation")


def _binary_action(action_id: str, cost: float, predictions: dict[str, int]) -> MeasurementAction:
    return MeasurementAction(
        action_id,
        cost,
        tuple(
            HypothesisPrediction(hypothesis_id, (
                OutcomeLikelihood("0", float(1 - value)),
                OutcomeLikelihood("1", float(value)),
            ))
            for hypothesis_id, value in sorted(predictions.items())
        ),
    )


def demo() -> dict:
    hypotheses = (Hypothesis("p_ge_2", 0.5), Hypothesis("p_eq_2", 0.5))
    actions = (
        _binary_action("measure_x_0", 1.0, {"p_ge_2": 0, "p_eq_2": 0}),
        _binary_action("measure_x_2", 1.0, {"p_ge_2": 1, "p_eq_2": 1}),
        _binary_action("measure_x_3", 1.0, {"p_ge_2": 1, "p_eq_2": 0}),
    )
    selected = select_measurement(hypotheses, actions, remaining_budget=1.0)
    return {
        "selection": asdict(selected),
        "after_observation": asdict(update_after_observation(hypotheses, actions[2], "1")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = demo()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.json else None))


if __name__ == "__main__":
    main()
