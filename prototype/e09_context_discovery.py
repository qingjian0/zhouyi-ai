"""E09-D1: discover context-conditioned relations under environment shifts.

Two environments use different hidden rules. The learner is not told either
rule. We compare a learner that receives the context variable with a context-
blind learner whose contradictory observations are quarantined by EvidenceLedger.
This is a finite synthetic benchmark, not open-ended discovery.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example, RuleLearningError,
)
from prototype.e09_evidence_ledger import EvidenceLedger
from prototype.e09_noise_benchmark import BASE_DOMAIN


ENVIRONMENTS = (0, 1)


def target(a: int, b: int, c: int, environment: int) -> int:
    if environment == 0:
        return int(a == 1 and c == 2)
    return int(a == 2 and b == 0)


def _metrics(predictions: list[tuple[int | None, int]]) -> dict:
    known = [(p, y) for p, y in predictions if p is not None]
    correct = sum(p == y for p, y in known)
    total = len(predictions)
    return {
        "total": total,
        "coverage": len(known) / total if total else 0.0,
        "selective_accuracy": correct / len(known) if known else None,
        "overall_correct_rate": correct / total if total else 0.0,
        "abstentions": total - len(known),
    }


def run(seed: int = 31, min_support: int = 2,
        max_candidates: int = 100_000) -> dict:
    rng = random.Random(seed)
    assignments = list(itertools.product(BASE_DOMAIN, repeat=3))
    rng.shuffle(assignments)
    split = int(len(assignments) * 2 / 3)
    train_assignments = assignments[:split]
    test_assignments = assignments[split:]

    contextual_train = [
        Example((a, b, c, env), target(a, b, c, env))
        for a, b, c in train_assignments
        for env in ENVIRONMENTS
    ]
    contextual = CounterexampleRuleLearner(
        (BASE_DOMAIN, BASE_DOMAIN, BASE_DOMAIN, ENVIRONMENTS),
        min_support=min_support, max_candidates=max_candidates,
    )
    contextual_error = None
    try:
        contextual.fit(contextual_train)
    except RuleLearningError as exc:
        contextual_error = str(exc)

    ledger = EvidenceLedger()
    for env in ENVIRONMENTS:
        for a, b, c in train_assignments:
            ledger.append(
                f"train-e{env}-{a}{b}{c}",
                Example((a, b, c), target(a, b, c, env)),
            )
    blind_train = ledger.training_examples()
    contested_inputs = tuple(
        tuple(item["inputs"]) for item in ledger.adjudication()["contested"]
    )
    blind = CounterexampleRuleLearner(
        (BASE_DOMAIN, BASE_DOMAIN, BASE_DOMAIN),
        min_support=min_support, max_candidates=max_candidates,
    )
    blind_error = None
    try:
        if not blind_train:
            raise RuleLearningError("no uncontested context-blind training rows")
        blind.fit(blind_train)
    except RuleLearningError as exc:
        blind_error = str(exc)

    unsafe_blind_clauses = {
        index for index, clause in enumerate(blind.clauses)
        if any(clause.matches(inputs) for inputs in contested_inputs)
    }
    safe_blind_clauses = tuple(
        clause for index, clause in enumerate(blind.clauses)
        if index not in unsafe_blind_clauses
    )

    def predict_blind_safely(inputs: tuple[int, int, int]):
        labels = {
            clause.label for clause in safe_blind_clauses
            if clause.matches(inputs)
        }
        return next(iter(labels)) if len(labels) == 1 else None

    contextual_predictions = {env: [] for env in ENVIRONMENTS}
    blind_predictions = {env: [] for env in ENVIRONMENTS}
    for a, b, c in test_assignments:
        for env in ENVIRONMENTS:
            gold = target(a, b, c, env)
            contextual_prediction = (
                contextual.predict((a, b, c, env))
                if contextual_error is None else None
            )
            blind_prediction = (
                predict_blind_safely((a, b, c))
                if blind_error is None else None
            )
            contextual_predictions[env].append((contextual_prediction, gold))
            blind_predictions[env].append((blind_prediction, gold))

    contextual_by_env = {
        str(env): _metrics(contextual_predictions[env])
        for env in ENVIRONMENTS
    }
    blind_by_env = {
        str(env): _metrics(blind_predictions[env])
        for env in ENVIRONMENTS
    }
    return {
        "task": "E09-D1_context_conditioned_relation_discovery",
        "seed": seed,
        "split_audit": {
            "train_base_assignments": [list(row) for row in train_assignments],
            "test_base_assignments": [list(row) for row in test_assignments],
            "environment_count": len(ENVIRONMENTS),
            "contextual_train_rows": len(contextual_train),
            "context_blind_unique_train_rows": len(blind_train),
            "context_blind_contested_inputs": ledger.adjudication()["contested_inputs"],
        },
        "contextual": {
            "error": contextual_error,
            "metrics_by_environment": contextual_by_env,
            "learner_snapshot": contextual.snapshot(),
        },
        "context_blind": {
            "error": blind_error,
            "metrics_by_environment": blind_by_env,
            "learner_snapshot": blind.snapshot(),
            "unsafe_clauses_quarantined": len(unsafe_blind_clauses),
            "safe_clauses_retained": len(safe_blind_clauses),
            "ledger_adjudication": ledger.adjudication(),
        },
        "limitations": [
            "The categorical DSL and context variable are declared in advance.",
            "The hidden rule family is synthetic and finite.",
            "Both environments are represented in training; this tests context-conditioned identification, not zero-shot discovery of a never-seen environment.",
            "Context-blind contradictory inputs are quarantined, so abstention is an intended safe behavior.",
            "No gradient updates are used by either learner.",
        ],
    }


def run_sweep(seeds: int = 5, start_seed: int = 31) -> dict:
    if seeds < 1:
        raise ValueError("seeds must be positive")
    results = [run(start_seed + i) for i in range(seeds)]
    summary = {}
    for model in ("contextual", "context_blind"):
        for env in ENVIRONMENTS:
            key = str(env)
            for metric in ("coverage", "overall_correct_rate"):
                values = [
                    row[model]["metrics_by_environment"][key][metric]
                    for row in results
                ]
                summary.setdefault(model, {}).setdefault(key, {})[
                    f"{metric}_mean"
                ] = sum(values) / len(values)
    return {
        "task": "E09-D1_context_conditioned_relation_discovery_sweep",
        "seeds": [start_seed + i for i in range(seeds)],
        "summary": summary,
        "per_seed": results,
        "interpretation": (
            "Contextual and context-blind arms share identical base splits. "
            "Compare per-environment coverage and overall correctness; do not "
            "interpret abstention as an ordinary classification error."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_sweep(args.seeds) if args.sweep else run(args.seed)
    print(json.dumps(result, indent=2, default=repr) if args.json else result)


if __name__ == "__main__":
    main()
