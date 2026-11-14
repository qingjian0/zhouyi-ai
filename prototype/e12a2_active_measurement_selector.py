"""E12-A2-M: cost-aware active measurement selection by expected information gain.

This module is a deterministic, finite-hypothesis baseline. It does not perform
interventions or causal discovery.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def _entropy(weights: Mapping[str, float]) -> float:
    return -sum(p * math.log2(p) for p in weights.values() if p > 0.0)


def _normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    if not weights:
        raise ValueError("at least one hypothesis is required")
    cleaned: dict[str, float] = {}
    for key, value in weights.items():
        if not isinstance(key, str) or not key:
            raise ValueError("hypothesis IDs must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("hypothesis weights must be numeric")
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise ValueError("hypothesis weights must be finite and non-negative")
        cleaned[key] = value
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("hypothesis weights must have positive total mass")
    return {key: value / total for key, value in cleaned.items()}


def _validate_predictions(
    hypothesis_ids: set[str],
    predictions: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> None:
    for action_id, by_hypothesis in predictions.items():
        if not isinstance(action_id, str) or not action_id:
            raise ValueError("action IDs must be non-empty strings")
        if set(by_hypothesis) != hypothesis_ids:
            raise ValueError(f"{action_id}: predictions must cover every hypothesis exactly")
        outcome_sets: list[set[str]] = []
        for hypothesis_id, distribution in by_hypothesis.items():
            if not distribution:
                raise ValueError(f"{action_id}/{hypothesis_id}: empty outcome distribution")
            total = 0.0
            for outcome, probability in distribution.items():
                if not isinstance(outcome, str) or not outcome:
                    raise ValueError("outcome IDs must be non-empty strings")
                if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                    raise TypeError("outcome probabilities must be numeric")
                probability = float(probability)
                if not math.isfinite(probability) or probability < 0:
                    raise ValueError("outcome probabilities must be finite and non-negative")
                total += probability
            if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f"{action_id}/{hypothesis_id}: probabilities must sum to 1")
            outcome_sets.append(set(distribution))
        if any(outcomes != outcome_sets[0] for outcomes in outcome_sets[1:]):
            raise ValueError(f"{action_id}: hypotheses must share the declared outcome space")


def expected_information_gain(
    weights: Mapping[str, float],
    predictions: Mapping[str, Mapping[str, float]],
) -> float:
    """Return mutual information I(H; O | action), in bits."""
    prior = _normalize_weights(weights)
    if set(predictions) != set(prior):
        raise ValueError("predictions must cover every hypothesis exactly")
    _validate_predictions(set(prior), {"_": predictions})
    outcomes = sorted(next(iter(predictions.values())))
    prior_entropy = _entropy(prior)
    expected_posterior_entropy = 0.0
    for outcome in outcomes:
        marginal = sum(
            prior[hypothesis_id] * float(predictions[hypothesis_id][outcome])
            for hypothesis_id in prior
        )
        if marginal <= 0:
            continue
        posterior = {
            hypothesis_id: prior[hypothesis_id] * float(predictions[hypothesis_id][outcome]) / marginal
            for hypothesis_id in prior
        }
        expected_posterior_entropy += marginal * _entropy(posterior)
    return max(0.0, prior_entropy - expected_posterior_entropy)


def select_measurement(
    weights: Mapping[str, float],
    predictions: Mapping[str, Mapping[str, Mapping[str, float]]],
    costs: Mapping[str, float],
    remaining_budget: float,
    *,
    epsilon: float = 1e-9,
    tie_tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Select a permitted measurement or return an explicit abstention state.

    predictions[action][hypothesis][outcome] = P(outcome | hypothesis, action)
    """
    prior = _normalize_weights(weights)
    if not math.isfinite(float(remaining_budget)) or remaining_budget < 0:
        raise ValueError("remaining_budget must be finite and non-negative")
    if not math.isfinite(float(epsilon)) or epsilon <= 0:
        raise ValueError("epsilon must be finite and positive")
    if not math.isfinite(float(tie_tolerance)) or tie_tolerance < 0:
        raise ValueError("tie_tolerance must be finite and non-negative")
    if not predictions or set(predictions) != set(costs):
        return {"status": "INVALID_ACTION_SET", "selected_action": None, "evaluated": []}

    _validate_predictions(set(prior), predictions)
    normalized_costs: dict[str, float] = {}
    for action_id, cost in costs.items():
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise TypeError("action costs must be numeric")
        cost = float(cost)
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("action costs must be finite and non-negative")
        normalized_costs[action_id] = cost

    feasible = [
        action_id for action_id in sorted(predictions)
        if normalized_costs[action_id] <= remaining_budget
    ]
    if not feasible:
        return {
            "status": "BUDGET_EXHAUSTED",
            "selected_action": None,
            "evaluated": [],
        }

    evaluated = []
    for action_id in feasible:
        gain = expected_information_gain(prior, predictions[action_id])
        cost = normalized_costs[action_id]
        evaluated.append({
            "action_id": action_id,
            "expected_information_gain_bits": gain,
            "cost": cost,
            "utility": gain / (cost + epsilon),
        })

    best_gain = max(item["expected_information_gain_bits"] for item in evaluated)
    if best_gain <= tie_tolerance:
        return {
            "status": "NO_DISCRIMINATING_ACTION",
            "selected_action": None,
            "evaluated": evaluated,
        }

    best_utility = max(item["utility"] for item in evaluated)
    tied = [
        item for item in evaluated
        if best_utility - item["utility"] <= tie_tolerance
    ]
    selected = min(tied, key=lambda item: (item["cost"], item["action_id"]))
    return {
        "status": "SELECTED",
        "selected_action": selected["action_id"],
        "expected_information_gain_bits": selected["expected_information_gain_bits"],
        "utility": selected["utility"],
        "evaluated": evaluated,
    }


def update_weights(
    weights: Mapping[str, float],
    predictions: Mapping[str, Mapping[str, float]],
    observed_outcome: str,
) -> dict[str, float]:
    """Bayesian update after the environment reveals one measurement outcome."""
    prior = _normalize_weights(weights)
    if set(predictions) != set(prior):
        raise ValueError("predictions must cover every hypothesis exactly")
    _validate_predictions(set(prior), {"_": predictions})
    if observed_outcome not in next(iter(predictions.values())):
        raise ValueError("observed outcome is outside the declared outcome space")
    unnormalized = {
        hypothesis_id: prior[hypothesis_id] * float(distribution[observed_outcome])
        for hypothesis_id, distribution in predictions.items()
    }
    total = sum(unnormalized.values())
    if total <= 0:
        raise ValueError("observed outcome has zero likelihood under every hypothesis")
    return {key: value / total for key, value in unnormalized.items()}


def demo() -> dict[str, Any]:
    weights = {"threshold": 0.5, "equality": 0.5}
    predictions = {
        "probe_low": {
            "threshold": {"yes": 0.0, "no": 1.0},
            "equality": {"yes": 0.0, "no": 1.0},
        },
        "probe_high": {
            "threshold": {"yes": 1.0, "no": 0.0},
            "equality": {"yes": 0.0, "no": 1.0},
        },
    }
    return select_measurement(weights, predictions, {"probe_low": 1.0, "probe_high": 2.0}, 2.0)


if __name__ == "__main__":
    import json
    print(json.dumps(demo(), indent=2, ensure_ascii=False))
