"""Evidence-traceable candidate-image abstraction and revision baseline.

This symbolic prototype consumes already annotated observations. It does not
parse classical Chinese, extract features from raw perception, or learn causal
laws. Feature dimensions are explicit so unrelated dimensions are not mixed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DIMENSIONS = frozenset({
    "morphology", "attribute", "function", "relation", "process",
    "spatiotemporal", "potential", "integrated",
})


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str
    dimension: str = "relation"


@dataclass(frozen=True)
class Observation:
    observation_id: str
    domain: str
    features: Mapping[str, str]
    relations: tuple[Edge, ...]
    context: Mapping[str, str]
    evidence_refs: tuple[str, ...]
    feature_dimensions: Mapping[str, str]


@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    version: int
    dimensions: tuple[str, ...]
    invariant_features: Mapping[str, str]
    feature_dimensions: Mapping[str, str]
    variable_features: tuple[str, ...]
    excluded_patterns: tuple[tuple[tuple[str, str], ...], ...]
    support_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    scope: str


@dataclass(frozen=True)
class Membership:
    observation_id: str
    accepted: bool
    score: float
    matched: tuple[str, ...]
    missing: tuple[str, ...]
    excluded: tuple[str, ...]
    reason_codes: tuple[str, ...]


def _validate_observation(obs: Observation) -> None:
    if not isinstance(obs, Observation):
        raise ValueError("observation must be an Observation")
    if (not isinstance(obs.observation_id, str) or not obs.observation_id.strip()
            or not isinstance(obs.domain, str) or not obs.domain.strip()):
        raise ValueError("observation_id and domain are required")
    if not isinstance(obs.features, Mapping) or not obs.features:
        raise ValueError("observation must contain at least one feature")
    if any(not isinstance(k, str) or not k.strip()
           or not isinstance(v, str) or not v.strip()
           for k, v in obs.features.items()):
        raise ValueError("feature keys and values must be non-empty strings")
    if not isinstance(obs.feature_dimensions, Mapping):
        raise ValueError("feature_dimensions must be a mapping")
    if set(obs.feature_dimensions) != set(obs.features):
        raise ValueError("every feature must have exactly one declared dimension")
    if any(not isinstance(d, str) or d not in DIMENSIONS
           for d in obs.feature_dimensions.values()):
        raise ValueError("feature dimensions must use known dimension names")
    if not isinstance(obs.relations, tuple):
        raise ValueError("relations must be a tuple")
    for edge in obs.relations:
        if (not isinstance(edge, Edge)
                or not isinstance(edge.source, str) or not edge.source.strip()
                or not isinstance(edge.target, str) or not edge.target.strip()
                or not isinstance(edge.kind, str) or not edge.kind.strip()
                or edge.dimension not in DIMENSIONS):
            raise ValueError("relation endpoints, kind, and dimension must be valid")
    if not isinstance(obs.context, Mapping) or any(
        not isinstance(k, str) or not k.strip()
        or not isinstance(v, str) or not v.strip()
        for k, v in obs.context.items()
    ):
        raise ValueError("context keys and values must be non-empty strings")
    if (not isinstance(obs.evidence_refs, tuple)
            or any(not isinstance(ref, str) or not ref.strip() for ref in obs.evidence_refs)):
        raise ValueError("evidence_refs must be a tuple of non-empty strings")


def _selected_feature_dimensions(
    observations: tuple[Observation, ...], dimensions: tuple[str, ...]
) -> dict[str, str]:
    selected: dict[str, str] = {}
    for observation in observations:
        for key, dimension in observation.feature_dimensions.items():
            if dimension not in dimensions:
                continue
            previous = selected.setdefault(key, dimension)
            if previous != dimension:
                raise ValueError(f"feature {key!r} has conflicting dimensions")
    if not selected:
        raise ValueError("no observation features belong to the selected dimensions")
    return selected


def derive_pattern(
    observations: tuple[Observation, ...],
    *,
    pattern_id: str,
    dimensions: tuple[str, ...],
    min_support_ratio: float = 1.0,
    scope: str,
) -> Pattern:
    """Derive sample-bounded shared features using exact values only."""
    if (not observations or not isinstance(pattern_id, str) or not pattern_id.strip()
            or not isinstance(scope, str) or not scope.strip()):
        raise ValueError("observations, pattern_id, and scope are required")
    if (not dimensions or len(set(dimensions)) != len(dimensions)
            or set(dimensions) - DIMENSIONS):
        raise ValueError("dimensions must be non-empty, unique, and known")
    if (isinstance(min_support_ratio, bool)
            or not isinstance(min_support_ratio, (int, float))
            or not 0 < min_support_ratio <= 1):
        raise ValueError("min_support_ratio must be in (0, 1]")
    for observation in observations:
        _validate_observation(observation)
    ids = [observation.observation_id for observation in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("observation ids must be unique")

    feature_dimensions = _selected_feature_dimensions(observations, dimensions)
    keys = set(feature_dimensions)
    candidates: dict[tuple[str, str], int] = {}
    for key in keys:
        values = [
            observation.features[key]
            for observation in observations
            if key in observation.features
            and observation.feature_dimensions[key] == feature_dimensions[key]
        ]
        for value in set(values):
            count = values.count(value)
            if count / len(observations) >= min_support_ratio:
                candidates[(key, value)] = count

    invariant: dict[str, str] = {}
    for key in keys:
        ranked = sorted(
            ((count, value) for (candidate_key, value), count in candidates.items()
             if candidate_key == key),
            reverse=True,
        )
        if ranked and (len(ranked) == 1 or ranked[0][0] > ranked[1][0]):
            if ranked[0][0] / len(observations) >= min_support_ratio:
                invariant[key] = ranked[0][1]
    variable = tuple(sorted(keys - set(invariant)))
    refs = tuple(sorted({
        ref for observation in observations for ref in observation.evidence_refs
    }))
    return Pattern(
        pattern_id, 1, dimensions, invariant, feature_dimensions, variable, (),
        tuple(ids), (), refs, scope,
    )


def classify_observation(
    pattern: Pattern, observation: Observation, *, min_score: float = 1.0
) -> Membership:
    """Check dimension-aligned invariants, exclusions, and evidence presence."""
    _validate_observation(observation)
    if (isinstance(min_score, bool) or not isinstance(min_score, (int, float))
            or not 0 <= min_score <= 1):
        raise ValueError("min_score must be in [0, 1]")
    matched = tuple(sorted(
        key for key, value in pattern.invariant_features.items()
        if observation.features.get(key) == value
        and observation.feature_dimensions.get(key) == pattern.feature_dimensions.get(key)
    ))
    missing = tuple(sorted(set(pattern.invariant_features) - set(matched)))
    selected_signature = {
        key: value for key, value in observation.features.items()
        if observation.feature_dimensions[key] in pattern.dimensions
    }
    excluded = tuple(sorted(
        " & ".join(f"{key}={value}" for key, value in signature)
        for signature in pattern.excluded_patterns
        if signature and all(selected_signature.get(key) == value for key, value in signature)
    ))
    total = len(pattern.invariant_features)
    score = len(matched) / total if total else 0.0
    reasons = []
    if not total:
        reasons.append("PATTERN_HAS_NO_INVARIANTS")
    if score < min_score:
        reasons.append("INVARIANT_FEATURE_MISMATCH")
    if excluded:
        reasons.append("MATCHES_EXCLUDED_COUNTEREXAMPLE_FEATURE")
    if not observation.evidence_refs:
        reasons.append("MISSING_OBSERVATION_EVIDENCE")
    return Membership(
        observation.observation_id, not reasons, score, matched, missing, excluded,
        tuple(reasons),
    )


def revise_pattern(
    pattern: Pattern,
    *,
    positive_examples: tuple[Observation, ...] = (),
    counterexamples: tuple[Observation, ...] = (),
    min_positive_support: float = 1.0,
) -> Pattern:
    """Create a new pattern version from typed positive and negative examples."""
    if not positive_examples:
        raise ValueError("at least one positive example is required")
    if (isinstance(min_positive_support, bool)
            or not isinstance(min_positive_support, (int, float))
            or not 0 < min_positive_support <= 1):
        raise ValueError("min_positive_support must be in (0, 1]")
    examples = (*positive_examples, *counterexamples)
    for observation in examples:
        _validate_observation(observation)
    if len({observation.observation_id for observation in examples}) != len(examples):
        raise ValueError("example ids must be unique across positives and counterexamples")

    feature_dimensions = _selected_feature_dimensions(positive_examples, pattern.dimensions)
    for observation in counterexamples:
        for key, dimension in observation.feature_dimensions.items():
            if key in feature_dimensions and feature_dimensions[key] != dimension:
                raise ValueError(f"feature {key!r} has conflicting dimensions")

    keys = set(feature_dimensions)
    candidates: dict[tuple[str, str], int] = {}
    for key in keys:
        values = [
            observation.features[key]
            for observation in positive_examples
            if key in observation.features
            and observation.feature_dimensions[key] == feature_dimensions[key]
        ]
        for value in set(values):
            count = values.count(value)
            if count / len(positive_examples) >= min_positive_support:
                candidates[(key, value)] = count

    retained: dict[str, str] = {}
    for key in keys:
        ranked = sorted(
            ((count, value) for (candidate_key, value), count in candidates.items()
             if candidate_key == key),
            reverse=True,
        )
        if not ranked or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
            continue
        retained[key] = ranked[0][1]

    excluded = tuple(sorted({
        tuple(sorted(
            (key, value) for key, value in observation.features.items()
            if key in feature_dimensions
            and observation.feature_dimensions[key] == feature_dimensions[key]
        ))
        for observation in counterexamples
    }))
    excluded = tuple(signature for signature in excluded if signature)
    variable = tuple(sorted(keys - set(retained)))
    refs = tuple(sorted(
        set(pattern.evidence_refs)
        | {ref for observation in examples for ref in observation.evidence_refs}
    ))
    return Pattern(
        pattern.pattern_id, pattern.version + 1, pattern.dimensions, retained,
        feature_dimensions, variable, excluded,
        tuple(sorted({observation.observation_id for observation in positive_examples})),
        tuple(sorted({observation.observation_id for observation in counterexamples})),
        refs, pattern.scope,
    )
