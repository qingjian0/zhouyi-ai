"""E12-A8: prequential active intervention selection over E12-A7 worlds.

A finite-hypothesis experimental-design baseline. The learner chooses an
intervention from predicted outcomes, commits before the environment is queried,
then updates only after the environment reveals the outcome.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from typing import Mapping, Sequence

from prototype.e12a7_multiworld import (
    MECHANISMS, Observation, SyntheticWorld, make_worlds, predict,
)
from prototype.e12a2_active_measurement_selector import (
    select_measurement, update_weights,
)


@dataclass(frozen=True)
class ExperimentAction:
    action_id: str
    intervention: bool
    x: int
    context: int
    time: int
    cost: float


def make_actions(*, include_interventions: bool = True) -> tuple[ExperimentAction, ...]:
    actions = []
    interventions = (False, True) if include_interventions else (False,)
    for do_x in interventions:
        for time in range(4):
            for context in range(2):
                for x in range(3):
                    cost = 2.0 if do_x else 1.0
                    action_id = f"do{int(do_x)}-t{time}-c{context}-x{x}"
                    actions.append(ExperimentAction(
                        action_id, do_x, x, context, time, cost
                    ))
    return tuple(actions)


def _normalize(prior: Mapping[str, float]) -> dict[str, float]:
    if not prior or set(prior) - set(MECHANISMS):
        raise ValueError("prior must contain known mechanism hypotheses")
    if any(isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or v < 0 for v in prior.values()):
        raise ValueError("prior weights must be finite and non-negative")
    total = sum(prior.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("prior must have positive mass")
    return {key: value / total for key, value in prior.items()}


def _predicted_outcome(hypothesis: str, action: ExperimentAction) -> int:
    observed_x = (action.x if action.intervention
                  else (action.x + action.context + action.time) % 3)
    row = Observation(
        world_family="candidate-world",
        intervention=action.intervention,
        x=observed_x,
        context=action.context,
        time=action.time,
        y=None,
    )
    return predict(hypothesis, row)


def likelihoods(
    prior: Mapping[str, float],
    action: ExperimentAction,
    *,
    noise_probability: float = 0.02,
) -> dict[str, dict[str, float]]:
    """Return P(y | mechanism, action) under a symmetric ternary noise channel."""
    _normalize(prior)
    if (isinstance(noise_probability, bool)
            or not isinstance(noise_probability, (int, float))
            or not math.isfinite(noise_probability)
            or not 0 <= noise_probability < 1):
        raise ValueError("noise_probability must be finite and in [0, 1)")
    result = {}
    for hypothesis in prior:
        predicted = _predicted_outcome(hypothesis, action)
        result[hypothesis] = {
            str(outcome): (1.0 - noise_probability if outcome == predicted
                           else noise_probability / 2.0)
            for outcome in range(3)
        }
    return result


def select_action(
    prior: Mapping[str, float],
    actions: Sequence[ExperimentAction],
    remaining_budget: float,
    *,
    noise_probability: float = 0.02,
) -> dict:
    """Adapt world-specific probes to the existing E12-A2 EIG selector."""
    prior = _normalize(prior)
    if (isinstance(remaining_budget, bool)
            or not isinstance(remaining_budget, (int, float))
            or not math.isfinite(remaining_budget) or remaining_budget < 0):
        raise ValueError("remaining_budget must be finite and non-negative")
    ids = [a.action_id for a in actions]
    if len(ids) != len(set(ids)):
        raise ValueError("action IDs must be unique")
    for action in actions:
        if (not action.action_id or isinstance(action.cost, bool)
                or not isinstance(action.cost, (int, float))
                or not math.isfinite(action.cost) or action.cost <= 0):
            raise ValueError("actions need IDs and positive finite costs")
    predictions = {
        action.action_id: likelihoods(
            prior, action, noise_probability=noise_probability
        )
        for action in actions
    }
    costs = {action.action_id: action.cost for action in actions}
    selected = select_measurement(prior, predictions, costs, remaining_budget)
    return {
        "status": selected["status"],
        "selected": selected.get("selected_action"),
        "gain_bits": selected.get("expected_information_gain_bits"),
        "utility": selected.get("utility"),
        "evaluated": selected.get("evaluated", []),
    }


class PrequentialExperimentLedger:
    """Append-only action commit / environment reveal / posterior update log."""

    def __init__(
        self,
        prior: Mapping[str, float],
        *,
        noise_probability: float = 0.02,
    ) -> None:
        self.posterior = _normalize(prior)
        self.noise_probability = noise_probability
        self.commits: dict[str, dict] = {}
        self.events: list[dict] = []
        self.spent = 0.0

    def commit(self, action: ExperimentAction) -> None:
        if (not isinstance(action.action_id, str) or not action.action_id
                or isinstance(action.cost, bool) or not isinstance(action.cost, (int, float))
                or not math.isfinite(action.cost) or action.cost <= 0):
            raise ValueError("committed action must have an ID and positive finite cost")
        if action.action_id in self.commits:
            raise ValueError("action already committed")
        table = likelihoods(
            self.posterior, action, noise_probability=self.noise_probability
        )
        self.commits[action.action_id] = {
            "action": action,
            "prior": dict(self.posterior),
            "likelihoods": table,
        }
        self.spent += action.cost
        self.events.append({
            "phase": "COMMIT",
            "action_id": action.action_id,
            "prior": dict(self.posterior),
            "predictions": table,
        })

    def reveal(self, action_id: str, outcome: int | None) -> dict:
        if action_id not in self.commits:
            raise ValueError("reveal requires a prior action commit")
        if any(event.get("action_id") == action_id and event["phase"] == "REVEAL"
               for event in self.events):
            raise ValueError("action outcome can only be revealed once")
        if outcome is None:
            self.events.append({
                "phase": "REVEAL", "action_id": action_id,
                "outcome": None, "status": "MISSING",
                "posterior": dict(self.posterior),
            })
            return {"status": "MISSING", "posterior": dict(self.posterior)}
        if isinstance(outcome, bool) or not isinstance(outcome, int) or outcome not in (0, 1, 2):
            raise ValueError("outcome must be 0, 1, 2, or None")
        commit = self.commits[action_id]
        try:
            self.posterior = update_weights(
                commit["prior"], commit["likelihoods"], str(outcome)
            )
            result = {"status": "UPDATED", "posterior": dict(self.posterior)}
        except ValueError:
            result = {"status": "INCONSISTENT", "posterior": None}
        self.events.append({
            "phase": "REVEAL", "action_id": action_id,
            "outcome": outcome, **result,
        })
        return result


def run_episode(
    world: SyntheticWorld,
    *,
    policy: str = "active",
    include_interventions: bool = True,
    budget: float = 12.0,
    max_steps: int = 12,
    confidence_threshold: float = 0.95,
    noise_probability: float = 0.02,
    seed: int = 0,
) -> dict:
    """Run a learner-facing episode; true mechanism is not returned to learner."""
    if policy not in {"active", "random", "fixed"}:
        raise ValueError("policy must be active, random, or fixed")
    if (isinstance(budget, bool) or not isinstance(budget, (int, float))
            or not math.isfinite(budget) or budget < 0):
        raise ValueError("budget must be finite and non-negative")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 0:
        raise ValueError("max_steps must be a non-negative integer")
    if (isinstance(confidence_threshold, bool)
            or not isinstance(confidence_threshold, (int, float))
            or not math.isfinite(confidence_threshold)
            or not 0 < confidence_threshold <= 1):
        raise ValueError("confidence_threshold must be finite and in (0, 1]")
    actions = list(make_actions(include_interventions=include_interventions))
    remaining = {action.action_id: action for action in actions}
    ledger = PrequentialExperimentLedger(
        {mechanism: 1.0 for mechanism in MECHANISMS},
        noise_probability=noise_probability,
    )
    rng = random.Random(seed)
    for _ in range(max_steps):
        affordable = [a for a in remaining.values() if a.cost <= budget - ledger.spent]
        if not affordable:
            break
        if policy == "active":
            choice = select_action(
                ledger.posterior, affordable, budget - ledger.spent,
                noise_probability=noise_probability,
            )
            if choice["status"] != "SELECTED":
                break
            action = remaining[choice["selected"]]
        elif policy == "random":
            action = rng.choice(sorted(affordable, key=lambda a: a.action_id))
        else:
            action = min(affordable, key=lambda a: a.action_id)

        # Crucial ordering: freeze the model's prediction before querying world.
        ledger.commit(action)
        observation = world.sample(
            intervention=action.intervention,
            x=action.x,
            context=action.context,
            time=action.time,
        )
        ledger.reveal(action.action_id, observation.y)
        del remaining[action.action_id]
        if max(ledger.posterior.values()) >= confidence_threshold:
            break

    return {
        "policy": policy,
        "posterior": dict(ledger.posterior),
        "confidence": max(ledger.posterior.values()),
        "spent": ledger.spent,
        "steps": sum(event["phase"] == "COMMIT" for event in ledger.events),
        "events": ledger.events,
    }


def evaluate_policy(
    worlds: Sequence[SyntheticWorld],
    *,
    policies: Sequence[str] = ("active", "random", "fixed"),
    seeds: Sequence[int] = (0, 1, 2, 3, 4),
    include_interventions: bool = True,
    budget: float = 12.0,
) -> dict:
    """Evaluator-only wrapper. Truth is accessed after learner episodes finish."""
    results = {}
    for policy in policies:
        episodes = []
        for world in worlds:
            for seed in seeds:
                learner = run_episode(
                    world, policy=policy, include_interventions=include_interventions,
                    budget=budget, seed=seed,
                )
                # Evaluator truth is read only after the learner episode is frozen.
                predicted = max(learner["posterior"], key=learner["posterior"].get)
                episodes.append({
                    "world": world.name,
                    "truth": world.mechanism,
                    "predicted": predicted,
                    "correct": predicted == world.mechanism,
                    "confidence": learner["confidence"],
                    "spent": learner["spent"],
                    "steps": learner["steps"],
                })
        results[policy] = {
            "episodes": episodes,
            "accuracy": sum(e["correct"] for e in episodes) / len(episodes),
            "mean_cost": sum(e["spent"] for e in episodes) / len(episodes),
            "mean_steps": sum(e["steps"] for e in episodes) / len(episodes),
            "high_confidence_error_rate": (
                sum(not e["correct"] for e in episodes if e["confidence"] >= 0.95)
                / max(1, sum(e["confidence"] >= 0.95 for e in episodes))
            ),
        }
    return {
        "task": "E12A8_active_multiworld_experiment_loop",
        "world_count": len(worlds),
        "seeds": list(seeds),
        "include_interventions": include_interventions,
        "budget": budget,
        "policies": results,
        "limitations": [
            "Finite known mechanism class; no open-world hypothesis invention.",
            "Synthetic world and shared process; evaluator separation is logical, not a sandbox.",
            "Bayesian likelihood assumes a symmetric ternary noise channel.",
            "The active policy optimizes one-step expected information gain per cost, not long-horizon value.",
            "No Yijing/Taixuan prior is included in this first slice.",
        ],
    }

def run_benchmark(*, seeds: Sequence[int] = tuple(range(20)), budget: float = 12.0) -> dict:
    """Run matched active/random/fixed policies across all E12-A7 worlds."""
    return evaluate_policy(
        make_worlds(),
        policies=("active", "random", "fixed"),
        seeds=seeds,
        include_interventions=True,
        budget=budget,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--budget", type=float, default=12.0)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")
    result = run_benchmark(seeds=tuple(range(args.seeds)), budget=args.budget)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)


if __name__ == "__main__":
    main()
