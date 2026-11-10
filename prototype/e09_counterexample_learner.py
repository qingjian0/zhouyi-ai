"""E09-B: counterexample-driven rule induction without gradient updates.

The learner searches a declared finite DSL of conjunctions over categorical
variables. Unsupported or conflicting predictions are rejected. This is a
bounded symbolic learner, not a claim of open-ended autonomous discovery.
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
    """Invalid evidence or search-space configuration."""


@dataclass(frozen=True)
class Clause:
    pattern: Pattern
    label: Label
    support_count: int

    @property
    def literal_count(self) -> int:
        return sum(value is not None for value in self.pattern)

    def matches(self, inputs: tuple[Value, ...]) -> bool:
        return all(want is None or want == got
                   for want, got in zip(self.pattern, inputs))


class CounterexampleRuleLearner:
    """Greedy cover learner; a new counterexample invalidates unsafe clauses."""

    def __init__(self, domains: Sequence[Sequence[Value]], *,
                 min_support: int = 2, max_candidates: int = 100_000) -> None:
        self.domains = tuple(tuple(dict.fromkeys(d)) for d in domains)
        if not self.domains or any(not d for d in self.domains):
            raise RuleLearningError("every variable needs a non-empty domain")
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
        seen = set()
        for row in rows:
            if len(row.inputs) != len(self.domains):
                raise RuleLearningError("input arity does not match declared domains")
            if any(v not in d for v, d in zip(row.inputs, self.domains)):
                raise RuleLearningError("input value is outside its declared domain")
            if row.inputs in seen:
                raise RuleLearningError("duplicate input assignments are not allowed")
            seen.add(row.inputs)
        return rows

    def fit(self, examples: Iterable[Example]) -> "CounterexampleRuleLearner":
        rows = self._validate(examples)
        space_size = 1
        for domain in self.domains:
            space_size *= len(domain) + 1
        labels = sorted({r.label for r in rows}, key=repr)
        total_evaluations = space_size * len(labels)
        if total_evaluations > self.max_candidates:
            raise RuleLearningError(
                "candidate evaluation budget exceeded: "
                f"{total_evaluations} > {self.max_candidates} "
                f"({space_size} patterns x {len(labels)} labels)"
            )
        patterns = tuple(itertools.product(
            *((None, *domain) for domain in self.domains)
        ))
        selected: list[Clause] = []
        viable_count = 0
        uncovered_by_label = {}

        for label in labels:
            positive = {i for i, row in enumerate(rows) if row.label == label}
            negative = {i for i, row in enumerate(rows) if row.label != label}
            candidates = []
            for pattern in patterns:
                def matches(index: int) -> bool:
                    return all(want is None or want == got
                               for want, got in zip(pattern, rows[index].inputs))
                covered = frozenset(i for i in positive if matches(i))
                if len(covered) < self.min_support:
                    continue
                if any(matches(i) for i in negative):
                    continue
                candidates.append((pattern, covered))
            viable_count += len(candidates)
            uncovered = set(positive)
            while uncovered:
                choices = [(p, covered & uncovered) for p, covered in candidates
                           if covered & uncovered]
                if not choices:
                    break
                pattern, new = min(
                    choices,
                    key=lambda item: (-len(item[1]),
                                      sum(v is not None for v in item[0]),
                                      repr(item[0])),
                )
                selected.append(Clause(pattern, label, len(new)))
                uncovered.difference_update(new)
            uncovered_by_label[repr(label)] = len(uncovered)

        self.clauses = tuple(selected)
        self.report = {
            "fitted": True,
            "training_examples": len(rows),
            "declared_variables": len(self.domains),
            "candidate_patterns_evaluated": total_evaluations,
            "candidate_evaluation_budget": self.max_candidates,
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
        if any(v not in d for v, d in zip(values, self.domains)):
            return None
        labels = {c.label for c in self.clauses if c.matches(values)}
        return next(iter(labels)) if len(labels) == 1 else None

    def snapshot(self) -> dict:
        return {
            "clauses": [
                {"pattern": list(c.pattern), "label": c.label,
                 "support_count": c.support_count,
                 "literal_count": c.literal_count}
                for c in self.clauses
            ],
            "report": dict(self.report),
        }


def _demo_dataset() -> tuple[list[Example], list[Example]]:
    # Hidden target: (a == 1 AND c == 2) OR (a == 2 AND b == 0).
    # The learner receives only labeled examples, not this expression.
    all_rows = list(itertools.product(range(3), repeat=3))
    def target(a: int, b: int, c: int) -> int:
        return int((a == 1 and c == 2) or (a == 2 and b == 0))
    labeled = [Example(row, target(*row)) for row in all_rows]
    heldout_inputs = {(1, 0, 2), (2, 0, 0), (0, 0, 0), (0, 1, 1)}
    train = [row for row in labeled if row.inputs not in heldout_inputs]
    test = [row for row in labeled if row.inputs in heldout_inputs]
    return train, test


def run_demo() -> dict:
    train, test = _demo_dataset()
    learner = CounterexampleRuleLearner((range(3), range(3), range(3)),
                                        min_support=2).fit(train)
    predictions = [learner.predict(row.inputs) for row in test]
    known = [(p, row.label) for p, row in zip(predictions, test) if p is not None]
    return {
        "task": "hidden_disjunction_of_conjunctions",
        "train_examples": len(train),
        "heldout_examples": len(test),
        "heldout_coverage": len(known) / len(test),
        "heldout_accuracy_when_predicted": (
            sum(p == gold for p, gold in known) / len(known) if known else None
        ),
        "heldout_abstentions": len(test) - len(known),
        "learner": learner.snapshot(),
        "limitations": [
            "The conjunction DSL and variable domains are declared in advance.",
            "This is a synthetic finite task, not natural-language discovery.",
            "Greedy cover is not guaranteed to find a globally minimal rule set.",
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
