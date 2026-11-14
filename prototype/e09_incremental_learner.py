"""Incremental conjunction learner for E09-B.

Maintains sufficient statistics only for conjunction patterns matched by each
new observation. It does not enumerate the full Cartesian pattern space or
refit from historical rows after each update.
"""
from __future__ import annotations

import itertools
from typing import Hashable, Sequence

Value = Hashable
Label = Hashable
Pattern = tuple[Value | None, ...]


class IncrementalLearningError(ValueError):
    """Invalid incremental evidence or query."""


class IncrementalConjunctionLearner:
    """Sound conjunction rules with O(2**arity) local evidence updates.

    A pattern is predictive for label L when at least min_support distinct,
    uncontested inputs match it and every matching input has label L.
    Multiple labels matching a query cause abstention.
    """

    def __init__(self, domains: Sequence[Sequence[Value]], *,
                 min_support: int = 2) -> None:
        self.domains = tuple(tuple(dict.fromkeys(d)) for d in domains)
        if not self.domains or any(not d for d in self.domains):
            raise IncrementalLearningError(
                "every variable needs a non-empty domain"
            )
        if min_support < 1:
            raise IncrementalLearningError("min_support must be positive")
        self.min_support = min_support
        self._labels_by_input: dict[tuple[Value, ...], set[Label]] = {}
        self._total: dict[Pattern, int] = {}
        self._by_label: dict[Pattern, dict[Label, int]] = {}
        self._updates = 0
        self._touched = 0
        self._retractions = 0

    def _validate_inputs(self, inputs: Sequence[Value]) -> tuple[Value, ...]:
        values = tuple(inputs)
        if len(values) != len(self.domains):
            raise IncrementalLearningError(
                "input arity does not match declared domains"
            )
        if any(v not in domain for v, domain in zip(values, self.domains)):
            raise IncrementalLearningError(
                "input value is outside its declared domain"
            )
        return values

    @staticmethod
    def _matching_patterns(values: tuple[Value, ...]):
        # Each dimension is either constrained to its observed value or
        # omitted. This visits exactly the 2**arity patterns matching a row.
        return itertools.product(*((None, value) for value in values))

    def _adjust(self, values: tuple[Value, ...], label: Label, delta: int) -> None:
        for pattern_tuple in self._matching_patterns(values):
            pattern = tuple(pattern_tuple)
            total = self._total.get(pattern, 0) + delta
            label_counts = self._by_label.setdefault(pattern, {})
            by_label = label_counts.get(label, 0) + delta
            if total < 0 or by_label < 0:
                raise IncrementalLearningError("internal evidence count underflow")
            if total:
                self._total[pattern] = total
            else:
                self._total.pop(pattern, None)
            if by_label:
                label_counts[label] = by_label
            else:
                label_counts.pop(label, None)
            if not label_counts:
                self._by_label.pop(pattern, None)
            self._touched += 1

    def observe(self, inputs: Sequence[Value], label: Label) -> str:
        """Append a label observation; conflicting inputs are retracted."""
        values = self._validate_inputs(inputs)
        known = self._labels_by_input.get(values)
        if known is None:
            self._labels_by_input[values] = {label}
            self._adjust(values, label, +1)
            self._updates += 1
            return "ADDED"
        if label in known:
            return "DUPLICATE"
        if len(known) == 1:
            previous = next(iter(known))
            self._adjust(values, previous, -1)
            self._retractions += 1
        known.add(label)
        self._updates += 1
        return "CONTESTED"

    def predict(self, inputs: Sequence[Value]) -> Label | None:
        values = self._validate_inputs(inputs)
        labels = set()
        for pattern_tuple in self._matching_patterns(values):
            pattern = tuple(pattern_tuple)
            total = self._total.get(pattern, 0)
            if total < self.min_support:
                continue
            for label, count in self._by_label.get(pattern, {}).items():
                if count == total:
                    labels.add(label)
        return next(iter(labels)) if len(labels) == 1 else None

    @property
    def report(self) -> dict:
        return {
            "fitted": bool(self._labels_by_input),
            "training_examples": sum(
                len(labels) == 1 for labels in self._labels_by_input.values()
            ),
            "candidate_patterns_evaluated": self._touched,
            "incremental_pattern_updates": self._touched,
            "unique_observations": len(self._labels_by_input),
            "contested_inputs": sum(
                len(labels) > 1 for labels in self._labels_by_input.values()
            ),
            "retracted_contributions": self._retractions,
            "gradient_updates": 0,
        }

    def snapshot(self) -> dict:
        return {
            "min_support": self.min_support,
            "observations": [
                {"inputs": list(inputs), "labels": sorted(labels, key=repr)}
                for inputs, labels in sorted(
                    self._labels_by_input.items(), key=lambda item: repr(item[0])
                )
            ],
            "pattern_statistics": [
                {
                    "pattern": list(pattern),
                    "total": total,
                    "labels": [
                        {"label": label, "count": count}
                        for label, count in sorted(
                            self._by_label.get(pattern, {}).items(),
                            key=lambda item: repr(item[0])
                        )
                    ],
                }
                for pattern, total in sorted(
                    self._total.items(), key=lambda item: repr(item[0])
                )
            ],
            "report": dict(self.report),
        }
