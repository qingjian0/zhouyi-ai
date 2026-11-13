"""Evidence-traceable candidate-image abstraction and revision baseline.

This is a symbolic research prototype, not a text parser or a learned model.
It operates on observations whose features, relations, context, and evidence
have already been supplied by an annotator or upstream extractor.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

DIMENSIONS = frozenset({"morphology", "attribute", "function", "relation", "process", "spatiotemporal", "potential", "integrated"})

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

@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    version: int
    dimensions: tuple[str, ...]
    invariant_features: Mapping[str, str]
    variable_features: tuple[str, ...]
    excluded_features: tuple[tuple[str, str], ...]
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
    if not obs.observation_id.strip() or not obs.domain.strip():
        raise ValueError("observation_id and domain are required")
    if not obs.features:
        raise ValueError("observation must contain at least one feature")
    if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip() for k, v in obs.features.items()):
        raise ValueError("feature keys and values must be non-empty strings")
    for edge in obs.relations:
        if not edge.source or not edge.target or not edge.kind:
            raise ValueError("relation endpoints and kind are required")
        if edge.dimension not in DIMENSIONS:
            raise ValueError(f"unknown relation dimension: {edge.dimension}")

def derive_pattern(observations: tuple[Observation, ...], *, pattern_id: str, dimensions: tuple[str, ...], min_support_ratio: float = 1.0, scope: str) -> Pattern:
    """Derive shared candidate features; exact equality only, not semantic truth."""
    if not observations or not pattern_id.strip() or not scope.strip():
        raise ValueError("observations, pattern_id, and scope are required")
    if not dimensions or len(set(dimensions)) != len(dimensions) or set(dimensions) - DIMENSIONS:
        raise ValueError("dimensions must be non-empty, unique, and known")
    if isinstance(min_support_ratio, bool) or not isinstance(min_support_ratio, (int, float)) or not 0 < min_support_ratio <= 1:
        raise ValueError("min_support_ratio must be in (0, 1]")
    for obs in observations:
        _validate_observation(obs)
    ids = [o.observation_id for o in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("observation ids must be unique")
    keys = set.intersection(*(set(o.features) for o in observations))
    support = {key: sum(o.features.get(key) == observations[0].features.get(key) for o in observations) for key in keys}
    invariant = {key: observations[0].features[key] for key, count in support.items() if count / len(observations) >= min_support_ratio and all(o.features.get(key) == observations[0].features[key] for o in observations)}
    variable = sorted(set.union(*(set(o.features) for o in observations)) - set(invariant))
    refs = tuple(sorted({ref for o in observations for ref in o.evidence_refs}))
    return Pattern(pattern_id, 1, dimensions, invariant, tuple(variable), (), tuple(ids), (), refs, scope)

def classify_observation(pattern: Pattern, observation: Observation, *, min_score: float = 1.0) -> Membership:
    """Check a candidate against explicit invariants and exclusions."""
    _validate_observation(observation)
    if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not 0 <= min_score <= 1:
        raise ValueError("min_score must be in [0, 1]")
    matched = tuple(sorted(k for k, v in pattern.invariant_features.items() if observation.features.get(k) == v))
    missing = tuple(sorted(k for k, v in pattern.invariant_features.items() if observation.features.get(k) != v))
    excluded = tuple(sorted(k for k, v in pattern.excluded_features if observation.features.get(k) == v))
    total = len(pattern.invariant_features)
    score = len(matched) / total if total else 0.0
    reasons = []
    if not total: reasons.append("PATTERN_HAS_NO_INVARIANTS")
    if score < min_score: reasons.append("INVARIANT_FEATURE_MISMATCH")
    if excluded: reasons.append("MATCHES_EXCLUDED_COUNTEREXAMPLE_FEATURE")
    if not observation.evidence_refs: reasons.append("MISSING_OBSERVATION_EVIDENCE")
    return Membership(observation.observation_id, not reasons, score, matched, missing, excluded, tuple(reasons))

def revise_pattern(pattern: Pattern, *, positive_examples: tuple[Observation, ...] = (), counterexamples: tuple[Observation, ...] = (), min_positive_support: float = 1.0) -> Pattern:
    """Create a new version using positive support and explicit counterexamples."""
    if not positive_examples:
        raise ValueError("at least one positive example is required")
    if isinstance(min_positive_support, bool) or not isinstance(min_positive_support, (int, float)) or not 0 < min_positive_support <= 1:
        raise ValueError("min_positive_support must be in (0, 1]")
    for obs in (*positive_examples, *counterexamples): _validate_observation(obs)
    if len({o.observation_id for o in (*positive_examples, *counterexamples)}) != len(positive_examples) + len(counterexamples):
        raise ValueError("example ids must be unique across positives and counterexamples")
    keys = set.union(*(set(o.features) for o in positive_examples))
    candidates = {}
    for key in keys:
        values = [o.features[key] for o in positive_examples if key in o.features]
        for value in set(values):
            count = values.count(value)
            if count / len(positive_examples) >= min_positive_support:
                candidates[(key, value)] = count
    excluded = {pair for pair in candidates if any(o.features.get(pair[0]) == pair[1] for o in counterexamples)}
    retained = {key: value for (key, value) in candidates if (key, value) not in excluded}
    variable = sorted(keys - set(retained))
    refs = tuple(sorted(set(pattern.evidence_refs) | {ref for o in (*positive_examples, *counterexamples) for ref in o.evidence_refs}))
    return Pattern(pattern.pattern_id, pattern.version + 1, pattern.dimensions, retained, tuple(variable), tuple(sorted(excluded)), tuple(sorted({o.observation_id for o in positive_examples})), tuple(sorted({o.observation_id for o in counterexamples})), refs, pattern.scope)
