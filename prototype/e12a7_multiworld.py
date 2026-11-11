"""E12-A7: multi-world mechanism identification and structural analogy benchmark.

The first A7 slice is an executable synthetic protocol, not an open-world
learner. It uses a declared finite mechanism class to test identifiability,
intervention value, noisy/missing observations, context dependence, delayed
switches, and safe transfer abstention.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Protocol, Sequence


class WorldFamily(Protocol):
    """Minimal generator contract for controlled world families."""

    name: str

    def sample(self, *, intervention: bool, x: int, context: int,
               time: int) -> "Observation": ...


@dataclass(frozen=True)
class Observation:
    world_family: str
    intervention: bool
    x: int
    context: int
    time: int
    y: int | None
    surface_tag: str = "influence"
    noisy: bool = False


@dataclass(frozen=True)
class SyntheticWorld:
    name: str
    mechanism: str
    missing_every: int = 0
    noise_every: int = 0
    switch_time: int = 2

    def sample(self, *, intervention: bool, x: int, context: int,
               time: int) -> Observation:
        latent = (x + context) % 3
        if self.mechanism == "direct":
            y = x if intervention else x
        elif self.mechanism == "inverse":
            y = (-x) % 3
        elif self.mechanism == "context_gate":
            y = x if context == 1 else 0
        elif self.mechanism == "confounded":
            # Observationally mimics direct influence; intervention breaks it.
            y = 0 if intervention else x
        elif self.mechanism == "delayed_switch":
            y = x if time < self.switch_time else (-x) % 3
        elif self.mechanism == "null":
            y = 0
        else:
            raise ValueError(f"unknown mechanism: {self.mechanism}")

        noisy = self.noise_every > 0 and (x + context + time) % self.noise_every == 0
        if noisy:
            y = (y + 1) % 3
        missing = self.missing_every > 0 and (x + 2 * context + time) % self.missing_every == 0
        return Observation(
            world_family=self.name, intervention=intervention, x=x,
            context=context, time=time, y=None if missing else y,
            noisy=noisy, surface_tag="influence",
        )


MECHANISMS = ("direct", "inverse", "context_gate", "confounded",
              "delayed_switch", "null")


def make_worlds() -> tuple[SyntheticWorld, ...]:
    return (
        SyntheticWorld("direct_world", "direct"),
        SyntheticWorld("inverse_world", "inverse"),
        SyntheticWorld("context_world", "context_gate"),
        SyntheticWorld("confounded_world", "confounded"),
        SyntheticWorld("switch_world", "delayed_switch"),
        SyntheticWorld("noisy_missing_world", "direct", missing_every=5, noise_every=7),
        SyntheticWorld("null_world", "null"),
    )


def collect(world: WorldFamily, *, interventions: bool = True) -> tuple[Observation, ...]:
    rows = []
    for time in range(4):
        for context in range(2):
            for x in range(3):
                for do_x in ((False, True) if interventions else (False,)):
                    rows.append(world.sample(
                        intervention=do_x, x=x, context=context, time=time
                    ))
    return tuple(rows)


def predict(mechanism: str, row: Observation) -> int:
    x, c, t = row.x, row.context, row.time
    if mechanism == "direct":
        return x
    if mechanism == "inverse":
        return (-x) % 3
    if mechanism == "context_gate":
        return x if c == 1 else 0
    if mechanism == "confounded":
        return 0 if row.intervention else x
    if mechanism == "delayed_switch":
        return x if t < 2 else (-x) % 3
    if mechanism == "null":
        return 0
    raise ValueError(f"unknown mechanism: {mechanism}")


def identify(observations: Sequence[Observation], *, max_errors: int = 2
             ) -> dict:
    visible = [row for row in observations if row.y is not None]
    intervention_count = sum(row.intervention for row in visible)
    if not visible:
        return {"status": "abstain", "reason": "no_visible_labels",
                "candidates": [], "best_errors": None}
    scores = {
        mechanism: sum(predict(mechanism, row) != row.y for row in visible)
        for mechanism in MECHANISMS
    }
    best = min(scores.values())
    winners = sorted(name for name, score in scores.items() if score == best)
    if best > max_errors:
        status, reason = "abstain", "no_candidate_within_error_budget"
    elif len(winners) != 1:
        status, reason = "abstain", "observationally_ambiguous"
    elif intervention_count == 0 and winners[0] in {"direct", "confounded"}:
        status, reason = "abstain", "intervention_needed_to_separate_cause_from_confounding"
    else:
        status, reason = "identified", "unique_best_mechanism"
    return {
        "status": status, "reason": reason, "candidates": winners,
        "best_errors": best, "scores": scores,
        "visible_count": len(visible), "intervention_count": intervention_count,
    }


def transfer(source: Sequence[Observation], target: Sequence[Observation]) -> dict:
    src, dst = identify(source), identify(target)
    if src["status"] != "identified" or dst["status"] != "identified":
        return {"decision": "abstain", "reason": "source_or_target_not_identified",
                "source": src, "target": dst}
    if src["candidates"][0] != dst["candidates"][0]:
        return {"decision": "reject_transfer", "reason": "mechanisms_not_isomorphic",
                "source": src["candidates"][0], "target": dst["candidates"][0]}
    return {"decision": "transfer", "reason": "matching_structural_mechanism",
            "mechanism": src["candidates"][0]}


def run_benchmark() -> dict:
    worlds = make_worlds()
    full = {w.name: collect(w, interventions=True) for w in worlds}
    observational = {w.name: collect(w, interventions=False) for w in worlds}
    pairs = {
        "direct_to_direct": transfer(full["direct_world"], full["direct_world"]),
        "direct_to_inverse": transfer(full["direct_world"], full["inverse_world"]),
        "direct_to_confounded_without_intervention": transfer(
            observational["direct_world"], observational["confounded_world"]),
        "direct_to_context": transfer(full["direct_world"], full["context_world"]),
    }
    identifications = {name: identify(rows) for name, rows in full.items()}
    return {
        "task": "E12A7_multiworld_structural_analogy",
        "world_count": len(worlds),
        "mechanism_class": list(MECHANISMS),
        "identifications": identifications,
        "transfer_cases": pairs,
        "surface_tag_collision_count": len({
            row.surface_tag for rows in full.values() for row in rows
        }),
        "limitations": [
            "Finite declared mechanism class; not open-world discovery.",
            "Synthetic deterministic worlds except explicitly configured noise/missingness.",
            "Exact symbolic hypothesis scoring; not a trained neural learner.",
            "Structural analogy is tested on controlled mechanisms, not natural-language semantics.",
            "A future slice must compare no-prior, random, traditional-symbolic, shuffled, anti-aligned, and data-learned priors.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_benchmark()
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else result)


if __name__ == "__main__":
    main()
