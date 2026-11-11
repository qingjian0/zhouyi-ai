"""TX-02B-2 deterministic rule-family splits and label isolation.

Splits are disjoint at the hidden coefficient-tuple level, not merely at the
episode-seed level. Model-facing inputs and evaluator-only labels are separate
objects so locked-test targets need not be passed to a learner.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from prototype.tx02_multistate_benchmark import episode_to_dict, make_episode


@dataclass(frozen=True)
class LearnerInput:
    cardinality: int
    symbol_mapping: str
    support: tuple[tuple[int, int, int], ...]
    queries: tuple[tuple[int, int], ...]
    candidates: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class SupervisedEpisode:
    inputs: LearnerInput
    targets: tuple[int, ...]


@dataclass(frozen=True)
class EvaluationEpisode:
    inputs: LearnerInput
    # Kept in evaluator-owned records; never pass this object to predict().
    targets: tuple[int, ...]


@dataclass(frozen=True)
class SplitBundle:
    train: tuple[SupervisedEpisode, ...]
    validation: tuple[EvaluationEpisode, ...]
    locked_test: tuple[EvaluationEpisode, ...]
    rule_families: dict[str, tuple[tuple[int, int, int], ...]]
    metadata: dict


def learner_input(payload: dict) -> LearnerInput:
    """Strip labels and all generator-only metadata from a serialized episode."""
    return LearnerInput(
        cardinality=payload["cardinality"],
        symbol_mapping=payload["symbol_mapping"],
        support=tuple(tuple(row) for row in payload["support"]),
        queries=tuple(tuple(row) for row in payload["queries"]),
        candidates=tuple(tuple(row) for row in payload["candidates"]),
    )


def _partition_rules(cardinality: int, seed: int,
                     train_fraction: float, validation_fraction: float
                     ) -> dict[str, tuple[tuple[int, int, int], ...]]:
    rules = [(a, b, d) for a in range(cardinality)
             for b in range(cardinality) for d in range(cardinality)]
    random.Random(seed).shuffle(rules)
    n = len(rules)
    train_end = max(1, min(n - 2, round(n * train_fraction)))
    val_end = max(train_end + 1, min(n - 1,
                                     train_end + round(n * validation_fraction)))
    return {
        "train": tuple(rules[:train_end]),
        "validation": tuple(rules[train_end:val_end]),
        "locked_test": tuple(rules[val_end:]),
    }


def make_rule_disjoint_splits(
    cardinality: int,
    episodes_per_rule: int = 2,
    support_size: int = 4,
    query_count: int = 2,
    seed: int = 20261111,
    symbol_mappings: Iterable[str] = ("canonical", "permuted"),
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> SplitBundle:
    """Create deterministic splits with no coefficient tuple shared across splits.

    This is a coefficient-family holdout, not a claim of generalization to
    arbitrary functions. For compound K, unit/non-unit coefficient strata
    remain present and should be reported separately.
    """
    if type(cardinality) is not int or cardinality < 2:
        raise ValueError("cardinality must be an integer >= 2")
    if type(episodes_per_rule) is not int or episodes_per_rule < 1:
        raise ValueError("episodes_per_rule must be >= 1")
    if not 0.0 < train_fraction < 1.0 or not 0.0 < validation_fraction < 1.0:
        raise ValueError("split fractions must be in (0, 1)")
    if train_fraction + validation_fraction >= 1.0:
        raise ValueError("train_fraction + validation_fraction must be < 1")
    mappings = tuple(symbol_mappings)
    if not mappings or any(m not in ("canonical", "permuted") for m in mappings):
        raise ValueError("symbol_mappings must contain canonical and/or permuted")

    rules = _partition_rules(cardinality, seed, train_fraction, validation_fraction)
    split_rows = {"train": [], "validation": [], "locked_test": []}
    for split_index, split_name in enumerate(("train", "validation", "locked_test")):
        for rule_index, rule in enumerate(rules[split_name]):
            for mapping_index, mapping in enumerate(mappings):
                for repeat in range(episodes_per_rule):
                    episode_seed = (seed * 1_000_003 + split_index * 100_000_007
                                    + rule_index * 10_007 + mapping_index * 101
                                    + repeat)
                    episode = make_episode(
                        cardinality, episode_seed, support_size, query_count,
                        mapping, rule=rule,
                    )
                    payload = episode_to_dict(episode)
                    row = (learner_input(payload), tuple(payload["targets"]))
                    split_rows[split_name].append(row)

    train = tuple(SupervisedEpisode(inputs, targets)
                  for inputs, targets in split_rows["train"])
    validation = tuple(EvaluationEpisode(inputs, targets)
                       for inputs, targets in split_rows["validation"])
    locked_test = tuple(EvaluationEpisode(inputs, targets)
                        for inputs, targets in split_rows["locked_test"])
    return SplitBundle(
        train=train,
        validation=validation,
        locked_test=locked_test,
        rule_families=rules,
        metadata={
            "protocol": "TX-02B-2",
            "cardinality": cardinality,
            "episodes_per_rule": episodes_per_rule,
            "support_size": support_size,
            "query_count": query_count,
            "seed": seed,
            "symbol_mappings": list(mappings),
            "split_unit": "hidden coefficient tuple (alpha,beta,delta)",
            "targets_exposed_to_learner": "train only; validation/test are evaluator records",
        },
    )
