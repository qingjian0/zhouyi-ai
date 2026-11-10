"""E12-A4: bounded counterexample-triggered parameterized operator expansion.

A3 residual diagnosis supplies feature pairs; Train proposes thresholds; Gate validates.
This is a finite meta-operator family, not unrestricted primitive invention.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Literal

Kind = Literal["numeric"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: Kind = "numeric"


@dataclass(frozen=True)
class Observation:
    evidence_id: str
    values: tuple[tuple[str, float], ...]
    label: int

    def value(self, name: str) -> float:
        for key, value in self.values:
            if key == name:
                return value
        raise KeyError(name)


@dataclass(frozen=True)
class LearnerView:
    schema: tuple[FeatureSpec, ...]
    train: tuple[Observation, ...]
    gate: tuple[Observation, ...]
    # Pairs implicated by A3's residual/counterexample diagnosis.
    counterexample_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class OperatorCandidate:
    operator_id: str
    family: str
    left: str
    right: str
    threshold: float
    parent_primitives: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]

    def evaluate(self, left_value: float, right_value: float) -> int:
        return int(abs(left_value - right_value) > self.threshold)


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_view(view: LearnerView) -> None:
    names = [item.name for item in view.schema]
    if not names or any(not name for name in names) or len(names) != len(set(names)):
        raise ValueError("schema requires unique non-empty feature names")
    if any(item.kind != "numeric" for item in view.schema):
        raise TypeError("A4-P currently supports numeric features only")
    if not view.train or not view.gate:
        raise ValueError("Train and Gate must both be non-empty")
    for split_name, examples in (("Train", view.train), ("Gate", view.gate)):
        ids = [item.evidence_id for item in examples]
        if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError(f"{split_name} evidence IDs must be unique and non-empty")
        for example in examples:
            if example.label not in (0, 1):
                raise ValueError("labels must be binary")
            if len(example.values) != len(names) or {key for key, _ in example.values} != set(names):
                raise ValueError("each observation must contain exactly the schema features")
            if any(not _finite_number(value) for _, value in example.values):
                raise TypeError("all feature values must be finite numeric values")
    if {item.evidence_id for item in view.train} & {item.evidence_id for item in view.gate}:
        raise ValueError("Train/Gate evidence IDs must be disjoint")
    if not view.counterexample_pairs:
        raise ValueError("at least one A3-counterexample feature pair is required")
    canonical = [tuple(sorted(pair)) for pair in view.counterexample_pairs]
    if any(len(pair) != 2 or pair[0] == pair[1] or
           pair[0] not in names or pair[1] not in names for pair in canonical):
        raise ValueError("counterexample pairs must name two distinct schema features")
    if len(canonical) != len(set(canonical)):
        raise ValueError("counterexample pairs must be unique")


def _thresholds(values: list[float]) -> tuple[tuple[float, float, float], ...]:
    unique = sorted(set(values))
    result = []
    for lower, upper in zip(unique, unique[1:]):
        threshold = lower / 2.0 + upper / 2.0
        if math.isfinite(threshold) and lower < threshold < upper:
            result.append((threshold, lower, upper))
    return tuple(result)


def propose_operators(view: LearnerView) -> tuple[OperatorCandidate, ...]:
    """Propose ABS_DIFF_GT thresholds from Train, only for A3-flagged pairs."""
    validate_view(view)
    schema = {item.name: item for item in view.schema}
    result = []
    for left_name, right_name in sorted(tuple(sorted(pair)) for pair in view.counterexample_pairs):
        left, right = schema[left_name], schema[right_name]
        distances = [abs(item.value(left.name) - item.value(right.name)) for item in view.train]
        for threshold, lower, upper in _thresholds(distances):
            low_ids = [item.evidence_id for item in view.train
                       if abs(item.value(left.name) - item.value(right.name)) == lower]
            high_ids = [item.evidence_id for item in view.train
                        if abs(item.value(left.name) - item.value(right.name)) == upper]
            evidence_ids = tuple(sorted(set(low_ids + high_ids)))
            token = format(threshold, ".17g")
            result.append(OperatorCandidate(
                operator_id=f"op:abs-diff-gt:{left.name}:{right.name}:{token}",
                family="ABS_DIFF_GT", left=left.name, right=right.name,
                threshold=threshold,
                parent_primitives=("A3:numeric:pair", "META:threshold-separation"),
                source_evidence_ids=evidence_ids,
            ))
    return tuple(sorted(result, key=lambda item: item.operator_id))


def _consistent(candidate: OperatorCandidate, examples: tuple[Observation, ...]) -> bool:
    return all(candidate.evaluate(item.value(candidate.left), item.value(candidate.right)) == item.label
               for item in examples)


def infer(view: LearnerView, candidate_budget: int | None = None) -> dict:
    candidates = propose_operators(view)
    if candidate_budget is not None:
        if isinstance(candidate_budget, bool) or not isinstance(candidate_budget, int):
            raise TypeError("candidate_budget must be an integer")
        if candidate_budget < 0:
            raise ValueError("candidate_budget must be non-negative")
    evaluated = candidates if candidate_budget is None else candidates[:candidate_budget]
    train_ok = tuple(item for item in evaluated if _consistent(item, view.train))
    gate_ok = tuple(item for item in train_ok if _consistent(item, view.gate))
    if len(evaluated) < len(candidates):
        status, selected = "BUDGET_EXHAUSTED", None
    elif len(gate_ok) == 1:
        status, selected = "IDENTIFIABLE_WITHIN_A4_OPERATOR_FAMILY", gate_ok[0]
    elif len(gate_ok) > 1:
        status, selected = "AMBIGUOUS", None
    else:
        status, selected = "INCONSISTENT", None
    provenance = None if selected is None else {
        "operator_id": selected.operator_id,
        "family": selected.family,
        "parent_primitives": selected.parent_primitives,
        "source_evidence_ids": selected.source_evidence_ids,
        "validation_evidence_ids": tuple(sorted(item.evidence_id for item in view.gate)),
        "counterexample_pairs": tuple(sorted(tuple(sorted(pair)) for pair in view.counterexample_pairs)),
        "revision": "E12-A4-r0",
    }
    return {"status": status, "candidate_count": len(candidates),
            "evaluated_count": len(evaluated), "train_consistent_count": len(train_ok),
            "gate_consistent_count": len(gate_ok), "candidates": gate_ok,
            "selected": selected, "provenance": provenance}


def demo_view() -> LearnerView:
    schema = (FeatureSpec("x"), FeatureSpec("y"))
    train = (
        Observation("tr-01", (("x", 0), ("y", 1)), 0),
        Observation("tr-02", (("x", 0), ("y", 4)), 1),
        Observation("tr-03", (("x", 2), ("y", 3)), 0),
        Observation("tr-04", (("x", 1), ("y", 6)), 1),
        Observation("tr-05", (("x", 5), ("y", 7)), 0),
    )
    gate = (Observation("ga-01", (("x", 0), ("y", 5)), 1),
            Observation("ga-02", (("x", 3), ("y", 4)), 0))
    return LearnerView(schema, train, gate, (("x", "y"),))
