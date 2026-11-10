"""E11-A0: unlabeled recurring-substructure concept proposal baseline.

This is a deliberately narrow, transparent frequent-pattern baseline. It
proposes conjunctions of opaque attributes from learner-visible objects;
hidden concept memberships are kept in the evaluator-only benchmark object.
It is not an open-world concept learner.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ObjectView:
    object_id: str
    attributes: frozenset[str]


@dataclass(frozen=True)
class Episode:
    learner_objects: tuple[ObjectView, ...]
    query_objects: tuple[ObjectView, ...]
    # Evaluator-only truth. Never passed to propose_concepts or predict.
    truth: dict[str, frozenset[str]]
    hidden_schemas: dict[str, frozenset[str]]


def make_episode(seed: int = 17, *, object_count: int = 240,
                 train_fraction: float = 0.6) -> Episode:
    if object_count < 30:
        raise ValueError("object_count must be at least 30")
    if not 0.2 <= train_fraction <= 0.8:
        raise ValueError("train_fraction must be in [0.2, 0.8]")
    rng = random.Random(seed)
    schemas = {
        "latent-a": frozenset({"attr-01", "attr-02", "attr-03"}),
        "latent-b": frozenset({"attr-04", "attr-05", "attr-06"}),
        "latent-c": frozenset({"attr-07", "attr-08", "attr-09"}),
    }
    objects: list[ObjectView] = []
    truth: dict[str, frozenset[str]] = {}
    for index in range(object_count):
        memberships = {
            concept for concept in schemas
            if rng.random() < (0.34 if concept != "latent-c" else 0.28)
        }
        # Ensure a useful mixture without exposing memberships to the learner.
        attrs = set()
        for concept in memberships:
            attrs.update(schemas[concept])
        for noise_index in range(12):
            if rng.random() < 0.12:
                attrs.add(f"noise-{noise_index:02d}")
        # Rare distractor attributes make single-feature frequency insufficient.
        if rng.random() < 0.08:
            attrs.add("rare-decoy")
        object_id = f"object-{index:04d}"
        objects.append(ObjectView(object_id, frozenset(attrs)))
        truth[object_id] = frozenset(memberships)
    rng.shuffle(objects)
    split = int(object_count * train_fraction)
    learner = tuple(objects[:split])
    query = tuple(objects[split:])
    return Episode(learner, query, truth, schemas)


def _canonical(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(items)))


def propose_concepts(objects: tuple[ObjectView, ...], *,
                     min_support: float = 0.08,
                     max_order: int = 3) -> tuple[tuple[str, ...], ...]:
    """Enumerate frequent attribute conjunctions using learner data only."""
    if not 0.0 < min_support <= 1.0:
        raise ValueError("min_support must be in (0, 1]")
    if not 1 <= max_order <= 4:
        raise ValueError("max_order must be between 1 and 4")
    if not objects:
        return ()
    vocabulary = sorted(set().union(*(obj.attributes for obj in objects)))
    proposals = []
    for order in range(1, max_order + 1):
        for candidate in itertools.combinations(vocabulary, order):
            support = sum(set(candidate).issubset(obj.attributes)
                          for obj in objects) / len(objects)
            if support >= min_support:
                proposals.append(candidate)
    return tuple(proposals)


def predict(objects: tuple[ObjectView, ...],
            concepts: tuple[tuple[str, ...], ...]) -> dict[str, frozenset[int]]:
    """Return candidate indices present in each object; no truth is accepted."""
    predictions = {}
    for obj in objects:
        present = frozenset(
            index for index, concept in enumerate(concepts)
            if set(concept).issubset(obj.attributes)
        )
        predictions[obj.object_id] = present
    return predictions


def _f1(predicted: set[str], actual: set[str]) -> float:
    if not predicted and not actual:
        return 1.0
    if not predicted or not actual:
        return 0.0
    precision = len(predicted & actual) / len(predicted)
    recall = len(predicted & actual) / len(actual)
    return 2 * precision * recall / (precision + recall)


def evaluate(episode: Episode, concepts: tuple[tuple[str, ...], ...]) -> dict:
    """Evaluator-only best-match scoring; concepts remain unlabeled."""
    predictions = predict(episode.query_objects, concepts)
    rows = []
    for latent_id in sorted(episode.hidden_schemas):
        actual = {
            obj.object_id for obj in episode.query_objects
            if latent_id in episode.truth[obj.object_id]
        }
        best = max((
            _f1(
                {object_id for object_id, indices in predictions.items()
                 if candidate_index in indices},
                actual,
            )
            for candidate_index in range(len(concepts))
        ), default=0.0)
        rows.append({"latent_concept": latent_id, "best_query_f1": best,
                     "query_positive_count": len(actual)})
    return {
        "query_objects": len(episode.query_objects),
        "candidate_count": len(concepts),
        "per_concept": rows,
        "mean_best_query_f1": sum(r["best_query_f1"] for r in rows) / len(rows),
    }


def run(seed: int = 17, *, object_count: int = 240,
        min_support: float = 0.08, max_order: int = 3) -> dict:
    episode = make_episode(seed, object_count=object_count)
    candidates = propose_concepts(
        episode.learner_objects, min_support=min_support, max_order=max_order
    )
    result = evaluate(episode, candidates)
    return {
        "task": "E11-A0_unlabeled_recurring_attribute_conjunctions",
        "seed": seed,
        "learner_objects": len(episode.learner_objects),
        "query_objects": len(episode.query_objects),
        "object_identity_disjoint": not (
            {o.object_id for o in episode.learner_objects}
            & {o.object_id for o in episode.query_objects}
        ),
        "max_order": max_order,
        "min_support": min_support,
        "candidate_count": len(candidates),
        "mean_best_query_f1": result["mean_best_query_f1"],
        "per_concept": result["per_concept"],
        "limitations": [
            "The generator uses three planted attribute conjunctions.",
            "The learner is bounded frequent-pattern enumeration, not autonomous ontology induction.",
            "Evaluator truth is available only to evaluate(), not proposal or prediction.",
            "The benchmark does not establish causal, compositional, or natural-language concepts.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--objects", type=int, default=240)
    parser.add_argument("--min-support", type=float, default=0.08)
    parser.add_argument("--max-order", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run(args.seed, object_count=args.objects,
                 min_support=args.min_support, max_order=args.max_order)
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
