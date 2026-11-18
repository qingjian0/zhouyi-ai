"""Dynamic Yixiang baseline: compare state transitions, not static snapshots.

Inputs are explicit annotations. This module does not infer hidden states,
causes, or temporal laws from raw observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DYNAMIC_DIMENSIONS = frozenset({
    "morphology", "attribute", "function", "relation", "process",
    "spatiotemporal", "potential", "integrated",
})


@dataclass(frozen=True)
class StateObservation:
    observation_id: str
    entity_id: str
    domain: str
    step: int
    state: Mapping[str, str]
    feature_dimensions: Mapping[str, str]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class TransitionPattern:
    pattern_id: str
    version: int
    dimensions: tuple[str, ...]
    transitions: Mapping[str, tuple[str, str]]
    feature_dimensions: Mapping[str, str]
    variable_features: tuple[str, ...]
    transition_support_ids: Mapping[str, tuple[str, ...]]
    evidence_refs: tuple[str, ...]
    scope: str


@dataclass(frozen=True)
class TransitionAssessment:
    accepted: bool
    score: float
    matched: tuple[str, ...]
    missing: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _validate_state(item: StateObservation) -> None:
    if not isinstance(item, StateObservation):
        raise ValueError("states must be StateObservation instances")
    if any(not isinstance(value, str) or not value.strip()
           for value in (item.observation_id, item.entity_id, item.domain)):
        raise ValueError("observation_id, entity_id, and domain are required")
    if type(item.step) is not int:
        raise ValueError("step must be an integer")
    if not isinstance(item.state, Mapping) or not item.state:
        raise ValueError("state must contain features")
    if set(item.state) != set(item.feature_dimensions):
        raise ValueError("every state feature needs exactly one dimension")
    if any(not isinstance(k, str) or not k.strip()
           or not isinstance(v, str) or not v.strip()
           for k, v in item.state.items()):
        raise ValueError("state feature keys and values must be non-empty strings")
    if any(d not in DYNAMIC_DIMENSIONS for d in item.feature_dimensions.values()):
        raise ValueError("unknown feature dimension")
    if not isinstance(item.evidence_refs, tuple) or any(
        not isinstance(ref, str) or not ref.strip() for ref in item.evidence_refs
    ):
        raise ValueError("evidence_refs must be a tuple of non-empty strings")


def derive_transition_pattern(
    trajectories: tuple[tuple[StateObservation, ...], ...],
    *,
    pattern_id: str,
    dimensions: tuple[str, ...],
    scope: str,
    min_support_ratio: float = 1.0,
) -> TransitionPattern:
    """Derive recurring directed feature changes across independent trajectories.

    Each trajectory contributes at most one vote per feature-transition pair,
    preventing longer trajectories from dominating the support ratio.
    """
    if not trajectories or not pattern_id.strip() or not scope.strip():
        raise ValueError("trajectories, pattern_id, and scope are required")
    if not dimensions or len(set(dimensions)) != len(dimensions) or set(dimensions) - DYNAMIC_DIMENSIONS:
        raise ValueError("dimensions must be non-empty, unique, and known")
    if isinstance(min_support_ratio, bool) or not isinstance(min_support_ratio, (int, float)) or not 0 < min_support_ratio <= 1:
        raise ValueError("min_support_ratio must be in (0, 1]")

    trajectory_ids = []
    votes: dict[str, dict[tuple[str, str], set[str]]] = {}
    feature_dimensions: dict[str, str] = {}
    evidence = set()
    seen_observation_ids = set()

    for index, trajectory in enumerate(trajectories):
        if len(trajectory) < 2:
            raise ValueError("each trajectory must contain at least two states")
        for item in trajectory:
            _validate_state(item)
            if item.observation_id in seen_observation_ids:
                raise ValueError("observation ids must be globally unique")
            seen_observation_ids.add(item.observation_id)
        if len({item.entity_id for item in trajectory}) != 1:
            raise ValueError("a trajectory must follow one entity")
        if len({item.domain for item in trajectory}) != 1:
            raise ValueError("a trajectory must stay within one domain")
        if any(a.step >= b.step for a, b in zip(trajectory, trajectory[1:])):
            raise ValueError("trajectory steps must be strictly increasing")

        trajectory_id = f"trajectory-{index + 1}"
        trajectory_ids.append(trajectory_id)
        evidence.update(ref for item in trajectory for ref in item.evidence_refs)
        local_pairs: dict[str, set[tuple[str, str]]] = {}
        for before, after in zip(trajectory, trajectory[1:]):
            common = set(before.state) & set(after.state)
            for key in common:
                dim = before.feature_dimensions[key]
                if dim != after.feature_dimensions[key]:
                    raise ValueError(f"feature {key!r} changes dimension")
                if dim not in dimensions or before.state[key] == after.state[key]:
                    continue
                prior = feature_dimensions.setdefault(key, dim)
                if prior != dim:
                    raise ValueError(f"feature {key!r} has conflicting dimensions")
                local_pairs.setdefault(key, set()).add((before.state[key], after.state[key]))
        for key, pairs in local_pairs.items():
            for pair in pairs:
                votes.setdefault(key, {}).setdefault(pair, set()).add(trajectory_id)

    invariants = {}
    transition_support_ids = {}
    for key, pair_votes in votes.items():
        ranked = sorted(
            ((len(ids), pair) for pair, ids in pair_votes.items()),
            key=lambda item: (-item[0], item[1]),
        )
        if ranked and ranked[0][0] / len(trajectories) >= min_support_ratio:
            if len(ranked) == 1 or ranked[0][0] > ranked[1][0]:
                invariants[key] = ranked[0][1]
                transition_support_ids[key] = tuple(sorted(pair_votes[ranked[0][1]]))

    selected_keys = set(feature_dimensions)
    return TransitionPattern(
        pattern_id=pattern_id,
        version=1,
        dimensions=dimensions,
        transitions=invariants,
        feature_dimensions=feature_dimensions,
        variable_features=tuple(sorted(selected_keys - set(invariants))),
        transition_support_ids=transition_support_ids,
        evidence_refs=tuple(sorted(evidence)),
        scope=scope,
    )


def classify_transition(
    pattern: TransitionPattern,
    before: StateObservation,
    after: StateObservation,
    *,
    min_score: float = 1.0,
) -> TransitionAssessment:
    """Assess one directed state change against a transition pattern."""
    _validate_state(before)
    _validate_state(after)
    if before.entity_id != after.entity_id or before.domain != after.domain:
        raise ValueError("before and after must describe the same entity and domain")
    if before.step >= after.step:
        raise ValueError("after.step must be greater than before.step")
    if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not 0 <= min_score <= 1:
        raise ValueError("min_score must be in [0, 1]")

    matched = []
    for key, expected in pattern.transitions.items():
        if (before.state.get(key), after.state.get(key)) == expected and (
            before.feature_dimensions.get(key) == pattern.feature_dimensions.get(key)
            and after.feature_dimensions.get(key) == pattern.feature_dimensions.get(key)
        ):
            matched.append(key)
    missing = tuple(sorted(set(pattern.transitions) - set(matched)))
    score = len(matched) / len(pattern.transitions) if pattern.transitions else 0.0
    reasons = []
    if not pattern.transitions:
        reasons.append("PATTERN_HAS_NO_TRANSITIONS")
    if score < min_score:
        reasons.append("TRANSITION_MISMATCH")
    if not before.evidence_refs or not after.evidence_refs:
        reasons.append("MISSING_TRANSITION_EVIDENCE")
    return TransitionAssessment(
        accepted=not reasons,
        score=score,
        matched=tuple(sorted(matched)),
        missing=missing,
        reason_codes=tuple(reasons),
    )
