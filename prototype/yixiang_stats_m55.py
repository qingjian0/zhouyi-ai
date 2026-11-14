"""M55 statistical inference utilities for paired causal-baseline experiments.

All functions operate on externally recorded, paired per-seed metrics. They do
not infer causality and do not make a superiority claim by themselves.
"""
from __future__ import annotations

import random
from math import isfinite, sqrt
from statistics import mean


def _finite_numbers(values, name):
    result = tuple(float(value) for value in values)
    if not result or not all(isfinite(value) for value in result):
        raise ValueError(f"{name}_must_be_nonempty_finite")
    return result


def wilson_interval(successes, trials, z=1.959963984540054):
    if (not isinstance(successes, int) or isinstance(successes, bool)
            or not isinstance(trials, int) or isinstance(trials, bool)
            or trials <= 0 or successes < 0 or successes > trials
            or not isfinite(z) or z <= 0):
        raise ValueError("invalid_binomial_counts_or_z")
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (p + z2 / (2.0 * trials)) / denominator
    radius = z * sqrt(p * (1.0 - p) / trials + z2 / (4.0 * trials * trials)) / denominator
    return (max(0.0, center - radius), min(1.0, center + radius))


def holm_adjust(p_values):
    """Holm step-down adjusted p-values, returned in original order."""
    values = _finite_numbers(p_values, "p_values")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("p_values_must_be_in_0_1")
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    adjusted = [0.0] * len(values)
    running = 0.0
    count = len(values)
    for rank, index in enumerate(order):
        candidate = min(1.0, (count - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return tuple(adjusted)


def benjamini_hochberg_adjust(p_values):
    """Benjamini-Hochberg adjusted p-values, returned in original order."""
    values = _finite_numbers(p_values, "p_values")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("p_values_must_be_in_0_1")
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    adjusted = [1.0] * len(values)
    running = 1.0
    count = len(values)
    for reverse_rank in range(count - 1, -1, -1):
        index = order[reverse_rank]
        rank = reverse_rank + 1
        running = min(running, values[index] * count / rank)
        adjusted[index] = min(1.0, running)
    return tuple(adjusted)


def paired_bootstrap_interval(differences, *, repetitions=10000, seed=20261114,
                              confidence=0.95):
    """Percentile bootstrap CI for mean paired difference (method A - B)."""
    values = _finite_numbers(differences, "differences")
    if (not isinstance(repetitions, int) or isinstance(repetitions, bool)
            or repetitions < 100):
        raise ValueError("repetitions_must_be_integer_at_least_100")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed_must_be_integer")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence_must_be_between_zero_and_one")
    rng = random.Random(seed)
    n = len(values)
    boot_means = []
    for _ in range(repetitions):
        boot_means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    boot_means.sort()
    tail = (1.0 - confidence) / 2.0
    lower_index = max(0, min(repetitions - 1, int(tail * repetitions)))
    upper_index = max(0, min(repetitions - 1, int((1.0 - tail) * repetitions) - 1))
    return {
        "mean_difference": mean(values),
        "confidence": confidence,
        "interval": (boot_means[lower_index], boot_means[upper_index]),
        "paired_units": n,
        "bootstrap_repetitions": repetitions,
        "seed": seed,
    }


def paired_comparison(records, *, method_a, method_b, metric,
                      repetitions=10000, seed=20261114):
    """Compare two methods on matched seed/scenario records.

    records: iterable of dicts with seed, scenario, method, and metric keys.
    Duplicate method/seed/scenario cells and unpaired cells are rejected.
    """
    cells = {}
    for record in records:
        try:
            key = (record["scenario"], record["seed"], record["method"])
            value = float(record[metric])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed_comparison_record") from exc
        if not isfinite(value):
            raise ValueError("metric_must_be_finite")
        if key in cells:
            raise ValueError("duplicate_method_seed_scenario")
        cells[key] = value
    scenarios = sorted({key[0] for key in cells})
    paired_differences = []
    for scenario in scenarios:
        seeds_a = {seed for (sc, seed, method) in cells
                   if sc == scenario and method == method_a}
        seeds_b = {seed for (sc, seed, method) in cells
                   if sc == scenario and method == method_b}
        if seeds_a != seeds_b or not seeds_a:
            raise ValueError("unpaired_seed_cells")
        for seed_value in sorted(seeds_a, key=str):
            paired_differences.append(
                cells[(scenario, seed_value, method_a)]
                - cells[(scenario, seed_value, method_b)]
            )
    return paired_bootstrap_interval(
        paired_differences, repetitions=repetitions, seed=seed
    )


def power_estimate(rejections, trials):
    low, high = wilson_interval(rejections, trials)
    return {"rejections": rejections, "trials": trials,
            "power": rejections / trials, "wilson_95": (low, high)}


def paired_sign_flip_pvalue(differences, *, repetitions=20000, seed=20261114):
    """Two-sided Monte Carlo paired randomization p-value for mean difference.

    Uses the plus-one correction, so the returned p-value is never zero.
    For small n (<=16), enumerates all sign assignments exactly.
    """
    values = _finite_numbers(differences, "differences")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed_must_be_integer")
    observed = abs(mean(values))
    n = len(values)
    if n <= 16:
        total = 1 << n
        extreme = 0
        for mask in range(total):
            statistic = abs(sum(value if (mask >> index) & 1 else -value
                                for index, value in enumerate(values)) / n)
            if statistic >= observed - 1e-15:
                extreme += 1
        return {"p_value": extreme / total, "method": "exact_sign_flip",
                "permutations": total, "observed_mean": mean(values)}
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1000:
        raise ValueError("repetitions_must_be_integer_at_least_1000")
    rng = random.Random(seed)
    extreme = 0
    for _ in range(repetitions):
        statistic = abs(sum(value if rng.getrandbits(1) else -value
                            for value in values) / n)
        if statistic >= observed - 1e-15:
            extreme += 1
    return {"p_value": (extreme + 1) / (repetitions + 1),
            "method": "monte_carlo_sign_flip",
            "permutations": repetitions, "observed_mean": mean(values)}
