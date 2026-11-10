"""E09-C: controlled label-noise and spurious-feature benchmark.

Training and test assignments are disjoint. The shortcut feature is correlated
with the clean label in the shortcut arm's training set, then randomized at
test time. A no-shortcut arm controls for the extra input dimension.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import dataclass

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example, RuleLearningError,
)

BASE_DOMAIN = (0, 1, 2)
DISTRACTOR_DOMAIN = (0, 1)


def target(a: int, b: int, c: int) -> int:
    return int((a == 1 and c == 2) or (a == 2 and b == 0))


@dataclass(frozen=True)
class BenchmarkResult:
    seed: int
    noise_rate: float
    shortcut_enabled: bool
    train_size: int
    test_size: int
    coverage: float
    selective_accuracy: float | None
    overall_correct_rate: float
    abstention_rate: float
    prediction_agreement_with_shortcut: float
    candidate_evaluations: int
    error: str | None = None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def run(seed: int = 17, noise_rate: float = 0.0,
        shortcut_enabled: bool = True, min_support: int = 2,
        max_candidates: int = 100_000) -> dict:
    if not 0.0 <= noise_rate <= 1.0:
        raise ValueError("noise_rate must be between 0 and 1")
    split_rng = random.Random(seed)
    noise_rng = random.Random(seed + 1)
    train_distractor_rng = random.Random(seed + 2)
    test_distractor_rng = random.Random(seed + 3)
    assignments = list(itertools.product(BASE_DOMAIN, repeat=3))
    split_rng.shuffle(assignments)
    split = int(len(assignments) * 2 / 3)
    train_assignments, test_assignments = assignments[:split], assignments[split:]

    train = []
    noise_flipped_assignments = []
    for a, b, c in train_assignments:
        gold = target(a, b, c)
        flipped = noise_rng.random() < noise_rate
        observed = 1 - gold if flipped else gold
        if flipped:
            noise_flipped_assignments.append((a, b, c))
        z = gold if shortcut_enabled else train_distractor_rng.randrange(2)
        train.append(Example((a, b, c, z), observed))

    learner = CounterexampleRuleLearner(
        (BASE_DOMAIN, BASE_DOMAIN, BASE_DOMAIN, DISTRACTOR_DOMAIN),
        min_support=min_support, max_candidates=max_candidates,
    )
    fit_error = None
    try:
        learner.fit(train)
    except RuleLearningError as exc:
        fit_error = str(exc)

    evaluated = []
    shortcut_predictions = 0
    shortcut_agreements = 0
    for a, b, c in test_assignments:
        gold = target(a, b, c)
        z = test_distractor_rng.randrange(2)
        prediction = learner.predict((a, b, c, z)) if fit_error is None else None
        evaluated.append((prediction, gold))
        if prediction is not None:
            shortcut_predictions += 1
            if prediction == z:
                shortcut_agreements += 1

    predicted = [(p, y) for p, y in evaluated if p is not None]
    correct = sum(p == y for p, y in predicted)
    n = len(evaluated)
    result = BenchmarkResult(
        seed=seed, noise_rate=noise_rate, shortcut_enabled=shortcut_enabled,
        train_size=len(train), test_size=n,
        coverage=len(predicted) / n,
        selective_accuracy=correct / len(predicted) if predicted else None,
        overall_correct_rate=correct / n,
        abstention_rate=(n - len(predicted)) / n,
        prediction_agreement_with_shortcut=(
            shortcut_agreements / shortcut_predictions
            if shortcut_predictions else 0.0
        ),
        candidate_evaluations=learner.report.get(
            "candidate_patterns_evaluated", 0),
        error=fit_error,
    )
    return {
        "task": "E09-C_label_noise_and_spurious_shortcut",
        "seed": seed,
        "noise_rate": noise_rate,
        "shortcut_enabled": shortcut_enabled,
        "split_audit": {
            "train_assignments": [list(row) for row in train_assignments],
            "test_assignments": [list(row) for row in test_assignments],
            "noise_flipped_assignments": [
                list(row) for row in noise_flipped_assignments
            ],
        },
        "result": result.as_dict(),
        "learner_snapshot": learner.snapshot(),
        "limitations": [
            "The rule DSL, domains, and hidden target family are declared.",
            "Train and test base assignments are disjoint, but share the same finite rule family.",
            "The shortcut is synthetic and correlated only in the shortcut arm's training set.",
            "One observation per training assignment means the ledger cannot identify isolated label flips.",
            "This is a finite synthetic stress test, not real-world noise robustness.",
            "No gradient updates are used by the learner.",
        ],
    }


def run_sweep(seeds: int = 5, start_seed: int = 17,
              noise_rates: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20)) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    rows = []
    for rate in noise_rates:
        for shortcut in (False, True):
            results = [run(start_seed + i, rate, shortcut)["result"]
                       for i in range(seeds)]
            rows.append({
                "noise_rate": rate,
                "shortcut_enabled": shortcut,
                "seeds": seeds,
                "coverage_mean": sum(r["coverage"] for r in results) / seeds,
                "selective_accuracy_mean": (
                    sum(r["selective_accuracy"] or 0.0 for r in results) / seeds
                ),
                "overall_correct_rate_mean": (
                    sum(r["overall_correct_rate"] for r in results) / seeds
                ),
                "abstention_rate_mean": (
                    sum(r["abstention_rate"] for r in results) / seeds
                ),
                "prediction_agreement_with_shortcut_mean": (
                    sum(r["prediction_agreement_with_shortcut"]
                        for r in results) / seeds
                ),
                "candidate_evaluations_mean": (
                    sum(r["candidate_evaluations"] for r in results) / seeds
                ),
                "fit_failures": sum(bool(r["error"]) for r in results),
            })
    return {
        "task": "E09-C_label_noise_and_spurious_shortcut_sweep",
        "seed_start": start_seed,
        "seeds_per_condition": seeds,
        "rows": rows,
        "interpretation": (
            "Compare shortcut and no-shortcut arms at each noise rate. "
            "Report coverage and selective accuracy together."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--noise-rate", type=float, default=0.0)
    parser.add_argument("--no-shortcut", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=17)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = (run_sweep(args.seeds, args.start_seed) if args.sweep
              else run(args.seed, args.noise_rate, not args.no_shortcut))
    print(json.dumps(result, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
