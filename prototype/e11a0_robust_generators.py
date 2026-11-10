"""E11-A0.1 robust generator arms.

The learner-facing object view contains only opaque IDs, environment IDs, and
observed attributes. Membership truth and schemas are held separately by the
benchmark episode and must only be consumed by an evaluator.
"""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RobustObjectView:
    object_id: str
    environment: str
    attributes: frozenset[str]


@dataclass(frozen=True)
class RobustEpisode:
    mode: str
    learner_objects: tuple[RobustObjectView, ...]
    query_objects: tuple[RobustObjectView, ...]
    truth: dict[str, frozenset[str]]
    hidden_schemas: dict[str, frozenset[str]]


SCHEMAS = {
    "concept-a": frozenset({"shared-00", "a-01", "a-02"}),
    "concept-b": frozenset({"shared-00", "b-01", "b-02"}),
    "concept-c": frozenset({"shared-00", "c-01", "c-02"}),
}
VOCABULARY = frozenset().union(*SCHEMAS.values())


def _observe(memberships: frozenset[str], rng: random.Random, *,
             missing_rate: float, false_positive_rate: float,
             mode: str, environment: str) -> frozenset[str]:
    observed: set[str] = set()
    for concept in memberships:
        for attribute in SCHEMAS[concept]:
            if rng.random() >= missing_rate:
                observed.add(attribute)
    for attribute in VOCABULARY:
        if attribute not in observed and rng.random() < false_positive_rate:
            observed.add(attribute)

    if mode == "nuisance-confounded":
        # The nuisance is predictive in environment 0 and reverses in 1.
        has_a = "concept-a" in memberships
        probability = (
            (0.85 if has_a else 0.15) if environment == "env-0"
            else (0.15 if has_a else 0.85)
        )
        if rng.random() < probability:
            observed.add("nuisance-77")
    return frozenset(observed)


def make_robust_episode(seed: int = 17, *, mode: str = "missing-noisy",
                        objects_per_split: int = 180,
                        missing_rate: float = 0.15,
                        false_positive_rate: float = 0.04) -> RobustEpisode:
    """Create object-disjoint observations with evaluator-only memberships.

    Modes:
      missing-noisy: missing defining attributes and false-positive attributes.
      shared-attribute: all concepts share a common attribute.
      nuisance-confounded: train/query environments reverse a spurious cue.
    """
    allowed = {"missing-noisy", "shared-attribute", "nuisance-confounded"}
    if mode not in allowed:
        raise ValueError(f"mode must be one of {sorted(allowed)}")
    if objects_per_split < 30:
        raise ValueError("objects_per_split must be at least 30")
    if not 0.0 <= missing_rate < 1.0:
        raise ValueError("missing_rate must be in [0, 1)")
    if not 0.0 <= false_positive_rate < 1.0:
        raise ValueError("false_positive_rate must be in [0, 1)")
    rng = random.Random(seed)
    learner: list[RobustObjectView] = []
    query: list[RobustObjectView] = []
    truth: dict[str, frozenset[str]] = {}

    for split_name, target, environment in (
        ("learner", learner, "env-0"),
        ("query", query, "env-1" if mode == "nuisance-confounded" else "env-0"),
    ):
        for index in range(objects_per_split):
            memberships = frozenset(
                concept for concept in SCHEMAS
                if rng.random() < {"concept-a": 0.34, "concept-b": 0.31,
                                   "concept-c": 0.28}[concept]
            )
            # Shared-attribute arm retains a common feature but removes the
            # independent missingness that would obscure the specific test.
            local_missing = 0.0 if mode == "shared-attribute" else missing_rate
            local_fp = 0.0 if mode == "shared-attribute" else false_positive_rate
            attributes = _observe(
                memberships, rng, missing_rate=local_missing,
                false_positive_rate=local_fp, mode=mode, environment=environment,
            )
            object_id = f"{split_name}-{index:05d}"
            target.append(RobustObjectView(object_id, environment, attributes))
            truth[object_id] = memberships

    return RobustEpisode(mode, tuple(learner), tuple(query), truth, dict(SCHEMAS))
