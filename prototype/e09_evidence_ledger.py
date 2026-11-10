"""Append-only evidence ledger for E09 symbolic learners.

Evidence IDs are idempotent. Contradictory labels for the same input do not
overwrite one another: that input is quarantined from training until reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example, RuleLearningError,
)

Value = Hashable
Label = Hashable


class EvidenceError(ValueError):
    """Invalid or conflicting evidence-ledger operation."""


@dataclass(frozen=True)
class EvidenceRecord:
    sample_id: str
    example: Example
    source: str = ""


class EvidenceLedger:
    """In-memory append-only ledger with deterministic conflict adjudication."""

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        self._order: list[str] = []

    def append(self, sample_id: str, example: Example, *,
               source: str = "") -> bool:
        if not sample_id or not isinstance(sample_id, str):
            raise EvidenceError("sample_id must be a non-empty string")
        candidate = EvidenceRecord(sample_id, example, source)
        existing = self._records.get(sample_id)
        if existing is not None:
            if existing == candidate:
                return False
            raise EvidenceError("sample_id is immutable and already has other content")
        self._records[sample_id] = candidate
        self._order.append(sample_id)
        return True

    def extend(self, records: Iterable[EvidenceRecord]) -> int:
        added = 0
        for record in records:
            added += int(self.append(record.sample_id, record.example,
                                     source=record.source))
        return added

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records[sample_id] for sample_id in self._order)

    def adjudication(self) -> dict:
        labels_by_input: dict[tuple[Value, ...], set[Label]] = {}
        ids_by_input: dict[tuple[Value, ...], list[str]] = {}
        for record in self.records():
            key = record.example.inputs
            labels_by_input.setdefault(key, set()).add(record.example.label)
            ids_by_input.setdefault(key, []).append(record.sample_id)
        contested = {key for key, labels in labels_by_input.items()
                     if len(labels) > 1}
        repeated = {key for key, ids in ids_by_input.items() if len(ids) > 1}
        return {
            "total_records": len(self._records),
            "unique_inputs": len(labels_by_input),
            "contested_inputs": len(contested),
            "repeated_same_label_inputs": len(repeated - contested),
            "contested": [
                {"inputs": list(key), "labels": sorted(labels, key=repr),
                 "sample_ids": ids_by_input[key]}
                for key, labels in sorted(contested.items(), key=lambda item: repr(item[0]))
            ],
        }

    def training_examples(self) -> tuple[Example, ...]:
        labels_by_input: dict[tuple[Value, ...], set[Label]] = {}
        for record in self.records():
            labels_by_input.setdefault(record.example.inputs, set()).add(
                record.example.label
            )
        clean = []
        for key, labels in labels_by_input.items():
            if len(labels) == 1:
                clean.append(Example(key, next(iter(labels))))
        return tuple(clean)

    def fit(self, learner: CounterexampleRuleLearner) -> CounterexampleRuleLearner:
        examples = self.training_examples()
        if not examples:
            raise EvidenceError("no uncontested evidence is available for fitting")
        try:
            return learner.fit(examples)
        except RuleLearningError as exc:
            raise EvidenceError(f"learner rejected adjudicated evidence: {exc}") from exc

    def snapshot(self) -> dict:
        return {
            "records": [
                {"sample_id": r.sample_id, "inputs": list(r.example.inputs),
                 "label": r.example.label, "source": r.source}
                for r in self.records()
            ],
            "adjudication": self.adjudication(),
            "training_example_count": len(self.training_examples()),
        }
