"""Learner-side active challenge selection; no evaluator oracle inputs."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, log2
from typing import Hashable, Mapping

@dataclass(frozen=True)
class ChallengeChoice:
    action: str | None
    expected_information_gain: float
    information_gain_per_cost: float
    cost: float
    scores: tuple[tuple[str, float, float], ...]
    reason: str

def _entropy(probabilities):
    return -sum(p * log2(p) for p in probabilities if p > 0)

def _distribution(raw, label):
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError(label + " distribution must be non-empty")
    values = {}
    for key, probability in raw.items():
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            raise ValueError(label + " probabilities must be numeric")
        probability = float(probability)
        if not isfinite(probability) or probability < 0:
            raise ValueError(label + " probabilities must be finite and >= 0")
        values[key] = probability
    if abs(sum(values.values()) - 1.0) > 1e-9:
        raise ValueError(label + " probabilities must sum to 1")
    return values

def schedule_challenge(hypothesis_priors: Mapping[str, float],
                       predicted_outcomes: Mapping[str, Mapping[str, Mapping[Hashable, float]]],
                       action_costs: Mapping[str, float], *, remaining_budget: float,
                       min_information_gain_per_cost: float = 0.0) -> ChallengeChoice:
    """Maximize one-step mutual information per cost; abstain if infeasible."""
    priors = _distribution(hypothesis_priors, "hypothesis prior")
    if any(not isinstance(h, str) or not h for h in priors):
        raise ValueError("hypothesis identifiers must be non-empty strings")
    if set(predicted_outcomes) != set(priors):
        raise ValueError("predictions must cover exactly the declared hypotheses")
    if not action_costs:
        raise ValueError("action_costs must be non-empty")
    costs = {}
    for action, cost in action_costs.items():
        if not isinstance(action, str) or not action:
            raise ValueError("action names must be non-empty strings")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise ValueError("action costs must be numeric")
        cost = float(cost)
        if not isfinite(cost) or cost <= 0:
            raise ValueError("action costs must be finite and > 0")
        costs[action] = cost
    for name, value in (("remaining_budget", remaining_budget),
                        ("min_information_gain_per_cost", min_information_gain_per_cost)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(name + " must be numeric")
        if not isfinite(float(value)) or value < 0:
            raise ValueError(name + " must be finite and >= 0")
    predictions = {}
    for hypothesis in priors:
        by_action = predicted_outcomes[hypothesis]
        if set(by_action) != set(costs):
            raise ValueError("each hypothesis must predict every candidate action")
        predictions[hypothesis] = {
            action: _distribution(by_action[action], hypothesis + "/" + action)
            for action in costs
        }
    scored = []
    for action, cost in costs.items():
        outcome_space = set().union(*(predictions[h][action] for h in priors))
        marginal = {outcome: sum(priors[h] * predictions[h][action].get(outcome, 0.0)
                                 for h in priors) for outcome in outcome_space}
        conditional_entropy = sum(priors[h] * _entropy(list(predictions[h][action].values()))
                                  for h in priors)
        eig = max(0.0, _entropy(list(marginal.values())) - conditional_entropy)
        scored.append((action, eig, eig / cost, cost))
    scored.sort(key=lambda item: (-item[2], item[0]))
    eligible = [item for item in scored
                if item[3] <= float(remaining_budget)
                and item[2] >= float(min_information_gain_per_cost)]
    public_scores = tuple((a, eig, ratio) for a, eig, ratio, _ in scored)
    if not eligible:
        reason = ("budget_exhausted" if all(c > remaining_budget for _, _, _, c in scored)
                  else "below_information_threshold")
        return ChallengeChoice(None, 0.0, 0.0, 0.0, public_scores, reason)
    action, eig, ratio, cost = eligible[0]
    return ChallengeChoice(action, eig, ratio, cost, public_scores, "max_information_gain_per_cost")
