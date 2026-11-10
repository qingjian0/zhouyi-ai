"""E12-A5-2a: family-wise residual-pair diagnosis by max-statistic permutation.

The permutation unit is the residual label. Every permutation reruns the complete
pair/threshold/polarity scan, so candidate p-values are adjusted against the
maximum statistic over the full searched family.
"""
from __future__ import annotations

from dataclasses import replace
import math
import random

from prototype.e12a5_residual_pair_diagnosis import (
    ResidualRecord, ResidualView, diagnose_pairs, validate_view,
)


def _valid_split_count(view: ResidualView, min_side_support: int) -> int:
    count = 0
    names = [item.name for item in view.schema]
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            distances = sorted({abs(row.value(left) - row.value(right))
                                for row in view.records})
            if any(not math.isfinite(value) for value in distances):
                raise ValueError("pairwise absolute differences must remain finite")
            for lower, upper in zip(distances, distances[1:]):
                threshold = lower / 2.0 + upper / 2.0
                if not math.isfinite(threshold) or not lower < threshold < upper:
                    continue
                low = sum(abs(row.value(left) - row.value(right)) <= threshold
                          for row in view.records)
                high = len(view.records) - low
                if min(low, high) >= min_side_support:
                    count += 2  # HIGH_ERROR and LOW_ERROR
    return count


def _max_statistic(view: ResidualView, min_side_support: int) -> float:
    result = diagnose_pairs(
        view, min_side_support=min_side_support,
        min_balanced_accuracy=0.5, top_k=1,
    )
    if not result["diagnoses"]:
        return 0.5
    return result["diagnoses"][0].balanced_accuracy


def _permuted_view(view: ResidualView, residuals: list[int]) -> ResidualView:
    rows = tuple(
        replace(row, label=int(residual), a3_prediction=0)
        for row, residual in zip(view.records, residuals)
    )
    return replace(view, records=rows)


def maxstat_permutation_test(
    view: ResidualView,
    *,
    permutations: int = 999,
    seed: int = 20261111,
    min_side_support: int = 2,
    alpha: float = 0.05,
    top_k: int = 3,
    max_total_candidate_evaluations: int = 2_000_000,
) -> dict:
    """Run a deterministic max-statistic permutation test over the full scan.

    Exchangeability of residual labels is an assumption, not something this
    function can establish. For time-dependent prequential streams, callers
    should use a justified block/cluster permutation design instead.
    """
    validate_view(view)
    for name, value in (("permutations", permutations),
                        ("seed", seed),
                        ("min_side_support", min_side_support),
                        ("top_k", top_k),
                        ("max_total_candidate_evaluations",
                         max_total_candidate_evaluations)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
    if permutations < 1 or min_side_support < 1 or top_k < 1:
        raise ValueError("permutations, min_side_support, and top_k must be positive")
    if max_total_candidate_evaluations < 1:
        raise ValueError("max_total_candidate_evaluations must be positive")
    if (isinstance(alpha, bool) or not isinstance(alpha, (int, float))
            or not math.isfinite(alpha) or not 0.0 < alpha < 1.0):
        raise ValueError("alpha must be finite and strictly between 0 and 1")

    per_scan_evaluations = _valid_split_count(view, min_side_support)
    required = per_scan_evaluations * (permutations + 1)
    if required > max_total_candidate_evaluations:
        return {
            "status": "BUDGET_EXHAUSTED",
            "required_candidate_evaluations": required,
            "max_total_candidate_evaluations": max_total_candidate_evaluations,
            "permutations_requested": permutations,
            "permutations_completed": 0,
            "diagnoses": (),
        }

    observed = diagnose_pairs(
        view, min_side_support=min_side_support,
        min_balanced_accuracy=0.5, top_k=top_k,
    )
    observed_max = _max_statistic(view, min_side_support)
    residuals = [int(row.a3_prediction != row.label) for row in view.records]
    rng = random.Random(seed)
    null_maxima: list[float] = []
    for _ in range(permutations):
        shuffled = list(residuals)
        rng.shuffle(shuffled)
        null_maxima.append(_max_statistic(
            _permuted_view(view, shuffled), min_side_support
        ))

    def adjusted_p(score: float) -> float:
        return (1 + sum(value >= score for value in null_maxima)) / (permutations + 1)

    diagnoses = tuple({
        "left": item.left,
        "right": item.right,
        "threshold": item.threshold,
        "polarity": item.polarity,
        "balanced_accuracy": item.balanced_accuracy,
        "maxT_adjusted_p_value": adjusted_p(item.balanced_accuracy),
        "family_wise_significant": adjusted_p(item.balanced_accuracy) <= alpha,
        "evidence_ids": item.evidence_ids,
    } for item in observed["diagnoses"])

    observed_p = adjusted_p(observed_max)
    return {
        "status": "COMPLETED",
        "prediction_mode": view.prediction_mode,
        "model_version": view.model_version,
        "record_count": len(view.records),
        "residual_count": len(residuals) and sum(residuals),
        "candidate_pair_count": observed["candidate_pair_count"],
        "per_threshold_polarity_evaluations": per_scan_evaluations,
        "required_candidate_evaluations": required,
        "permutations_requested": permutations,
        "permutations_completed": len(null_maxima),
        "seed": seed,
        "alpha": float(alpha),
        "observed_max_statistic": observed_max,
        "global_maxT_adjusted_p_value": observed_p,
        "global_family_wise_significant": observed_p <= alpha,
        "null_maxima": tuple(null_maxima),
        "diagnoses": diagnoses,
    }
