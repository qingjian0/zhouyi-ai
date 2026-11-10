"""Append-only evidence ledger for E09 symbolic learners.

Evidence IDs are idempotent. Contradictory labels for the same input do not
overwrite one another: that input is quarantined from training until reviewed.
Source IDs are provenance labels, not cryptographic identity or trust proofs.
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
    source_id: str = ""


class EvidenceLedger:
    """In-memory append-only ledger with conservative conflict adjudication."""

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        self._order: list[str] = []

    @staticmethod
    def _validate_record(record: EvidenceRecord) -> None:
        if not isinstance(record.sample_id, str) or not record.sample_id.strip():
            raise EvidenceError("sample_id must be a non-empty string")
        if not isinstance(record.source, str) or not isinstance(record.source_id, str):
            raise EvidenceError("source and source_id must be strings")
        if not isinstance(record.example, Example):
            raise EvidenceError("record.example must be an Example")

    def append(self, sample_id: str, example: Example, *,
               source: str = "", source_id: str = "") -> bool:
        candidate = EvidenceRecord(sample_id, example, source, source_id)
        self._validate_record(candidate)
        existing = self._records.get(sample_id)
        if existing is not None:
            if existing == candidate:
                return False
            raise EvidenceError("sample_id is immutable and already has other content")
        self._records[sample_id] = candidate
        self._order.append(sample_id)
        return True

    def extend(self, records: Iterable[EvidenceRecord]) -> int:
        """Atomically append a batch; any invalid/conflicting ID rejects all."""
        batch = tuple(records)
        staged: dict[str, EvidenceRecord] = {}
        for record in batch:
            self._validate_record(record)
            existing = staged.get(record.sample_id, self._records.get(record.sample_id))
            if existing is not None and existing != record:
                raise EvidenceError(
                    "sample_id is immutable and batch contains conflicting content"
                )
            staged[record.sample_id] = record
        added = 0
        for sample_id, record in staged.items():
            if sample_id not in self._records:
                self._records[sample_id] = record
                self._order.append(sample_id)
                added += 1
        return added

    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records[sample_id] for sample_id in self._order)

    def adjudication(self) -> dict:
        labels_by_input: dict[tuple[Value, ...], set[Label]] = {}
        ids_by_input: dict[tuple[Value, ...], list[str]] = {}
        sources_by_input_label: dict[
            tuple[tuple[Value, ...], Label], set[str]
        ] = {}
        unknown_source_records: dict[tuple[Value, ...], int] = {}
        for record in self.records():
            key = record.example.inputs
            label = record.example.label
            labels_by_input.setdefault(key, set()).add(label)
            ids_by_input.setdefault(key, []).append(record.sample_id)
            if record.source_id.strip():
                sources_by_input_label.setdefault((key, label), set()).add(
                    record.source_id
                )
            else:
                unknown_source_records[key] = unknown_source_records.get(key, 0) + 1

        contested = {key for key, labels in labels_by_input.items()
                     if len(labels) > 1}
        repeated = {key for key, ids in ids_by_input.items() if len(ids) > 1}
        source_evidence = []
        for key in sorted(labels_by_input, key=repr):
            by_label = []
            for label in sorted(labels_by_input[key], key=repr):
                source_ids = sorted(sources_by_input_label.get((key, label), set()))
                by_label.append({
                    "label": label,
                    "distinct_source_ids": len(source_ids),
                    "source_ids": source_ids,
                })
            source_evidence.append({
                "inputs": list(key),
                "labels": by_label,
                "records_without_source_id": unknown_source_records.get(key, 0),
            })
        return {
            "total_records": len(self._records),
            "unique_inputs": len(labels_by_input),
            "contested_inputs": len(contested),
            "repeated_same_label_inputs": len(repeated - contested),
            "source_evidence": source_evidence,
            "contested": [
                {"inputs": list(key), "labels": sorted(labels_by_input[key], key=repr),
                 "sample_ids": ids_by_input[key]}
                for key in sorted(contested, key=repr)
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
                 "label": r.example.label, "source": r.source,
                 "source_id": r.source_id}
                for r in self.records()
            ],
            "adjudication": self.adjudication(),
            "training_example_count": len(self.training_examples()),
        }
