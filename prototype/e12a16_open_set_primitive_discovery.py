"""E12-A16: open-set sparse primitive discovery with MDL and held-out gates.

This is a symbolic research prototype, not a production learner. It discovers
sparse conjunctions over observed atoms; it does not claim semantic grounding.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class PrimitiveObservation:
    observation_id: str
    atoms: tuple[str, ...]
    outcome: str
    incumbent_probability: float | None = None

    def __post_init__(self):
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise ValueError("observation_id is required")
        if not isinstance(self.atoms, tuple) or tuple(sorted(set(self.atoms))) != self.atoms:
            raise ValueError("atoms must be a sorted tuple of unique strings")
        if any(not isinstance(x, str) or not x.strip() for x in self.atoms):
            raise ValueError("atoms must be non-empty strings")
        if not isinstance(self.outcome, str) or not self.outcome.strip():
            raise ValueError("outcome is required")
        if self.incumbent_probability is not None:
            p = self.incumbent_probability
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 < p <= 1:
                raise ValueError("incumbent_probability must be in (0,1]")


@dataclass(frozen=True)
class DiscoveryConfig:
    max_arity: int = 3
    min_train_support: int = 3
    min_validation_support: int = 2
    max_candidates: int = 5000
    max_complexity_bits: float = 24.0
    min_train_gain_bits: float = 0.0
    min_validation_gain_bits: float = 0.0
    laplace_alpha: float = 0.5
    validation_fraction: float = 0.3
    novelty_probability_threshold: float = 0.05
    novelty_fraction_threshold: float = 0.25

    def __post_init__(self):
        for name in ("max_arity", "min_train_support", "min_validation_support", "max_candidates"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("max_complexity_bits", "min_train_gain_bits", "min_validation_gain_bits",
                     "laplace_alpha", "novelty_probability_threshold", "novelty_fraction_threshold"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.max_complexity_bits <= 0 or self.laplace_alpha <= 0:
            raise ValueError("complexity budget and Laplace alpha must be positive")
        if not 0 <= self.validation_fraction < 1:
            raise ValueError("validation_fraction must be in [0,1)")
        if not 0 < self.novelty_probability_threshold <= 1:
            raise ValueError("novelty_probability_threshold must be in (0,1]")
        if not 0 <= self.novelty_fraction_threshold <= 1:
            raise ValueError("novelty_fraction_threshold must be in [0,1]")


@dataclass(frozen=True)
class DiscoveredPrimitive:
    primitive_id: str
    version: int
    atoms: tuple[str, ...]
    outcome_probabilities: tuple[tuple[str, float], ...]
    train_support: int
    validation_support: int
    train_gain_bits: float
    validation_gain_bits: float
    complexity_bits: float
    description_length_gain_bits: float
    parent_refs: tuple[str, ...]
    grammar_version: str


@dataclass(frozen=True)
class NoveltyReport:
    observation_count: int
    low_likelihood_count: int
    low_likelihood_fraction: float
    threshold: float
    novelty_detected: bool
    unexplained_observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[DiscoveredPrimitive, ...]
    novelty: NoveltyReport
    generated_candidate_count: int
    truncated: bool
    train_observation_ids: tuple[str, ...]
    validation_observation_ids: tuple[str, ...]
    dataset_digest: str


def _split(observations: tuple[PrimitiveObservation, ...], fraction: float):
    ordered = sorted(observations, key=lambda x: x.observation_id)
    if fraction == 0 or len(ordered) < 4:
        return ordered, []
    validation_count = max(1, min(len(ordered) - 2, round(len(ordered) * fraction)))
    validation = ordered[-validation_count:]
    train = ordered[:-validation_count]
    return train, validation


def _distribution(rows: Iterable[PrimitiveObservation], outcomes: tuple[str, ...],
                  alpha: float) -> dict[str, float]:
    counts = Counter(row.outcome for row in rows)
    denominator = sum(counts.values()) + alpha * len(outcomes)
    return {outcome: (counts[outcome] + alpha) / denominator for outcome in outcomes}


def _gain_bits(rows: list[PrimitiveObservation], baseline: dict[str, float],
               conditional: dict[str, float], matched_atoms: tuple[str, ...]) -> float:
    total = 0.0
    for row in rows:
        if all(atom in row.atoms for atom in matched_atoms):
            total += math.log2(conditional[row.outcome] / baseline[row.outcome])
    return total


def _complexity_bits(atoms: tuple[str, ...], vocabulary_size: int) -> float:
    # Universal-code style upper bound: choose subset + encode each atom and rule header.
    k, n = len(atoms), max(1, vocabulary_size)
    return 1.0 + math.log2(math.comb(n, k)) + k * math.log2(n + 1)


def _novelty_report(observations: tuple[PrimitiveObservation, ...],
                    config: DiscoveryConfig) -> NoveltyReport:
    measured = [row for row in observations if row.incumbent_probability is not None]
    low = [row for row in measured
           if row.incumbent_probability <= config.novelty_probability_threshold]
    fraction = len(low) / len(measured) if measured else 0.0
    return NoveltyReport(len(measured), len(low), fraction,
        config.novelty_probability_threshold,
        bool(measured) and fraction >= config.novelty_fraction_threshold,
        tuple(row.observation_id for row in low))


def discover_primitives(observations: Iterable[PrimitiveObservation], *,
                        parent_refs: tuple[str, ...] = (),
                        grammar_version: str = "sparse-conjunction-v1",
                        config: DiscoveryConfig = DiscoveryConfig()) -> DiscoveryResult:
    rows = tuple(observations)
    if len(rows) < 4:
        raise ValueError("at least four observations are required for train/validation discovery")
    if len({row.observation_id for row in rows}) != len(rows):
        raise ValueError("observation ids must be unique")
    if any(not isinstance(ref, str) or not ref.strip() for ref in parent_refs):
        raise ValueError("parent_refs must contain non-empty strings")
    if not grammar_version.strip():
        raise ValueError("grammar_version is required")

    train, validation = _split(rows, config.validation_fraction)
    outcomes = tuple(sorted({row.outcome for row in rows}))
    vocabulary = tuple(sorted({atom for row in rows for atom in row.atoms}))
    if not outcomes or not vocabulary:
        raise ValueError("observations need at least one atom and outcome")
    baseline = _distribution(train, outcomes, config.laplace_alpha)
    generated = 0
    truncated = False
    candidates = []

    for arity in range(1, min(config.max_arity, len(vocabulary)) + 1):
        for atom_set in itertools.combinations(vocabulary, arity):
            if generated >= config.max_candidates:
                truncated = True
                break
            generated += 1
            matching_train = [row for row in train
                              if all(atom in row.atoms for atom in atom_set)]
            matching_validation = [row for row in validation
                                   if all(atom in row.atoms for atom in atom_set)]
            if len(matching_train) < config.min_train_support:
                continue
            if validation and len(matching_validation) < config.min_validation_support:
                continue
            conditional = _distribution(matching_train, outcomes, config.laplace_alpha)
            complexity = _complexity_bits(atom_set, len(vocabulary))
            if complexity > config.max_complexity_bits:
                continue
            train_gain = _gain_bits(train, baseline, conditional, atom_set)
            validation_gain = (_gain_bits(validation, baseline, conditional, atom_set)
                               if validation else train_gain)
            # Charge structural complexity once; require independent held-out improvement.
            mdl_gain = train_gain - complexity
            if mdl_gain <= config.min_train_gain_bits:
                continue
            if validation and validation_gain <= config.min_validation_gain_bits:
                continue
            payload = {"atoms": atom_set, "outcomes": conditional,
                       "parents": parent_refs, "grammar": grammar_version}
            primitive_id = "primitive:" + _digest(payload)[:20]
            candidates.append(DiscoveredPrimitive(
                primitive_id, 1, atom_set, tuple(sorted(conditional.items())),
                len(matching_train), len(matching_validation), train_gain,
                validation_gain, complexity, mdl_gain, parent_refs, grammar_version))

        if truncated:
            break

    candidates.sort(key=lambda c: (-c.validation_gain_bits,
                                   -c.description_length_gain_bits,
                                   len(c.atoms), c.atoms, c.primitive_id))
    return DiscoveryResult(tuple(candidates), _novelty_report(rows, config),
        generated, truncated, tuple(row.observation_id for row in train),
        tuple(row.observation_id for row in validation),
        _digest([{"id": r.observation_id, "atoms": r.atoms, "outcome": r.outcome,
                  "incumbent_probability": r.incumbent_probability} for r in rows]))
