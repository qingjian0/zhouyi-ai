"""E09-B: counterexample-driven rule-structure induction without gradients.

The learner searches a declared finite conjunction DSL. It is intentionally
small and auditable: each clause is a partial assignment (a conjunction of
categorical literals) associated with one label. A clause is admissible only
when it covers enough positive observations and no observed counterexample.
Uncovered or conflicting inputs are rejected rather than guessed.

This is a symbolic prototype, not evidence of open-ended rule invention.
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from typing import Hashable, Iterable, Sequence

Value = Hashable
Label = Hashable
Pattern = tuple[Value | None, ...]


@dataclass(frozen=True)
class Example:
    inputs: tuple[Value, ...]
    label: Label


class RuleLearningError(ValueError):
    """Raised when examples or the declared DSL are invalid."""


@dataclass(frozen=True)
class Clause:
    pattern: Pattern
    label: Label
    support_count: int

    @property
    def literal_count(self) -> int:
        return sum(value is not None for value in self.pattern)

    def matches(self, inputs: tuple[Value, ...]) -> bool:
        return all(expected is None or expected == actual
                   for expected, actual in zip(self.pattern, inputs))


class CounterexampleRuleLearner:
    """Greedy minimum-description conjunction cover with explicit abstention."""

    def __init__(self, domains: Sequence[Sequence[Value]], *,
                 min_support: int = 2, max_candidates: int = 100_000) -> None:
        self.domains = tuple(tuple(dict.fromkeys(domain)) for domain in domains)
        if not self.domains or any(not domain for domain in self.domains):
            raise RuleLearningError("every input variable needs a non-empty domain")
        if min_support < 1 or max_candidates < 1:
            raise RuleLearningError("support and candidate budgets must be positive")
        self.min_support = min_support
        self.max_candidates = max_candidates
        self.clauses: tuple[Clause, ...] = ()
        self.report: dict = {"fitted": False}

    def _validate(self, examples: Iterable[Example]) -> tuple[Example, ...]:
        rows = tuple(examples)
        if not rows:
            raise RuleLearningError("training examples must not be empty")
        for row in rows:
            if len(row.inputs) != len(self.domains):
                raise RuleLearningError("input arity does not match declared domains")
            if any(value not in domain
                   for value, domain in zip(row.inputs, self.domains)):
                raise RuleLearningError("input value is outside its declared domain")
        if len({row.inputs for row in rows}) != len(rows):
            raise RuleLearningError("duplicate input assignments are not allowed")
        return rows

    def fit(self, examples: Iterable[Example]) -> "CounterexampleRuleLearner":
        rows = self._validate(examples)
        candidate_count = 1
        for domain in self.domains:
            candidate_count *= len(domain) + 1  # None denotes an omitted literal.
        if candidate_count > self.max_candidates:
            raise RuleLearningError(
                f"candidate budget exceeded: {candidate_count} > {self.max_candidates}"
            )

        patterns = tuple(itertools.product(
            *((None, *domain) for domain in self.domains)
        ))
        labels = sorted({row.label for row in rows}, key=repr)
        selected: list[Clause] = []
        viable_count = 0
        uncovered_by_label: dict[str, int] = {}

        for label in labels:
            positive = {i for i, row in enumerate(rows) if row.label == label}
            negative = {i for i, row in enumerate(rows) if row.label != label}
            candidates: list[tuple[Pattern, frozenset[int]]] = []
            for pattern in patterns:
                covered = frozenset(
                    i for i in positive
                    if all(expected is None or expected == actual
                           for expected, actual in zip(pattern, rows[i].inputs))
                )
                if len(covered) < self.min_support:
                    continue
                if any(all(expected is None or expected == actual
                           for expected, actual in zip(pattern, rows[i].inputs))
                       for i in negative):
                    continue
                candidates.append((pattern, covered))
            viable_count += len(candidates)

            uncovered = set(positive)
            while uncovered:
                choices = [
                    (pattern, covered & uncovered)
                    for pattern, covered in candidates
                    if covered & uncovered
                ]
                if not choices:
                    break
                # Prefer maximum new coverage, then shorter descriptions,
                # then a stable representation for reproducible tie-breaking.
                pattern, newly_covered = min(
                    choices,
                    key=lambda item: (
                        -len(item[1]),
                        sum(value is not None for value in item[0]),
                        repr(item[0]),
                    ),
                )
                selected.append(Clause(pattern, label, len(newly_covered)))
                uncovered.difference_update(newly_covered)
            uncovered_by_label[repr(label)] = len(uncovered)

        self.clauses = tuple(selected)
        self.report = {
            "fitted": True,
            "training_examples": len(rows),
            "declared_variables": len(self.domains),
            "candidate_patterns_evaluated": len(patterns) * len(labels),
            "viable_patterns": viable_count,
            "selected_clauses": len(selected),
            "uncovered_training_examples_by_label": uncovered_by_label,
            "gradient_updates": 0,
            "search_space_size_per_label": len(patterns),
        }
        return self

    def predict(self, inputs: Sequence[Value]) -> Label | None:
        values = tuple(inputs)
        if len(values) != len(self.domains):
            raise RuleLearningError("input arity does not match declared domains")
        if any(value not in domain
               for value, domain in zip(values, self.domains)):
            return None
        matches = {clause.label for clause in self.clauses
                   if clause.matches(values)}
        return next(iter(matches)) if len(matches) == 1 else None

    def predict_many(self, inputs: Iterable[Sequence[Value]]) -> list[Label | None]:
        return [self.predict(values) for values in inputs]

    def snapshot(self) -> dict:
        return {
            "clauses": [
                {"pattern": list(clause.pattern), "label": clause.label,
                 "support_count": clause.support_count,
                 "literal_count": clause.literal_count}
                for clause in self.clauses
            ],
            "report": dict(self.report),
        }


def _demo_dataset() -> tuple[list[Example], list[Example]]:
    # Hidden target is a disjunction of two conjunctions; no coefficients or
    # target-rule identifier are passed to the learner.
    all_rows = list(itertools.product(range(3), repeat=3))
    def target(a: int, b: int, c: int) -> int:
        return int((a == b and c == 2) or (a == 2 and b == 0))
    labeled = [Example(row, target(*row)) for row in all_rows]
    train = [row for row in labeled if row.inputs not in {
        (0, 0, 2), (1, 1, 2), (2, 0, 0), (2, 0, 1)
    }]
    test = [row for row in labeled if row not in train]
    return train, test


def run_demo() -> dict:
    train, test = _demo_dataset()
    learner = CounterexampleRuleLearner((range(3), range(3), range(3)),
                                        min_support=2).fit(train)
    predictions = [learner.predict(row.inputs) for row in test]
    known = [(pred, row.label) for pred, row in zip(predictions, test)
             if pred is not None]
    return {
        "task": "hidden_disjunction_of_conjunctions",
        "train_examples": len(train),
        "heldout_examples": len(test),
        "heldout_coverage": len(known) / len(test),
        "heldout_accuracy_when_predicted": (
            sum(pred == gold for pred, gold in known) / len(known)
            if known else None
        ),
        "heldout_abstentions": len(test) - len(known),
        "learner": learner.snapshot(),
        "limitations": [
            "The conjunction DSL and variable domains are declared in advance.",
            "The hidden target is a synthetic finite task, not natural-language discovery.",
            "The greedy cover is not guaranteed to find a globally minimal rule set.",
            "Unseen overlaps and unsupported inputs are rejected."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_demo()
    print(json.dumps(result, indent=2, default=repr) if args.json else result)


if __name__ == "__main__":
    main()
