"""E12-A0: tiny identifiability and leakage baseline.

This is a transparent finite-grammar protocol check, not a learned model.
The learner receives only a LearnerView. EvaluatorTruth is kept in a
separate object and is used only by the environment/evaluator.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, replace
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
        # Add a contradictory duplicate observation at a point where both
        # candidate predicates return zero. The evaluator truth remains private.
        observations += (Observation(1, 1),)

    view = LearnerView(observations, probes)
    truth = EvaluatorTruth(f"{family}-{seed}", target, domain)
    return view, truth


def consistent_primitives(view: LearnerView) -> tuple[PrimitiveId, ...]:
    matches = []
    for primitive_id in PRIMITIVES:
        if all(
            evaluate_primitive(primitive_id, obs.value) == obs.label
            for obs in view.observations
        ):
            matches.append(primitive_id)
    return tuple(matches)


def infer(view: LearnerView, candidate_budget: int | None = None) -> dict:
    """Infer only from learner-visible observations; never accepts evaluator truth."""
    if candidate_budget is not None and candidate_budget < len(PRIMITIVES):
        return {
            "status": "BUDGET_EXHAUSTED",
            "candidates": (),
            "selected": None,
        }
    candidates = consistent_primitives(view)
    if len(candidates) == 1:
        status, selected = "IDENTIFIABLE", candidates[0]
    elif len(candidates) > 1:
        status, selected = "AMBIGUOUS", None
    else:
        status, selected = "INCONSISTENT", None
    return {"status": status, "candidates": candidates, "selected": selected}


def apply_probe(
    view: LearnerView, truth: EvaluatorTruth, value: int
) -> LearnerView:
    """Environment-side action. Truth is not passed to the learner's infer()."""
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


def run_suite(seeds: int = 20, start_seed: int = 7) -> dict:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    families = ("identifiable", "ambiguous", "intervention_pending",
                "unobservable", "inconsistent")
    counts = {family: {} for family in families}
    probe_recovery = 0
    probe_total = 0

    for family in families:
        for seed in range(start_seed, start_seed + seeds):
            view, truth = make_episode(family, seed)
            result = infer(view)
            counts[family][result["status"]] = (
                counts[family].get(result["status"], 0) + 1
            )
            if family == "intervention_pending":
                probe_total += 1
                updated = apply_probe(view, truth, 3)
                after = infer(updated)
                probe_recovery += int(
                    after["status"] == "IDENTIFIABLE"
                    and after["selected"] == truth.primitive_id
                )

    return {
        "experiment": "E12-A0-identifiability-and-leakage-baseline",
        "seeds": seeds,
        "start_seed": start_seed,
        "grammar": list(PRIMITIVES),
        "status_counts": counts,
        "intervention_probe_recovery": (
            probe_recovery / probe_total if probe_total else None
        ),
        "intervention_probe_episodes": probe_total,
        "scope": (
            "Finite synthetic two-predicate grammar only. This is a protocol "
            "sanity check, not open-world primitive induction or causal discovery."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_suite(args.seeds, args.start_seed)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
