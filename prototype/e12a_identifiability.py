"""E12-A0: tiny identifiability and leakage baseline.

Transparent finite-grammar protocol check, not a learned model.
The learner receives only LearnerView; evaluator truth is environment-side.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, replace
from typing import Literal

PrimitiveId = Literal["ge2", "eq2"]
PRIMITIVES: tuple[PrimitiveId, ...] = ("ge2", "eq2")


@dataclass(frozen=True)
class Observation:
    value: int
    label: int


@dataclass(frozen=True)
class LearnerView:
    observations: tuple[Observation, ...]
    allowed_probe_values: tuple[int, ...] = ()


@dataclass(frozen=True)
class EvaluatorTruth:
    episode_id: str
    primitive_id: PrimitiveId
    domain_values: tuple[int, ...]


def evaluate_primitive(primitive_id: PrimitiveId, value: int) -> int:
    if primitive_id == "ge2":
        return int(value >= 2)
    if primitive_id == "eq2":
        return int(value == 2)
    raise ValueError(f"unknown primitive: {primitive_id}")


def make_episode(family: str, seed: int = 7) -> tuple[LearnerView, EvaluatorTruth]:
    """Return separate learner/evaluator payloads for a controlled world."""
    rng = random.Random(seed)
    target: PrimitiveId = rng.choice(PRIMITIVES)

    if family == "identifiable":
        support_values, domain, probes = (0, 2, 3), (0, 1, 2, 3), ()
    elif family == "ambiguous":
        support_values, domain, probes = (0, 2), (0, 1, 2, 3), ()
    elif family == "intervention_pending":
        support_values, domain, probes = (0, 2), (0, 1, 2, 3), (3,)
    elif family == "unobservable":
        support_values, domain, probes = (0, 2), (0, 2), ()
    elif family == "inconsistent":
        support_values, domain, probes = (0, 1, 2), (0, 1, 2, 3), ()
    else:
        raise ValueError(f"unknown family: {family}")

    observations = tuple(
        Observation(value, evaluate_primitive(target, value))
        for value in support_values
    )
    if family == "inconsistent":
        observations += (Observation(1, 1),)

    return (
        LearnerView(observations, probes),
        EvaluatorTruth(f"{family}-{seed}", target, domain),
    )


def infer(view: LearnerView, candidate_budget: int | None = None) -> dict:
    """Infer from learner-visible observations with explicit budget accounting."""
    if candidate_budget is not None and candidate_budget < 0:
        raise ValueError("candidate_budget cannot be negative")

    checked = []
    exhausted = False
    for primitive_id in PRIMITIVES:
        if candidate_budget is not None and len(checked) >= candidate_budget:
            exhausted = True
            break
        checked.append(primitive_id)

    # An incomplete search cannot establish uniqueness or inconsistency.
    if exhausted:
        return {
            "status": "BUDGET_EXHAUSTED",
            "candidates": (),
            "selected": None,
            "evaluated_candidates": len(checked),
            "remaining_candidates": len(PRIMITIVES) - len(checked),
        }

    candidates = tuple(
        primitive_id for primitive_id in checked
        if all(
            evaluate_primitive(primitive_id, obs.value) == obs.label
            for obs in view.observations
        )
    )
    if len(candidates) == 1:
        status, selected = "IDENTIFIABLE", candidates[0]
    elif len(candidates) > 1:
        status, selected = "AMBIGUOUS", None
    else:
        status, selected = "INCONSISTENT", None

    return {
        "status": status,
        "candidates": candidates,
        "selected": selected,
        "evaluated_candidates": len(checked),
        "remaining_candidates": 0,
    }


def apply_probe(
    view: LearnerView, truth: EvaluatorTruth, value: int
) -> LearnerView:
    """Environment-side action; truth is not passed to infer()."""
    if value not in view.allowed_probe_values:
        raise ValueError("probe is not permitted by this learner view")
    if value not in truth.domain_values:
        raise ValueError("probe value is outside the environment domain")
    observation = Observation(
        value, evaluate_primitive(truth.primitive_id, value)
    )
    return replace(
        view,
        observations=view.observations + (observation,),
        allowed_probe_values=tuple(
            item for item in view.allowed_probe_values if item != value
        ),
    )


def run_suite(
    seeds: int = 20,
    start_seed: int = 7,
    candidate_budget: int | None = None,
) -> dict:
    if seeds <= 0:
        raise ValueError("seeds must be positive")

    families = (
        "identifiable", "ambiguous", "intervention_pending",
        "unobservable", "inconsistent",
    )
    counts = {family: {} for family in families}
    probe_recovery = 0
    probe_total = 0
    episodes = []

    for family in families:
        for seed in range(start_seed, start_seed + seeds):
            view, truth = make_episode(family, seed)
            result = infer(view, candidate_budget=candidate_budget)
            counts[family][result["status"]] = (
                counts[family].get(result["status"], 0) + 1
            )
            episode = {
                "family": family,
                "seed": seed,
                "status_before_probe": result["status"],
                "candidates_before_probe": list(result["candidates"]),
                "evaluated_candidates": result["evaluated_candidates"],
                "remaining_candidates": result["remaining_candidates"],
            }

            if family == "intervention_pending":
                probe_total += 1
                updated = apply_probe(view, truth, 3)
                after = infer(updated, candidate_budget=candidate_budget)
                recovered = (
                    after["status"] == "IDENTIFIABLE"
                    and after["selected"] == truth.primitive_id
                )
                probe_recovery += int(recovered)
                episode.update({
                    "status_after_probe": after["status"],
                    "candidates_after_probe": list(after["candidates"]),
                    "probe_recovered": recovered,
                    "probe_evaluated_candidates": after["evaluated_candidates"],
                    "probe_remaining_candidates": after["remaining_candidates"],
                })
            episodes.append(episode)

    return {
        "experiment": "E12-A0-identifiability-and-leakage-baseline",
        "seeds": seeds,
        "start_seed": start_seed,
        "candidate_budget": candidate_budget,
        "grammar": list(PRIMITIVES),
        "status_counts": counts,
        "intervention_probe_recovery": (
            probe_recovery / probe_total if probe_total else None
        ),
        "intervention_probe_episodes": probe_total,
        "episodes": episodes,
        "scope": (
            "Finite synthetic two-predicate grammar only. This is a protocol "
            "sanity check, not open-world primitive induction or causal discovery."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--candidate-budget", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_suite(
        args.seeds, args.start_seed, args.candidate_budget
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
