"""E12-M2.2: synthetic calibration and planted-motif power experiments."""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from statistics import mean
from typing import Sequence

from prototype.e12m2_permutation_benchmark import (
    degree_preserving_swaps,
    permutation_test,
)


def _margins(rows: Sequence[set[str]]) -> tuple[tuple[int, ...], tuple[tuple[str, int], ...]]:
    return (
        tuple(len(row) for row in rows),
        tuple(sorted(Counter(item for row in rows for item in row).items())),
    )


def make_fixed_margin_dataset(
    *,
    rows: int = 120,
    items: int = 12,
    row_size: int = 3,
    seed: int = 0,
    mixing_swaps_per_edge: int = 30,
) -> list[set[str]]:
    """Create a balanced bipartite incidence graph, then randomize by 2-switches."""
    if rows < 2 or items < 3 or row_size < 1 or row_size >= items:
        raise ValueError("require rows>=2, items>=3, and 1<=row_size<items")
    if (rows * row_size) % items:
        raise ValueError("rows * row_size must be divisible by items for balanced item margins")
    if mixing_swaps_per_edge < 0:
        raise ValueError("mixing_swaps_per_edge must be non-negative")
    data = [
        {f"item_{(row + offset) % items}" for offset in range(row_size)}
        for row in range(rows)
    ]
    attempts = mixing_swaps_per_edge * rows * row_size
    randomized, _ = degree_preserving_swaps(data, swaps=attempts, seed=seed)
    return randomized


def plant_pair(
    observations: Sequence[set[str]],
    members: tuple[str, str] = ("item_0", "item_1"),
    *,
    injections: int,
    seed: int = 0,
) -> tuple[list[set[str]], int]:
    """Increase pair co-occurrence with degree-preserving 2-switches.

    Each successful injection moves one non-target item from a row containing
    the first target to a row containing the second target, while moving the
    second target item in the opposite direction. Both margins stay fixed.
    """
    if injections < 0:
        raise ValueError("injections must be non-negative")
    a, b = members
    if a == b:
        raise ValueError("pair members must be distinct")
    rows = [set(row) for row in observations]
    rng = random.Random(seed)
    applied = 0
    for _ in range(injections):
        candidates = []
        for r1, row1 in enumerate(rows):
            if a not in row1 or b in row1:
                continue
            movable = [item for item in row1 if item != a]
            rng.shuffle(movable)
            for r2, row2 in enumerate(rows):
                if b not in row2 or a in row2:
                    continue
                valid = [item for item in movable if item not in row2]
                if valid:
                    candidates.append((r1, r2, valid[0]))
        if not candidates:
            break
        r1, r2, movable = rng.choice(candidates)
        rows[r1].remove(movable)
        rows[r2].remove(b)
        rows[r1].add(b)
        rows[r2].add(movable)
        applied += 1
    return rows, applied


def _pair_count(rows: Sequence[set[str]], pair: tuple[str, str]) -> int:
    a, b = pair
    return sum(a in row and b in row for row in rows)


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float]:
    """95% Wilson score interval for a binomial proportion."""
    if total < 1:
        return [0.0, 1.0]
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * (proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)) ** 0.5
        / denominator
    )
    return [max(0.0, center - radius), min(1.0, center + radius)]


def run_calibration(
    *,
    seeds: int = 10,
    permutations: int = 39,
    swaps_per_edge: int = 3,
    injections: int = 12,
    alpha: float = 0.05,
    seed_start: int = 100,
) -> dict:
    if seeds < 1 or permutations < 1 or swaps_per_edge < 1:
        raise ValueError("seeds, permutations, and swaps_per_edge must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    pair = ("item_0", "item_1")
    null_p: list[float] = []
    null_max_p: list[float] = []
    planted_p: list[float] = []
    planted_max_p: list[float] = []
    accepted_rates: list[float] = []
    applied_injections: list[int] = []
    pair_lift_changes: list[int] = []

    for offset in range(seeds):
        seed = seed_start + offset
        null_data = make_fixed_margin_dataset(seed=seed)
        planted_data, applied = plant_pair(
            null_data, pair, injections=injections, seed=seed + 1
        )
        null_result = permutation_test(
            null_data, pair, permutations=permutations,
            swaps_per_edge=swaps_per_edge, max_order=2, seed=seed + 2,
        )
        planted_result = permutation_test(
            planted_data, pair, permutations=permutations,
            swaps_per_edge=swaps_per_edge, max_order=2, seed=seed + 3,
        )
        null_p.append(null_result.p_value)
        null_max_p.append(null_result.max_statistic_p_value)
        planted_p.append(planted_result.p_value)
        planted_max_p.append(planted_result.max_statistic_p_value)
        accepted_rates.extend((null_result.acceptance_rate, planted_result.acceptance_rate))
        applied_injections.append(applied)
        pair_lift_changes.append(
            _pair_count(planted_data, pair) - _pair_count(null_data, pair)
        )

    null_candidate_rejections = sum(p <= alpha for p in null_p)
    null_max_rejections = sum(p <= alpha for p in null_max_p)
    planted_candidate_detections = sum(p <= alpha for p in planted_p)
    planted_max_detections = sum(p <= alpha for p in planted_max_p)

    return {
        "seeds": seeds,
        "permutations_per_condition": permutations,
        "alpha": alpha,
        "pair": list(pair),
        "null": {
            "candidate_rejection_rate": null_candidate_rejections / seeds,
            "candidate_rejection_rate_wilson_95": _wilson_interval(null_candidate_rejections, seeds),
            "max_statistic_rejection_rate": null_max_rejections / seeds,
            "max_statistic_rejection_rate_wilson_95": _wilson_interval(null_max_rejections, seeds),
            "mean_candidate_p": mean(null_p),
            "p_values": null_p,
            "max_statistic_p_values": null_max_p,
        },
        "planted": {
            "candidate_detection_rate": planted_candidate_detections / seeds,
            "candidate_detection_rate_wilson_95": _wilson_interval(planted_candidate_detections, seeds),
            "max_statistic_detection_rate": planted_max_detections / seeds,
            "max_statistic_detection_rate_wilson_95": _wilson_interval(planted_max_detections, seeds),
            "mean_candidate_p": mean(planted_p),
            "p_values": planted_p,
            "max_statistic_p_values": planted_max_p,
            "requested_injections": injections,
            "applied_injections": applied_injections,
            "observed_pair_count_gain": pair_lift_changes,
        },
        "mean_swap_acceptance_rate": mean(accepted_rates),
        "interpretation": (
            "Synthetic diagnostic only; small seed/permutation counts are not "
            "a calibrated scientific conclusion. Inspect p-value resolution, "
            "swap acceptance, and independent-chain mixing before inference."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--permutations", type=int, default=39)
    parser.add_argument("--swaps-per-edge", type=int, default=3)
    parser.add_argument("--injections", type=int, default=12)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed-start", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(run_calibration(
        seeds=args.seeds,
        permutations=args.permutations,
        swaps_per_edge=args.swaps_per_edge,
        injections=args.injections,
        alpha=args.alpha,
        seed_start=args.seed_start,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
