"""Paired, deterministic bootstrap comparisons for registered experiments.

This module analyzes already-recorded metrics; it never executes experiments.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SeedMetric:
    seed: int
    value: float

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if (isinstance(self.value, bool) or not isinstance(self.value, (int, float))
                or not math.isfinite(self.value)):
            raise ValueError("metric value must be a finite number")


@dataclass(frozen=True)
class PairedComparison:
    metric_name: str
    direction: str
    sample_count: int
    baseline_mean: float
    candidate_mean: float
    mean_difference: float
    median_difference: float
    difference_stddev: float
    improvement_rate: float
    paired_cohens_dz: float | None
    confidence_level: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    bootstrap_samples: int
    bootstrap_seed: int


def _validate_samples(samples: Iterable[SeedMetric], label: str) -> dict[int, float]:
    if isinstance(samples, (str, bytes)):
        raise ValueError(f"{label} samples must be an iterable of SeedMetric")
    try:
        items = list(samples)
    except TypeError as exc:
        raise ValueError(f"{label} samples must be iterable") from exc
    if len(items) < 2:
        raise ValueError("at least two paired seeds are required")
    result: dict[int, float] = {}
    for item in items:
        if not isinstance(item, SeedMetric):
            raise ValueError(f"{label} samples must contain SeedMetric values")
        if item.seed in result:
            raise ValueError(f"duplicate {label} seed: {item.seed}")
        result[item.seed] = float(item.value)
    return result


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def compare_paired(
    metric_name: str,
    baseline: Iterable[SeedMetric],
    candidate: Iterable[SeedMetric],
    *,
    direction: str = "higher",
    confidence_level: float = 0.95,
    bootstrap_samples: int = 10_000,
    bootstrap_seed: int = 0,
) -> PairedComparison:
    """Compare candidate against baseline using matched seeds and percentile bootstrap CI.

    The confidence interval is a paired percentile-bootstrap interval, not a
    guarantee of calibrated coverage for tiny samples. Seeds are resampled as
    paired observations, preserving baseline/candidate correspondence.
    """
    if not isinstance(metric_name, str) or not metric_name.strip():
        raise ValueError("metric_name must be non-empty")
    if direction not in {"higher", "lower"}:
        raise ValueError("direction must be 'higher' or 'lower'")
    if (isinstance(confidence_level, bool) or not isinstance(confidence_level, (int, float))
            or not math.isfinite(confidence_level) or not 0 < confidence_level < 1):
        raise ValueError("confidence_level must be between 0 and 1")
    if (isinstance(bootstrap_samples, bool) or not isinstance(bootstrap_samples, int)
            or bootstrap_samples < 100):
        raise ValueError("bootstrap_samples must be an integer >= 100")
    if (isinstance(bootstrap_seed, bool) or not isinstance(bootstrap_seed, int)
            or bootstrap_seed < 0):
        raise ValueError("bootstrap_seed must be a non-negative integer")

    base = _validate_samples(baseline, "baseline")
    cand = _validate_samples(candidate, "candidate")
    if base.keys() != cand.keys():
        missing_candidate = sorted(base.keys() - cand.keys())
        missing_baseline = sorted(cand.keys() - base.keys())
        raise ValueError(
            "baseline/candidate seeds must match exactly "
            f"(missing candidate={missing_candidate}, missing baseline={missing_baseline})"
        )

    seeds = sorted(base)
    baseline_values = [base[seed] for seed in seeds]
    candidate_values = [cand[seed] for seed in seeds]
    sign = 1.0 if direction == "higher" else -1.0
    differences = [(candidate_values[i] - baseline_values[i]) * sign
                   for i in range(len(seeds))]
    mean_diff = statistics.fmean(differences)
    stddev = statistics.stdev(differences)
    rng = random.Random(bootstrap_seed)
    n = len(differences)
    boot_means = [
        statistics.fmean(differences[rng.randrange(n)] for _ in range(n))
        for _ in range(bootstrap_samples)
    ]
    boot_means.sort()
    tail = (1.0 - confidence_level) / 2.0
    dz = mean_diff / stddev if stddev > 0 else None
    return PairedComparison(
        metric_name=metric_name,
        direction=direction,
        sample_count=n,
        baseline_mean=statistics.fmean(baseline_values),
        candidate_mean=statistics.fmean(candidate_values),
        mean_difference=mean_diff,
        median_difference=statistics.median(differences),
        difference_stddev=stddev,
        improvement_rate=sum(value > 0 for value in differences) / n,
        paired_cohens_dz=dz,
        confidence_level=float(confidence_level),
        bootstrap_ci_low=_quantile(boot_means, tail),
        bootstrap_ci_high=_quantile(boot_means, 1.0 - tail),
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
