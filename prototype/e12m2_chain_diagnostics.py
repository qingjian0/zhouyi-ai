"""E12-M2.3: independent-chain mixing diagnostics for conditional motif nulls.

Diagnostics are descriptive. Acceptance rate and ESS do not prove that the
2-switch Markov chain has reached the uniform distribution over realizations.
"""
from __future__ import annotations

import random
from statistics import mean, variance
from typing import Sequence

from prototype.e12m2_permutation_benchmark import (
    _motif_score,
    _normalize,
    degree_preserving_swaps,
)


def _lag1_autocorrelation(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = mean(values)
    denominator = sum((value - center) ** 2 for value in values)
    if denominator == 0:
        return 0.0
    numerator = sum(
        (values[index] - center) * (values[index - 1] - center)
        for index in range(1, len(values))
    )
    return max(-1.0, min(1.0, numerator / denominator))


def _initial_positive_ess(values: Sequence[float]) -> float:
    """Conservative single-chain ESS approximation using positive lag pairs."""
    count = len(values)
    if count < 3:
        return float(count)
    if max(values) == min(values):
        return float(count)
    center = mean(values)
    centered = [value - center for value in values]
    denominator = sum(value * value for value in centered)
    if denominator == 0:
        return float(count)

    correlations = []
    for lag in range(1, count):
        covariance = sum(
            centered[index] * centered[index - lag]
            for index in range(lag, count)
        )
        # Biased autocovariance normalization keeps the finite-sample ACF
        # bounded more reliably at long lags than dividing by (n - lag).
        correlations.append(covariance / denominator)

    positive_sum = 0.0
    for index in range(0, len(correlations), 2):
        pair_sum = correlations[index]
        if index + 1 < len(correlations):
            pair_sum += correlations[index + 1]
        if pair_sum <= 0:
            break
        positive_sum += pair_sum
    tau = max(1.0, 1.0 + 2.0 * positive_sum)
    return min(float(count), max(1.0, count / tau))


def diagnose_permutation_chains(
    observations: Sequence[set[str]],
    members: Sequence[str],
    *,
    chains: int = 4,
    samples_per_chain: int = 100,
    burn_in_swaps_per_edge: int = 10,
    thinning_swaps_per_edge: int = 3,
    seed: int = 0,
) -> dict:
    """Run reproducible independent-seed chains and report score-trace diagnostics.

    Each chain starts from the same observed graph but uses a distinct RNG
    stream. Burn-in and thinning are measured in attempted 2-switches per edge.
    """
    if isinstance(chains, bool) or not isinstance(chains, int) or chains < 1:
        raise ValueError("chains must be a positive integer")
    if isinstance(samples_per_chain, bool) or not isinstance(samples_per_chain, int) or samples_per_chain < 2:
        raise ValueError("samples_per_chain must be an integer >= 2")
    for name, value in (
        ("burn_in_swaps_per_edge", burn_in_swaps_per_edge),
        ("thinning_swaps_per_edge", thinning_swaps_per_edge),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    candidate = tuple(sorted(members))
    if len(candidate) < 2 or len(set(candidate)) != len(candidate):
        raise ValueError("members must contain at least two distinct items")

    original = _normalize(observations)
    edge_count = sum(len(row) for row in original)
    attempts_per_edge = max(1, edge_count)
    burn_attempts = burn_in_swaps_per_edge * attempts_per_edge
    thin_attempts = thinning_swaps_per_edge * attempts_per_edge
    observed_score = _motif_score(original, candidate)
    rng = random.Random(seed)
    chain_reports = []

    for chain_index in range(chains):
        chain_seed = rng.randrange(0, 2**63)
        chain_rng = random.Random(chain_seed)
        state = [set(row) for row in original]
        attempted = accepted = 0
        if burn_attempts:
            state, count = degree_preserving_swaps(
                state, swaps=burn_attempts,
                seed=chain_rng.randrange(0, 2**63),
            )
            attempted += burn_attempts
            accepted += count

        trace = []
        for _ in range(samples_per_chain):
            state, count = degree_preserving_swaps(
                state, swaps=thin_attempts,
                seed=chain_rng.randrange(0, 2**63),
            )
            attempted += thin_attempts
            accepted += count
            trace.append(_motif_score(state, candidate))

        chain_reports.append({
            "chain": chain_index,
            "seed": chain_seed,
            "score_mean": mean(trace),
            "score_variance": variance(trace),
            "score_min": min(trace),
            "score_max": max(trace),
            "lag1_autocorrelation": _lag1_autocorrelation(trace),
            "ess_initial_positive": _initial_positive_ess(trace),
            "attempted_swaps": attempted,
            "accepted_swaps": accepted,
            "acceptance_rate": accepted / attempted if attempted else 0.0,
            "trace": trace,
        })

    chain_means = [report["score_mean"] for report in chain_reports]
    return {
        "candidate": list(candidate),
        "observed_score": observed_score,
        "chains": chains,
        "samples_per_chain": samples_per_chain,
        "burn_in_swaps_per_edge": burn_in_swaps_per_edge,
        "thinning_swaps_per_edge": thinning_swaps_per_edge,
        "pooled_score_mean": mean(chain_means),
        "between_chain_mean_variance": variance(chain_means) if chains > 1 else 0.0,
        "mean_lag1_autocorrelation": mean(
            report["lag1_autocorrelation"] for report in chain_reports
        ),
        "total_ess_initial_positive": sum(
            report["ess_initial_positive"] for report in chain_reports
        ),
        "total_samples": chains * samples_per_chain,
        "chain_reports": chain_reports,
        "warning": (
            "Descriptive diagnostics only: independent RNG streams do not prove "
            "independent stationary draws or uniform sampling over graph realizations. "
            "Inspect traces, ESS, between-chain differences, and sensitivity to "
            "longer burn-in/thinning."
        ),
    }
