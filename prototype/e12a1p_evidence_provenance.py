"""E12-A1.1: immutable evidence and predicate provenance wrapper.

Provenance records where a candidate came from; it does not establish causality.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Literal

from prototype.e12a1_typed_predicate_induction import (
    Example, FeatureSpec, LearnerView, Predicate, infer, propose_predicates,
)

Split = Literal["train", "gate"]
GENERATOR_VERSION = "e12a1-predicate-generator/1"


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    split: Split
    example: Example
    schema_version: str


def _scalar_key(value: object) -> str:
    # JSON encoding distinguishes strings, integers, and floats deterministically.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def predicate_id(predicate: Predicate, generator_version: str = GENERATOR_VERSION) -> str:
    payload = {
        "feature": predicate.feature,
        "input_kind": predicate.input_kind,
        "operator": predicate.operator,
        "threshold": predicate.threshold,
        "generator_version": generator_version,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "predicate:" + encoded


def _support_ids(predicate: Predicate, records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    values = sorted({r.example.value(predicate.feature) for r in records}, key=_scalar_key)
    if predicate.input_kind == "categorical" or predicate.operator == "EQ":
        return tuple(r.evidence_id for r in records
                     if r.example.value(predicate.feature) == predicate.threshold)
    if predicate.operator in ("GE", "GT", "LE", "LT"):
        nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        pairs = [(a, b) for a, b in zip(nums, nums[1:])
                 if (a + b) / 2 == predicate.threshold]
        anchors = {v for pair in pairs for v in pair}
        return tuple(r.evidence_id for r in records if r.example.value(predicate.feature) in anchors)
    if predicate.operator == "PARITY":
        return tuple(r.evidence_id for r in records)
    return ()


def infer_with_provenance(
    schema: tuple[FeatureSpec, ...],
    train: tuple[EvidenceRecord, ...],
    gate: tuple[EvidenceRecord, ...],
    candidate_budget: int | None = None,
    schema_version: str = "schema/1",
) -> dict:
    """Infer from explicitly identified evidence and return immutable lineage."""
    if not schema_version:
        raise ValueError("schema_version must be non-empty")
    records = train + gate
    ids = [r.evidence_id for r in records]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("evidence IDs must be non-empty and globally unique")
    for record, expected_split in ((r, "train") for r in train):
        if record.split != expected_split:
            raise ValueError("Train evidence has incorrect split")
    for record, expected_split in ((r, "gate") for r in gate):
        if record.split != expected_split:
            raise ValueError("Gate evidence has incorrect split")
    if any(r.schema_version != schema_version for r in records):
        raise ValueError("evidence schema_version mismatch")

    view = LearnerView(
        schema=schema,
        train=tuple(r.example for r in train),
        gate=tuple(r.example for r in gate),
    )
    base = infer(view, candidate_budget)
    all_candidates = propose_predicates(view)
    evaluated = all_candidates if candidate_budget is None else all_candidates[:candidate_budget]
    train_ok = {p for p in evaluated if all(
        p.evaluate(r.example.value(p.feature)) == r.example.label for r in train
    )}
    gate_ok = {p for p in train_ok if all(
        p.evaluate(r.example.value(p.feature)) == r.example.label for r in gate
    )}
    candidate_rows = []
    for predicate in evaluated:
        candidate_rows.append({
            "candidate_id": predicate_id(predicate),
            "predicate": asdict(predicate),
            "generator_version": GENERATOR_VERSION,
            "schema_version": schema_version,
            "support_evidence_ids": list(_support_ids(predicate, train)),
            "train_consistent": predicate in train_ok,
            "gate_consistent": predicate in gate_ok,
            "gate_evidence_ids": [r.evidence_id for r in gate] if predicate in train_ok else [],
        })
    selected_id = predicate_id(base["selected"]) if base["selected"] is not None else None
    return {
        "status": base["status"],
        "candidate_count": base["candidate_count"],
        "evaluated_count": base["evaluated_count"],
        "train_consistent_count": base["train_consistent_count"],
        "gate_consistent_count": base["gate_consistent_count"],
        "selected_candidate_id": selected_id,
        "generator_version": GENERATOR_VERSION,
        "schema_version": schema_version,
        "evidence_lineage": {
            "train_evidence_ids": [r.evidence_id for r in train],
            "gate_evidence_ids": [r.evidence_id for r in gate],
        },
        "candidates": candidate_rows,
        "provenance_caveat": "Evidence lineage records derivation and evaluation sources; it does not establish causal validity.",
    }
