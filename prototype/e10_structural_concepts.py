"""E10-A: unsupervised structural concept formation from relational observations.

This deliberately discovers recurring attribute bundles and role-conditioned
bundles without receiving concept labels. It is a bounded finite prototype,
not open-world concept learning.
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Observation:
    """One object observation; object_id is provenance only, never a feature."""
    object_id: str
    attributes: frozenset[str]
    role_attributes: tuple[tuple[str, frozenset[str]], ...] = ()


@dataclass(frozen=True)
class ConceptCandidate:
    kind: str
    features: tuple[str, ...]
    support: int
    object_ids: tuple[str, ...]

    @property
    def complexity(self) -> int:
        return len(self.features) + (1 if self.kind == "role_bundle" else 0)


class ConceptFormationError(ValueError):
    pass


class StructuralConceptLearner:
    """Mine recurring bundles, with support counted by distinct object IDs.

    Candidate vocabulary is induced from observations. No target concept names,
    labels, or hidden generator metadata are accepted by the learner.
    """

    def __init__(self, *, min_support: int = 2, max_arity: int = 3,
                 max_candidates: int = 50_000) -> None:
        if min_support < 2 or max_arity < 1 or max_candidates < 1:
            raise ConceptFormationError("invalid support, arity, or candidate budget")
        self.min_support = min_support
        self.max_arity = max_arity
        self.max_candidates = max_candidates
        self.candidates: tuple[ConceptCandidate, ...] = ()
        self.report: dict = {"fitted": False}

    @staticmethod
    def _validate(rows: Iterable[Observation]) -> tuple[Observation, ...]:
        observations = tuple(rows)
        if not observations:
            raise ConceptFormationError("observations must not be empty")
        ids = [row.object_id for row in observations]
        if any(not value for value in ids) or len(set(ids)) != len(ids):
            raise ConceptFormationError("object IDs must be non-empty and unique")
        for row in observations:
            if not isinstance(row.attributes, frozenset):
                raise ConceptFormationError("attributes must be a frozenset")
            role_names = [role for role, _ in row.role_attributes]
            if len(set(role_names)) != len(role_names):
                raise ConceptFormationError("role names must be unique per object")
            if any(not role or not isinstance(attrs, frozenset)
                   for role, attrs in row.role_attributes):
                raise ConceptFormationError("roles need names and frozenset attributes")
        return observations

    def fit(self, rows: Iterable[Observation]) -> "StructuralConceptLearner":
        observations = self._validate(rows)
        bundles: dict[tuple[str, tuple[str, ...]], set[str]] = defaultdict(set)
        evaluated = 0
        for row in observations:
            attrs = tuple(sorted(row.attributes))
            for size in range(1, min(self.max_arity, len(attrs)) + 1):
                for bundle in itertools.combinations(attrs, size):
                    evaluated += 1
                    if evaluated > self.max_candidates:
                        raise ConceptFormationError("candidate evaluation budget exceeded")
                    bundles[("attribute_bundle", bundle)].add(row.object_id)
            for role, role_attrs in row.role_attributes:
                values = tuple(sorted(role_attrs))
                for size in range(1, min(self.max_arity, len(values)) + 1):
                    for bundle in itertools.combinations(values, size):
                        evaluated += 1
                        if evaluated > self.max_candidates:
                            raise ConceptFormationError("candidate evaluation budget exceeded")
                        # Role identity is structural; object identity is not.
                        bundles[("role_bundle", (role, *bundle))].add(row.object_id)

        found = [
            ConceptCandidate(kind, features, len(object_ids), tuple(sorted(object_ids)))
            for (kind, features), object_ids in bundles.items()
            if len(object_ids) >= self.min_support
        ]
        self.candidates = tuple(sorted(
            found, key=lambda c: (-c.support, c.complexity, c.kind, c.features)
        ))
        self.report = {
            "fitted": True,
            "observations": len(observations),
            "distinct_attribute_values": len({a for row in observations for a in row.attributes}),
            "candidate_extensions_evaluated": evaluated,
            "candidate_budget": self.max_candidates,
            "candidate_count": len(self.candidates),
            "min_support": self.min_support,
            "max_arity": self.max_arity,
            "target_labels_received": False,
            "gradient_updates": 0,
        }
        return self

    def snapshot(self) -> dict:
        return {
            "report": dict(self.report),
            "candidates": [
                {"kind": c.kind, "features": list(c.features),
                 "support": c.support, "object_ids": list(c.object_ids),
                 "complexity": c.complexity}
                for c in self.candidates
            ],
        }


def synthetic_observations(seed: int = 17, *, rename: bool = False,
                           shuffle: bool = False) -> tuple[Observation, ...]:
    """Synthetic data with recurring latent bundles and hard near-miss objects.

    The learner is not given the latent family names. Near misses share all but
    one feature, preventing a single common attribute from defining the motif.
    """
    import random

    rng = random.Random(seed)
    rows = []
    for index in range(12):
        suffix = f"renamed-{(index * 7) % 12}" if rename else f"object-{index}"
        core = {"amber", "spiral", "resonant"}
        if index >= 6:
            core = {"cobalt", "lattice", "conductive"}
        noise = {f"noise-{rng.randrange(5)}"}
        attrs = frozenset(core | noise)
        role_attrs = (
            ("agent", frozenset({"initiates", "persists"} if index % 2 == 0
                                else {"initiates", "adapts"})),
            ("medium", frozenset({"transmits", "filters"})),
        )
        rows.append(Observation(suffix, attrs, role_attrs))
    # Hard negatives: two of three motif features, never the complete bundle.
    for index in range(6):
        rows.append(Observation(
            f"near-miss-{index}",
            frozenset({"amber", "spiral", f"decoy-{index}"}),
            (("agent", frozenset({"initiates"})),),
        ))
    if shuffle:
        rng.shuffle(rows)
        rows = [
            Observation(row.object_id, row.attributes,
                        tuple(reversed(row.role_attributes)))
            for row in rows
        ]
    return tuple(rows)


def run(seed: int = 17, *, min_support: int = 4) -> dict:
    rows = synthetic_observations(seed)
    learner = StructuralConceptLearner(min_support=min_support).fit(rows)
    snapshot = learner.snapshot()
    return {
        "task": "E10-A_unsupervised_structural_concept_formation",
        "seed": seed,
        "learner": snapshot,
        "limitations": [
            "The synthetic generator contains recurring bundles by construction.",
            "The learner discovers frequent bundles, not semantic meaning or causality.",
            "Feature symbols and role slots are observable inputs; raw perception is out of scope.",
            "This is finite frequent-structure induction, not open-world concept invention.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seed)
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
