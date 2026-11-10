"""E12-A5-1: diagnose numeric feature pairs associated with A3 residuals.

Only prequential or out-of-fold predictions are accepted. The diagnosis uses
training records only; it does not inspect Gate or locked Test.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

PredictionMode = Literal["prequential", "out_of_fold"]


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: Literal["numeric"] = "numeric"


@dataclass(frozen=True)
class ResidualRecord:
    evidence_id: str
    values: tuple[tuple[str, float], ...]
    label: int
    a3_prediction: int


@dataclass(frozen=True)
class ResidualView:
    schema: tuple[FeatureSpec, ...]
    records: tuple[ResidualRecord, ...]
    prediction_mode: PredictionMode
    model_version: str


@dataclass(frozen=True)
class PairDiagnosis:
    left: str
    right: str
    threshold: float
    polarity: Literal["HIGH_ERROR", "LOW_ERROR"]
    balanced_accuracy: float
    error_support: int
    correct_support: int
    low_side_support: int
    high_side_support: int
    evidence_ids: tuple[str, ...]


def _finite_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def validate_view(view: ResidualView) -> None:
    names = [spec.name for spec in view.schema]
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("schema requires non-empty feature names")
    if len(names) != len(set(names)):
        raise ValueError("schema feature names must be unique")
    if len(names) < 2:
        raise ValueError("at least two features are required")
    if any(spec.kind != "numeric" for spec in view.schema):
        raise TypeError("A5-1 currently diagnoses numeric feature pairs only")
    if view.prediction_mode not in ("prequential", "out_of_fold"):
        raise ValueError("in-sample predictions are forbidden for residual diagnosis")
    if not isinstance(view.model_version, str) or not view.model_version:
        raise ValueError("model_version must be a non-empty string")
    if not view.records:
        raise ValueError("residual records must be non-empty")
    ids = [record.evidence_id for record in view.records]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("evidence IDs must be unique and non-empty")
    for record in view.records:
        if record.label not in (0, 1) or record.a3_prediction not in (0, 1):
            raise ValueError("labels and A3 predictions must be binary")
        if len(record.values) != len(names) or {key for key, _ in record.values} != set(names):
            raise ValueError("each record must contain exactly the schema features")
        if any(not _finite_number(value) for _, value in record.values):
            raise TypeError("all feature values must be finite numeric values")
    residuals = {int(record.a3_prediction != record.label) for record in view.records}
    if residuals != {0, 1}:
        raise ValueError("diagnosis requires both correct and incorrect A3 predictions")


def _balanced_accuracy(actual: list[int], predicted: list[int]) -> float:
    positives = [i for i, value in enumerate(actual) if value == 1]
    negatives = [i for i, value in enumerate(actual) if value == 0]
    if not positives or not negatives:
        return 0.0
    sensitivity = sum(predicted[i] == 1 for i in positives) / len(positives)
    specificity = sum(predicted[i] == 0 for i in negatives) / len(negatives)
    return (sensitivity + specificity) / 2.0


def _pair_best(view: ResidualView, left: str, right: str,
               min_side_support: int) -> PairDiagnosis | None:
    residual = [int(item.a3_prediction != item.label) for item in view.records]
    distances = [abs(item.value(left) - item.value(right)) for item in view.records]
    unique = sorted(set(distances))
    best: PairDiagnosis | None = None
    for lower, upper in zip(unique, unique[1:]):
        threshold = lower / 2.0 + upper / 2.0
        if not math.isfinite(threshold) or not lower < threshold < upper:
            continue
        high = [int(value > threshold) for value in distances]
        low_support = len(high) - sum(high)
        high_support = sum(high)
        if min(low_support, high_support) < min_side_support:
            continue
        for polarity, predicted in (("HIGH_ERROR", high),
                                    ("LOW_ERROR", [1 - value for value in high])):
            score = _balanced_accuracy(residual, predicted)
            candidate = PairDiagnosis(
                left=left, right=right, threshold=threshold, polarity=polarity,
                balanced_accuracy=score,
                error_support=sum(residual), correct_support=len(residual) - sum(residual),
                low_side_support=low_support, high_side_support=high_support,
                evidence_ids=tuple(sorted(item.evidence_id for item in view.records)),
            )
            if best is None or (candidate.balanced_accuracy, -candidate.threshold,
                                candidate.polarity) > (best.balanced_accuracy, -best.threshold,
                                                       best.polarity):
                best = candidate
    return best


def diagnose_pairs(view: ResidualView, *, min_side_support: int = 2,
                   min_balanced_accuracy: float = 0.65,
                   top_k: int = 3) -> dict:
    """Rank Train-only numeric pairs by out-of-sample residual separability."""
    validate_view(view)
    if isinstance(min_side_support, bool) or not isinstance(min_side_support, int):
        raise TypeError("min_side_support must be an integer")
    if min_side_support < 1:
        raise ValueError("min_side_support must be positive")
    if (isinstance(min_balanced_accuracy, bool)
            or not isinstance(min_balanced_accuracy, (int, float))
            or not math.isfinite(min_balanced_accuracy)
            or not 0.5 <= min_balanced_accuracy <= 1.0):
        raise ValueError("min_balanced_accuracy must be finite and in [0.5, 1]")
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("top_k must be an integer")
    if top_k < 1:
        raise ValueError("top_k must be positive")

    ranked = []
    for index, left in enumerate(view.schema):
        for right in view.schema[index + 1:]:
            candidate = _pair_best(view, left.name, right.name, min_side_support)
            if candidate is not None and candidate.balanced_accuracy >= min_balanced_accuracy:
                ranked.append(candidate)
    ranked.sort(key=lambda item: (-item.balanced_accuracy, item.left, item.right,
                                  item.threshold, item.polarity))
    selected = tuple(ranked[:top_k])
    return {
        "status": "DIAGNOSED" if selected else "NO_SUPPORTED_PAIR",
        "prediction_mode": view.prediction_mode,
        "model_version": view.model_version,
        "record_count": len(view.records),
        "residual_count": sum(item.a3_prediction != item.label for item in view.records),
        "candidate_pair_count": len(view.schema) * (len(view.schema) - 1) // 2,
        "qualified_pair_count": len(ranked),
        "diagnoses": selected,
        # A4 can consume these pairs directly; caller must retain this result as provenance.
        "counterexample_pairs": tuple((item.left, item.right) for item in selected),
    }
