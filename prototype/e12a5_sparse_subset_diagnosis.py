"""E12-A5-2b: sparse, non-contiguous higher-order relation proposal.

This is a bounded candidate generator over arbitrary feature subsets. It is
not an unrestricted concept learner: it discretizes numeric features using
feature-only quantile boundaries and proposes exact joint-cell predicates.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from itertools import combinations
import math

from prototype.e12a5_residual_pair_diagnosis import (
    ResidualView, validate_view,
)


@dataclass(frozen=True)
class SubsetDiagnosis:
    features: tuple[str, ...]
    signature: tuple[int, ...]
    bin_edges: tuple[tuple[float, ...], ...]
    polarity: str
    balanced_accuracy: float
    matched_support: int
    unmatched_support: int
    matched_error_support: int
    matched_correct_support: int
    matched_evidence_ids: tuple[str, ...]
    unmatched_evidence_ids: tuple[str, ...]
    skipped_positions: int


def _balanced_accuracy(actual: list[int], predicted: list[int]) -> float:
    positive = [i for i, value in enumerate(actual) if value == 1]
    negative = [i for i, value in enumerate(actual) if value == 0]
    if not positive or not negative:
        return 0.0
    sensitivity = sum(predicted[i] == 1 for i in positive) / len(positive)
    specificity = sum(predicted[i] == 0 for i in negative) / len(negative)
    return (sensitivity + specificity) / 2.0


def _quantile_edges(values: list[float], bins: int) -> tuple[float, ...]:
    """Feature-only equal-frequency cut proposals, with ties kept together."""
    ordered = sorted(values)
    n = len(ordered)
    edges: set[float] = set()
    for q in range(1, bins):
        index = math.ceil(q * n / bins)
        index = min(max(index, 1), n - 1)
        left = ordered[index - 1]
        right = ordered[index]
        if left == right:
            # Move to the next distinct boundary rather than splitting ties.
            while index < n and ordered[index] == left:
                index += 1
            if index >= n:
                continue
            right = ordered[index]
        midpoint = left / 2.0 + right / 2.0
        if math.isfinite(midpoint) and left < midpoint < right:
            edges.add(midpoint)
    return tuple(sorted(edges))


def _rank_bin(value: float, edges: tuple[float, ...]) -> int:
    return bisect_right(edges, value)


def diagnose_sparse_subsets(
    view: ResidualView,
    *,
    min_order: int = 2,
    max_order: int = 4,
    quantile_bins: int = 2,
    min_side_support: int = 2,
    min_balanced_accuracy: float = 0.5,
    top_k: int = 20,
    max_subset_count: int = 20_000,
    max_candidate_evaluations: int = 250_000,
) -> dict:
    """Propose residual-associated joint-cell rules over arbitrary subsets.

    Subsets are selected by combinations(schema features), not by adjacency;
    e.g. (a, c, e) is considered even when b and d lie between them.
    """
    validate_view(view)
    integer_parameters = {
        "min_order": min_order,
        "max_order": max_order,
        "quantile_bins": quantile_bins,
        "min_side_support": min_side_support,
        "top_k": top_k,
        "max_subset_count": max_subset_count,
        "max_candidate_evaluations": max_candidate_evaluations,
    }
    for name, value in integer_parameters.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
    if min_order < 2 or max_order < min_order:
        raise ValueError("require 2 <= min_order <= max_order")
    if max_order > len(view.schema):
        raise ValueError("max_order cannot exceed the number of features")
    if quantile_bins < 2 or min_side_support < 1 or top_k < 1:
        raise ValueError("quantile_bins, min_side_support, and top_k must be positive")
    if max_subset_count < 1 or max_candidate_evaluations < 1:
        raise ValueError("search budgets must be positive")
    if (isinstance(min_balanced_accuracy, bool)
            or not isinstance(min_balanced_accuracy, (int, float))
            or not math.isfinite(min_balanced_accuracy)
            or not 0.5 <= min_balanced_accuracy <= 1.0):
        raise ValueError("min_balanced_accuracy must be finite and in [0.5, 1]")

    feature_names = tuple(spec.name for spec in view.schema)
    residual = [int(row.a3_prediction != row.label) for row in view.records]
    values = {
        name: [row.value(name) for row in view.records]
        for name in feature_names
    }
    edges = {
        name: _quantile_edges(values[name], quantile_bins)
        for name in feature_names
    }
    bins = {
        name: tuple(_rank_bin(value, edges[name]) for value in values[name])
        for name in feature_names
    }

    ranked: list[SubsetDiagnosis] = []
    subset_count = 0
    candidate_evaluations = 0
    observed_signatures = 0
    for order in range(min_order, max_order + 1):
        for subset in combinations(feature_names, order):
            subset_count += 1
            if subset_count > max_subset_count:
                return {
                    "status": "BUDGET_EXHAUSTED",
                    "budget": "max_subset_count",
                    "subsets_examined": subset_count - 1,
                    "candidate_evaluations": candidate_evaluations,
                    "diagnoses": (),
                }

            row_signatures = tuple(
                tuple(bins[name][row_index] for name in subset)
                for row_index in range(len(view.records))
            )
            signatures = sorted(set(row_signatures))
            observed_signatures += len(signatures)
            for signature in signatures:
                matched = [i for i, item in enumerate(row_signatures)
                           if item == signature]
                unmatched = [i for i, item in enumerate(row_signatures)
                             if item != signature]
                if min(len(matched), len(unmatched)) < min_side_support:
                    continue
                for polarity in ("MATCHED_ERROR", "UNMATCHED_ERROR"):
                    candidate_evaluations += 1
                    if candidate_evaluations > max_candidate_evaluations:
                        return {
                            "status": "BUDGET_EXHAUSTED",
                            "budget": "max_candidate_evaluations",
                            "subsets_examined": subset_count,
                            "candidate_evaluations": candidate_evaluations - 1,
                            "diagnoses": (),
                        }
                    predicted = [0] * len(view.records)
                    target = matched if polarity == "MATCHED_ERROR" else unmatched
                    for index in target:
                        predicted[index] = 1
                    score = _balanced_accuracy(residual, predicted)
                    if score < min_balanced_accuracy:
                        continue
                    matched_errors = sum(residual[i] for i in matched)
                    candidate = SubsetDiagnosis(
                        features=tuple(subset),
                        signature=tuple(signature),
                        bin_edges=tuple(edges[name] for name in subset),
                        polarity=polarity,
                        balanced_accuracy=score,
                        matched_support=len(matched),
                        unmatched_support=len(unmatched),
                        matched_error_support=matched_errors,
                        matched_correct_support=len(matched) - matched_errors,
                        matched_evidence_ids=tuple(sorted(
                            view.records[i].evidence_id for i in matched
                        )),
                        unmatched_evidence_ids=tuple(sorted(
                            view.records[i].evidence_id for i in unmatched
                        )),
                        skipped_positions=sum(
                            feature_names.index(right) - feature_names.index(left) - 1
                            for left, right in zip(subset, subset[1:])
                        ),
                    )
                    ranked.append(candidate)

    ranked.sort(key=lambda item: (
        -item.balanced_accuracy,
        len(item.features),
        item.features,
        item.signature,
        item.polarity,
    ))
    selected = tuple(ranked[:top_k])
    return {
        "status": "DIAGNOSED" if selected else "NO_SUPPORTED_SUBSET",
        "prediction_mode": view.prediction_mode,
        "model_version": view.model_version,
        "record_count": len(view.records),
        "residual_count": sum(residual),
        "min_order": min_order,
        "max_order": max_order,
        "quantile_bins": quantile_bins,
        "subsets_examined": subset_count,
        "observed_joint_signatures": observed_signatures,
        "candidate_evaluations": candidate_evaluations,
        "qualified_candidate_count": len(ranked),
        "diagnoses": selected,
    }
