"""E09-D2: zero-shot transfer and few-shot adaptation to a new context.

Contexts 0 and 1 are observed during initial training. Context 2 is withheld
from that phase, then receives a small labeled support set. The benchmark
measures both unsupported transfer and evidence-driven adaptation, including
retention on the previously observed contexts.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example, RuleLearningError,
)
from prototype.e09_noise_benchmark import BASE_DOMAIN

TRAIN_CONTEXTS = (0, 1)
NOVEL_CONTEXT = 2
ALL_CONTEXTS = (0, 1, 2)


def target(a: int, b: int, c: int, context: int) -> int:
    if context == 0:
        return int(a == 1 and c == 2)
    if context == 1:
        return int(a == 2 and b == 0)
    if context == 2:
        return int(b == 2 and c == 1)
    raise ValueError("unknown context")


def metrics(rows: list[tuple[int | None, int]]) -> dict:
    known = [(prediction, gold) for prediction, gold in rows
             if prediction is not None]
    correct = sum(prediction == gold for prediction, gold in known)
    total = len(rows)
    return {
        "total": total,
        "coverage": len(known) / total if total else 0.0,
        "selective_accuracy": correct / len(known) if known else None,
        "overall_correct_rate": correct / total if total else 0.0,
        "abstentions": total - len(known),
    }


def _fit(examples: list[Example], *, max_candidates: int):
    learner = CounterexampleRuleLearner(
        (BASE_DOMAIN, BASE_DOMAIN, BASE_DOMAIN, ALL_CONTEXTS),
        min_support=2, max_candidates=max_candidates,
    )
    learner.fit(examples)
    return learner


def run(seed: int = 71, support_size: int = 6,
        max_candidates: int = 100_000) -> dict:
    if support_size < 2 or support_size > 18:
        raise ValueError("support_size must be between 2 and 18")
    rng = random.Random(seed)
    assignments = list(itertools.product(BASE_DOMAIN, repeat=3))
    rng.shuffle(assignments)
    split = int(len(assignments) * 2 / 3)
    train_assignments = assignments[:split]
    test_assignments = assignments[split:]
    support_assignments = train_assignments[:support_size]

    initial_train = [
        Example((a, b, c, context), target(a, b, c, context))
        for context in TRAIN_CONTEXTS
        for a, b, c in train_assignments
    ]
    novel_support = [
        Example((a, b, c, NOVEL_CONTEXT), target(a, b, c, NOVEL_CONTEXT))
        for a, b, c in support_assignments
    ]
    initial = _fit(initial_train, max_candidates=max_candidates)
    adapted = _fit(initial_train + novel_support,
                   max_candidates=max_candidates)

    zero_shot = {context: [] for context in ALL_CONTEXTS}
    after_adaptation = {context: [] for context in ALL_CONTEXTS}
    for a, b, c in test_assignments:
        for context in ALL_CONTEXTS:
            gold = target(a, b, c, context)
            zero_shot[context].append((
                initial.predict((a, b, c, context)), gold
            ))
            after_adaptation[context].append((
                adapted.predict((a, b, c, context)), gold
            ))

    return {
        "task": "E09-D2_novel_context_transfer_and_adaptation",
        "seed": seed,
        "support_size": support_size,
        "split_audit": {
            "train_base_assignments": [list(row) for row in train_assignments],
            "test_base_assignments": [list(row) for row in test_assignments],
            "novel_context_support_assignments": [
                list(row) for row in support_assignments
            ],
            "train_test_disjoint": set(train_assignments).isdisjoint(test_assignments),
            "support_test_disjoint": set(support_assignments).isdisjoint(test_assignments),
            "initial_train_contexts": list(TRAIN_CONTEXTS),
            "novel_context": NOVEL_CONTEXT,
            "initial_train_rows": len(initial_train),
            "adaptation_rows": len(novel_support),
        },
        "zero_shot": {
            str(context): metrics(zero_shot[context])
            for context in ALL_CONTEXTS
        },
        "after_adaptation": {
            str(context): metrics(after_adaptation[context])
            for context in ALL_CONTEXTS
        },
        "initial_model": initial.snapshot(),
        "adapted_model": adapted.snapshot(),
        "limitations": [
            "The finite categorical DSL and context field are declared in advance.",
            "The new context has a hidden synthetic rule from a fixed family.",
            "Zero-shot predictions are measured, not assumed to be safe or correct.",
            "Few-shot adaptation uses labeled examples from the new context.",
            "This does not establish open-world discovery or transfer to arbitrary contexts.",
            "The learner uses bounded symbolic search and no gradient updates.",
        ],
    }


def run_sweep(seeds: int = 5, start_seed: int = 71,
              support_size: int = 6) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    results = [run(start_seed + index, support_size=support_size)
               for index in range(seeds)]
    summary = {}
    for phase in ("zero_shot", "after_adaptation"):
        for context in ALL_CONTEXTS:
            key = str(context)
            summary.setdefault(phase, {})[key] = {}
            for metric_name in ("coverage", "overall_correct_rate",
                                "selective_accuracy"):
                values = [
                    result[phase][key][metric_name]
                    for result in results
                    if result[phase][key][metric_name] is not None
                ]
                summary[phase][key][metric_name + "_mean"] = (
                    sum(values) / len(values) if values else None
                )
    return {
        "task": "E09-D2_novel_context_transfer_and_adaptation_sweep",
        "seeds": [start_seed + index for index in range(seeds)],
        "support_size": support_size,
        "summary": summary,
        "per_seed": results,
        "interpretation": (
            "Compare novel-context zero-shot predictions with few-shot "
            "adaptation, and inspect contexts 0/1 for catastrophic forgetting."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=71)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--support-size", type=int, default=6)
    args = parser.parse_args()
    result = (run_sweep(args.seeds, support_size=args.support_size)
              if args.sweep else run(args.seed, support_size=args.support_size))
    print(json.dumps(result, indent=2, default=repr))


if __name__ == "__main__":
    main()
