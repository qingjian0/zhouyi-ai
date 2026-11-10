"""Yinfu-inspired active observation policy (experimental baseline)."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    prior: float

@dataclass(frozen=True)
class Likelihood:
    outcome: str
    probability: float

@dataclass(frozen=True)
class Prediction:
    hypothesis_id: str
    likelihoods: tuple[Likelihood, ...]

@dataclass(frozen=True)
class ObservationAction:
    action_id: str
    channel: str
    cost: float
    temporal_fit: float
    predictions: tuple[Prediction, ...]

@dataclass(frozen=True)
class ObservationDecision:
    status: Literal["SELECTED", "NO_INFORMATION", "NO_ELIGIBLE_ACTION", "INVALID"]
    action_id: str | None
    information_gain_bits: float | None
    utility: float | None
    channel_novelty: float | None
    reason: str

def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def _entropy(weights: list[float]) -> float:
    total = sum(weights)
    if total <= 0 or any(not _finite(x) or x < 0 for x in weights):
        raise ValueError("weights must be finite, non-negative, and have positive mass")
    return -sum((p / total) * math.log2(p / total) for p in weights if p > 0)

def information_gain(hypotheses: tuple[Hypothesis, ...], action: ObservationAction) -> float:
    priors = {h.hypothesis_id: h.prior for h in hypotheses}
    predictions = {p.hypothesis_id: p for p in action.predictions}
    outcomes = sorted({x.outcome for p in action.predictions for x in p.likelihoods})
    prior_h = _entropy([h.prior for h in hypotheses])
    expected_h = 0.0
    for outcome in outcomes:
        joint = {}
        for hid, prior in priors.items():
            likelihood = next((x.probability for x in predictions[hid].likelihoods
                               if x.outcome == outcome), 0.0)
            joint[hid] = prior * likelihood
        mass = sum(joint.values())
        if mass > 0:
            expected_h += mass * _entropy(list(joint.values()))
    return max(0.0, prior_h - expected_h)

def select_observation(
    hypotheses: tuple[Hypothesis, ...],
    actions: tuple[ObservationAction, ...],
    *,
    available_channels: tuple[str, ...] = (),
    remaining_budget: float,
    diversity_weight: float = 0.25,
    min_temporal_fit: float = 0.0,
    tie_tolerance: float = 1e-12,
) -> ObservationDecision:
    """Rank by IG/cost, modulated by temporal fit and channel novelty."""
    try:
        if not hypotheses or not actions:
            raise ValueError("hypotheses and actions must be non-empty")
        ids = [h.hypothesis_id for h in hypotheses]
        if any(not x for x in ids) or len(ids) != len(set(ids)):
            raise ValueError("hypothesis IDs must be unique and non-empty")
        if any(not _finite(h.prior) or h.prior < 0 for h in hypotheses):
            raise ValueError("priors must be finite and non-negative")
        if not math.isclose(sum(h.prior for h in hypotheses), 1.0, abs_tol=1e-9):
            raise ValueError("priors must sum to one")
        if not _finite(remaining_budget) or remaining_budget < 0:
            raise ValueError("remaining_budget must be non-negative")
        if not _finite(diversity_weight) or diversity_weight < 0:
            raise ValueError("diversity_weight must be non-negative")
        if not _finite(min_temporal_fit) or not 0 <= min_temporal_fit <= 1:
            raise ValueError("min_temporal_fit must be in [0, 1]")
        if not _finite(tie_tolerance) or tie_tolerance < 0:
            raise ValueError("tie_tolerance must be non-negative")
        action_ids = [a.action_id for a in actions]
        if any(not x for x in action_ids) or len(action_ids) != len(set(action_ids)):
            raise ValueError("action IDs must be unique and non-empty")
        expected = set(ids)
        for action in actions:
            if not action.channel or not _finite(action.cost) or action.cost <= 0:
                raise ValueError("each action needs a channel and positive finite cost")
            if not _finite(action.temporal_fit) or not 0 <= action.temporal_fit <= 1:
                raise ValueError("temporal_fit must be in [0, 1]")
            pids = [p.hypothesis_id for p in action.predictions]
            if set(pids) != expected or len(pids) != len(expected):
                raise ValueError("each action must predict every hypothesis exactly once")
            for prediction in action.predictions:
                outcomes = [x.outcome for x in prediction.likelihoods]
                probs = [x.probability for x in prediction.likelihoods]
                if not outcomes or any(not x for x in outcomes) or len(outcomes) != len(set(outcomes)):
                    raise ValueError("outcome labels must be unique and non-empty")
                if any(not _finite(x) or x < 0 for x in probs) or not math.isclose(sum(probs), 1.0, abs_tol=1e-9):
                    raise ValueError("likelihoods must be non-negative and sum to one")
    except (TypeError, ValueError, AttributeError) as exc:
        return ObservationDecision("INVALID", None, None, None, None, str(exc))

    eligible = [a for a in actions
                if a.cost <= remaining_budget and a.temporal_fit >= min_temporal_fit]
    if not eligible:
        return ObservationDecision("NO_ELIGIBLE_ACTION", None, None, None, None,
                                   "No action satisfies budget and timing constraints")
    counts = {channel: available_channels.count(channel) for channel in set(available_channels)}
    scored = []
    for action in eligible:
        gain = information_gain(hypotheses, action)
        novelty = 1.0 / (1.0 + counts.get(action.channel, 0))
        utility = gain * action.temporal_fit * (1.0 + diversity_weight * novelty) / action.cost
        scored.append((action, gain, utility, novelty))
    if all(item[1] <= tie_tolerance for item in scored):
        return ObservationDecision("NO_INFORMATION", None, 0.0, 0.0, None,
                                   "No eligible action discriminates current hypotheses")
    best = max(item[2] for item in scored)
    tied = [item for item in scored if best - item[2] <= tie_tolerance]
    action, gain, utility, novelty = min(tied, key=lambda x: (x[0].cost, x[0].action_id))
    return ObservationDecision("SELECTED", action.action_id, gain, utility, novelty,
                               "Selected by information gain, timing, channel novelty, and cost")
