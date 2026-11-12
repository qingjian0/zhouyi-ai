"""Evaluation primitives for semantic extraction quality and abstention.

This module scores extractor outputs against explicitly annotated gold cases.
It does not implement extraction, grounding, truth adjudication, or model
training. Candidate correctness is exact structural match on kind, canonical
key, and ordered role bindings; surface-form similarity is deliberately not
silently treated as semantic correctness.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Iterable

from prototype.observation_contract import SemanticUnitCandidate, UnitKind


@dataclass(frozen=True)
class GoldSemanticUnit:
    kind: UnitKind
    canonical_key: str
    role_bindings: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, UnitKind):
            raise TypeError("gold kind must be UnitKind")
        if not isinstance(self.canonical_key, str) or not self.canonical_key.strip():
            raise ValueError("gold canonical_key must be non-empty")
        if any(
            not isinstance(role, str) or not role.strip()
            or not isinstance(target, str) or not target.strip()
            for role, target in self.role_bindings
        ):
            raise ValueError("gold role bindings must contain non-empty role/target pairs")
        roles = [role for role, _ in self.role_bindings]
        if len(roles) != len(set(roles)):
            raise ValueError("gold role names must be unique")


@dataclass(frozen=True)
class ExtractionGoldCase:
    case_id: str
    domain: str
    expected_units: tuple[GoldSemanticUnit, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if not isinstance(self.domain, str) or not self.domain.strip():
            raise ValueError("domain must be non-empty")
        if any(not isinstance(unit, GoldSemanticUnit) for unit in self.expected_units):
            raise TypeError("expected_units must contain GoldSemanticUnit values")


@dataclass(frozen=True)
class ExtractionPrediction:
    case_id: str
    candidates: tuple[SemanticUnitCandidate, ...]
    abstained: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("prediction case_id must be non-empty")
        if not isinstance(self.abstained, bool):
            raise TypeError("abstained must be bool")
        if any(not isinstance(item, SemanticUnitCandidate) for item in self.candidates):
            raise TypeError("candidates must contain SemanticUnitCandidate values")
        if self.abstained and self.candidates:
            raise ValueError("an abstaining prediction cannot contain candidates")


def _gold_key(unit: GoldSemanticUnit) -> tuple:
    # Role order is semantic: never sort or normalize the role sequence.
    return (unit.kind.value, unit.canonical_key, unit.role_bindings)


def _prediction_key(candidate: SemanticUnitCandidate) -> tuple | None:
    key = candidate.canonical_key
    if not isinstance(key, str) or not key.strip():
        return None
    roles = tuple((binding.role_name, binding.target_ref) for binding in candidate.role_bindings)
    return (candidate.kind.value, key, roles)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _calibration_summary(observations: list[tuple[float, bool]], bins: int) -> dict:
    if not observations:
        return {
            "count": 0, "brier_score": None, "expected_calibration_error": None,
            "bins": [],
        }
    brier = sum((confidence - float(correct)) ** 2 for confidence, correct in observations) / len(observations)
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for confidence, correct in observations:
        index = min(int(confidence * bins), bins - 1)
        buckets[index].append((confidence, correct))
    rendered = []
    ece = 0.0
    for index, bucket in enumerate(buckets):
        if bucket:
            mean_confidence = sum(x[0] for x in bucket) / len(bucket)
            accuracy = sum(float(x[1]) for x in bucket) / len(bucket)
            ece += len(bucket) / len(observations) * abs(mean_confidence - accuracy)
        else:
            mean_confidence = None
            accuracy = None
        rendered.append({
            "lower_bound": index / bins,
            "upper_bound": (index + 1) / bins,
            "count": len(bucket),
            "mean_confidence": mean_confidence,
            "empirical_accuracy": accuracy,
        })
    return {
        "count": len(observations),
        "brier_score": brier,
        "expected_calibration_error": ece,
        "bins": rendered,
    }


def evaluate_extraction_cases(
    gold_cases: Iterable[ExtractionGoldCase],
    predictions: Iterable[ExtractionPrediction],
    *,
    calibration_bins: int = 10,
) -> dict:
    """Return deterministic micro, abstention, calibration and per-domain metrics.

    A candidate is correct only when (kind, canonical_key, ordered role bindings)
    exactly matches one gold unit. Candidate confidence is evaluated only when
    supplied; missing confidence is counted, not imputed. ECE uses fixed-width
    bins and is descriptive, so callers should also inspect sample counts.
    """
    if isinstance(calibration_bins, bool) or not isinstance(calibration_bins, int) or calibration_bins < 1:
        raise ValueError("calibration_bins must be a positive integer")
    cases = tuple(gold_cases)
    predicted = tuple(predictions)
    gold_by_id = {case.case_id: case for case in cases}
    if len(gold_by_id) != len(cases):
        raise ValueError("gold case IDs must be unique")
    prediction_by_id = {item.case_id: item for item in predicted}
    if len(prediction_by_id) != len(predicted):
        raise ValueError("prediction case IDs must be unique")
    if set(prediction_by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(prediction_by_id))
        extra = sorted(set(prediction_by_id) - set(gold_by_id))
        raise ValueError(f"prediction coverage mismatch: missing={missing}, extra={extra}")

    totals = Counter()
    abstention = Counter()
    confidence_observations: list[tuple[float, bool]] = []
    missing_confidence = 0
    domain_counts: dict[str, Counter] = {}

    for case in cases:
        prediction = prediction_by_id[case.case_id]
        gold_counter = Counter(_gold_key(unit) for unit in case.expected_units)
        prediction_keys = [_prediction_key(candidate) for candidate in prediction.candidates]
        prediction_counter = Counter(key for key in prediction_keys if key is not None)
        matched = gold_counter & prediction_counter
        tp = sum(matched.values())
        fp = len(prediction.candidates) - tp
        fn = sum(gold_counter.values()) - tp
        invalid = sum(key is None for key in prediction_keys)
        totals.update({"tp": tp, "fp": fp, "fn": fn, "invalid": invalid})
        domain_counts.setdefault(case.domain, Counter()).update({"tp": tp, "fp": fp, "fn": fn})

        gold_requires_abstention = not case.expected_units
        if prediction.abstained and gold_requires_abstention:
            abstention["tp"] += 1
        elif prediction.abstained:
            abstention["fp"] += 1
        elif gold_requires_abstention:
            abstention["fn"] += 1

        remaining = gold_counter.copy()
        for candidate, key in zip(prediction.candidates, prediction_keys):
            correct = False
            if key is not None and remaining[key] > 0:
                remaining[key] -= 1
                correct = True
            if candidate.extractor_confidence is None:
                missing_confidence += 1
            else:
                confidence = float(candidate.extractor_confidence)
                if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                    raise ValueError("candidate extractor_confidence must be finite in [0, 1]")
                confidence_observations.append((confidence, correct))

    unit_metrics = _prf(totals["tp"], totals["fp"], totals["fn"])
    abstention_metrics = _prf(
        abstention["tp"], abstention["fp"], abstention["fn"],
    )
    case_count = len(cases)
    abstained_cases = sum(item.abstained for item in predicted)
    by_domain = {}
    for domain in sorted(domain_counts):
        counts = domain_counts[domain]
        by_domain[domain] = {
            "case_count": sum(case.domain == domain for case in cases),
            "true_positive": counts["tp"],
            "false_positive": counts["fp"],
            "false_negative": counts["fn"],
            **_prf(counts["tp"], counts["fp"], counts["fn"]),
        }
    return {
        "case_count": case_count,
        "unit": {
            "true_positive": totals["tp"],
            "false_positive": totals["fp"],
            "false_negative": totals["fn"],
            "invalid_predictions": totals["invalid"],
            **unit_metrics,
        },
        "abstention": {
            "true_positive": abstention["tp"],
            "false_positive": abstention["fp"],
            "false_negative": abstention["fn"],
            "abstained_cases": abstained_cases,
            "abstention_rate": _ratio(abstained_cases, case_count),
            "coverage": _ratio(case_count - abstained_cases, case_count),
            **abstention_metrics,
        },
        "calibration": {
            **_calibration_summary(confidence_observations, calibration_bins),
            "predictions_without_confidence": missing_confidence,
        },
        "by_domain": by_domain,
        "matching": "exact kind + canonical_key + ordered role_bindings",
    }
