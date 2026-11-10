"""E12-M2.3: burn-in/thinning sensitivity experiments on heterogeneous graphs."""
from __future__ import annotations

import random
from collections import Counter
from statistics import mean
from typing import Sequence

from prototype.e12m2_chain_diagnostics import diagnose_permutation_chains
from prototype.e12m2_permutation_benchmark import degree_preserving_swaps


def make_heterogeneous_dataset(
    *,
    rows: int = 120,
    items: int = 12,
    min_row_size: int = 1,
    max_row_size: int = 5,
    popularity_exponent: float = 1.2,
    seed: int = 0,
    mixing_swaps_per_edge: int = 20,
) -> list[set[str]]:
    """Generate variable row degrees and skewed item popularity, then mix.

    Item weights follow a truncated Zipf-like rank law. The first 'items' rows
    each contain one distinct anchor item so every item is represented before
    weighted filling. Subsequent 2-switches preserve the realized margins.
    """
    if rows < items or items < 3:
        raise ValueError("require rows >= items >= 3")
    if not 1 <= min_row_size <= max_row_size < items:
        raise ValueError("require 1 <= min_row_size <= max_row_size < items")
    if popularity_exponent < 0:
        raise ValueError("popularity_exponent must be non-negative")
    if mixing_swaps_per_edge < 0:
        raise ValueError("mixing_swaps_per_edge must be non-negative")

    rng = random.Random(seed)
    universe = [f"item_{index}" for index in range(items)]
    weights = [1.0 / ((index + 1) ** popularity_exponent) for index in range(items)]
    dataset: list[set[str]] = []
    for row_index in range(rows):
        size = rng.randint(min_row_size, max_row_size)
        chosen: set[str] = set()
        if row_index < items:
            chosen.add(universe[row_index])
        while len(chosen) < size:
            available = [item for item in universe if item not in chosen]
            available_weights = [weights[universe.index(item)] for item in available]
            chosen.add(rng.choices(available, weights=available_weights, k=1)[0])
        dataset.append(chosen)

    edge_count = sum(map(len, dataset))
    mixed, _ = degree_preserving_swaps(
        dataset,
        swaps=mixing_swaps_per_edge * edge_count,
        seed=seed + 1,
    )
    return mixed


def _margin_summary(rows: Sequence[set[str]]) -> dict:
    row_degrees = [len(row) for row in rows]
    item_degrees = Counter(item for row in rows for item in row)
    values = sorted(item_degrees.values())
    return {
        "row_degree_min": min(row_degrees, default=0),
        "row_degree_max": max(row_degrees, default=0),
        "row_degree_mean": mean(row_degrees) if row_degrees else 0.0,
        "item_degree_min": min(values, default=0),
        "item_degree_max": max(values, default=0),
        "item_degree_mean": mean(values) if values else 0.0,
        "item_degree_gini": _gini(values),
    }


def _gini(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    total = sum(ordered)
    if total == 0:
        return 0.0
    count = len(ordered)
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    return (2.0 * weighted) / (count * total) - (count + 1) / count


def run_mixing_sensitivity(
    *,
    dataset_seeds: int = 5,
    chains: int = 4,
    samples_per_chain: int = 100,
    burn_in_grid: Sequence[int] = (0, 5, 20, 50),
    thinning_grid: Sequence[int] = (1, 3, 10),
    seed_start: int = 500,
) -> dict:
    """Compare chain diagnostics across burn-in/thinning and dataset seeds."""
    if dataset_seeds < 1 or chains < 1 or samples_per_chain < 2:
        raise ValueError("dataset_seeds/chains must be positive; samples >= 2")
    if not burn_in_grid or not thinning_grid:
        raise ValueError("burn_in_grid and thinning_grid must be non-empty")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in burn_in_grid):
        raise ValueError("burn_in_grid values must be non-negative integers")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in thinning_grid):
        raise ValueError("thinning_grid values must be non-negative integers")

    datasets = [
        make_heterogeneous_dataset(seed=seed_start + offset)
        for offset in range(dataset_seeds)
    ]
    margin_profiles = [_margin_summary(dataset) for dataset in datasets]
    results = []

    for burn_in in burn_in_grid:
        for thinning in thinning_grid:
            ess_fractions = []
            autocorrelations = []
            between_chain_variances = []
            acceptance_rates = []
            for offset, dataset in enumerate(datasets):
                degrees = Counter(item for row in dataset for item in row)
                candidate = tuple(item for item, _ in degrees.most_common(2))
                report = diagnose_permutation_chains(
                    dataset,
                    candidate,
                    chains=chains,
                    samples_per_chain=samples_per_chain,
                    burn_in_swaps_per_edge=burn_in,
                    thinning_swaps_per_edge=thinning,
                    seed=seed_start * 1009 + offset,
                )
                total_samples = chains * samples_per_chain
                ess_fractions.append(
                    report["total_ess_initial_positive"] / total_samples
                )
                autocorrelations.append(report["mean_lag1_autocorrelation"])
                between_chain_variances.append(
                    report["between_chain_mean_variance"]
                )
                acceptance_rates.extend(
                    chain["acceptance_rate"] for chain in report["chain_reports"]
                )
            results.append({
                "burn_in_swaps_per_edge": burn_in,
                "thinning_swaps_per_edge": thinning,
                "datasets": dataset_seeds,
                "chains_per_dataset": chains,
                "samples_per_chain": samples_per_chain,
                "mean_ess_fraction": mean(ess_fractions),
                "mean_lag1_autocorrelation": mean(autocorrelations),
                "mean_between_chain_mean_variance": mean(between_chain_variances),
                "mean_acceptance_rate": mean(acceptance_rates),
            })

    return {
        "experiment": "E12-M2.3 heterogeneous-graph mixing sensitivity",
        "dataset_seeds": dataset_seeds,
        "margin_profiles": margin_profiles,
        "configurations": results,
        "limitations": (
            "Exploratory score-specific diagnostics, not a proof of uniform "
            "stationary sampling. ESS estimates are approximate; dataset "
            "generation and graph-family coverage remain limited."
        ),
    }
