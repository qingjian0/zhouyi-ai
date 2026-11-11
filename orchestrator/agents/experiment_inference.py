"""Paired permutation inference and multiple-testing correction.

This module analyzes already-recorded metrics and never executes experiments.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PermutationTestResult:
    sample_count: int
    observed_mean_difference: float
    p_value: float
    method: str
    permutations_evaluated: int
    random_seed: int | None


def paired_sign_flip_test(
    differences: Iterable[float],
    *,
    monte_carlo_samples: int = 20_000,
    random_seed: int = 0,
    exact_limit: int = 20,
) -> PermutationTestResult:
    """Two-sided sign-flip test; exact for small n, deterministic Monte Carlo otherwise.

    Validity requires independent, exchangeable paired units under the null.
    A matching random-seed label alone does not establish this assumption.
    """
    try:
        values = list(differences)
    except TypeError as exc:
        raise ValueError("differences must be an iterable of finite numbers") from exc
    if len(values) < 2:
        raise ValueError("at least two paired differences are required")
    clean: list[float] = []
    for value in values:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value)):
            raise ValueError("differences must contain finite numbers")
        clean.append(float(value))
    if (isinstance(exact_limit, bool) or not isinstance(exact_limit, int)
            or exact_limit < 2 or exact_limit > 24):
        raise ValueError("exact_limit must be an integer from 2 to 24")
    if (isinstance(monte_carlo_samples, bool) or not isinstance(monte_carlo_samples, int)
            or monte_carlo_samples < 1000):
        raise ValueError("monte_carlo_samples must be an integer >= 1000")
    if (isinstance(random_seed, bool) or not isinstance(random_seed, int)
            or random_seed < 0):
        raise ValueError("random_seed must be a non-negative integer")

    observed = abs(statistics.fmean(clean))
    tolerance = 1e-12 * max(1.0, observed, *(abs(x) for x in clean))
    n = len(clean)
    if n <= exact_limit:
        extreme = 0
        total = 1 << n
        for mask in range(total):
            signed_sum = sum(value if mask & (1 << index) else -value
                             for index, value in enumerate(clean))
            if abs(signed_sum / n) + tolerance >= observed:
                extreme += 1
        return PermutationTestResult(
            n, statistics.fmean(clean), extreme / total,
            "exact_sign_flip", total, None,
        )

    rng = random.Random(random_seed)
    extreme = 0
    for _ in range(monte_carlo_samples):
        signed_mean = statistics.fmean(
            value if rng.getrandbits(1) else -value for value in clean
        )
        if abs(signed_mean) + tolerance >= observed:
            extreme += 1
    return PermutationTestResult(
        n, statistics.fmean(clean), (extreme + 1) / (monte_carlo_samples + 1),
        "monte_carlo_sign_flip", monte_carlo_samples, random_seed,
    )


def holm_bonferroni(p_values: dict[str, float]) -> dict[str, float]:
    """Compute Holm step-down adjusted p-values, preserving input key order."""
    if not isinstance(p_values, dict) or not p_values:
        raise ValueError("p_values must be a non-empty mapping")
    items: list[tuple[str, float]] = []
    for name, value in p_values.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("p-value names must be non-empty strings")
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError(f"p-value for {name} must be between 0 and 1")
        items.append((name, float(value)))
    ordered = sorted(items, key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running_max = 0.0
    count = len(ordered)
    for index, (name, raw_p) in enumerate(ordered):
        running_max = max(running_max, min(1.0, (count - index) * raw_p))
        adjusted[name] = running_max
    return {name: adjusted[name] for name, _ in items}
