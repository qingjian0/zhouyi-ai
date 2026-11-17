"""Deterministic Monte Carlo calibration for the M54 PC-style CI test.

This validates the Fisher-z partial-correlation test in selected linear-Gaussian
settings. It is not a broad causal-discovery benchmark or evidence of superiority.
"""
import argparse
import json
import random

from prototype.yixiang_pc_skeleton_m54 import _partial_correlation_pvalue


def _wilson_interval(successes, trials, z=1.959963984540054):
    if trials <= 0:
        raise ValueError("trials_must_be_positive")
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    radius = (z * ((p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) ** 0.5)
              / denominator)
    return [max(0.0, center - radius), min(1.0, center + radius)]


def _rate_record(rejections, repetitions):
    return {
        "rejections": rejections,
        "trials": repetitions,
        "rate": rejections / repetitions,
        "wilson_95": _wilson_interval(rejections, repetitions),
    }


def calibrate(*, repetitions=500, sample_sizes=(100, 300), seed=20261114,
              alpha=0.05, effect_sizes=(0.25, 0.4)):
    if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 50:
        raise ValueError("repetitions_must_be_integer_at_least_50")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha_must_be_between_zero_and_one")
    if not sample_sizes or any(not isinstance(n, int) or n < 20 for n in sample_sizes):
        raise ValueError("sample_sizes_must_be_integers_at_least_20")

    rng = random.Random(seed)
    records = []
    for n in sample_sizes:
        marginal_null_rejects = 0
        conditional_null_rejects = 0
        power_by_effect = {str(effect): 0 for effect in effect_sizes}
        for _ in range(repetitions):
            # H0: X and Y are independent standard Gaussians.
            x = [rng.gauss(0.0, 1.0) for _ in range(n)]
            y0 = [rng.gauss(0.0, 1.0) for _ in range(n)]
            if _partial_correlation_pvalue(x, y0, []) < alpha:
                marginal_null_rejects += 1

            # Conditional H0: X <- Z -> Y, with independent noises.
            z = [rng.gauss(0.0, 1.0) for _ in range(n)]
            xc = [0.8 * value + rng.gauss(0.0, 0.6) for value in z]
            yc = [1.1 * value + rng.gauss(0.0, 0.6) for value in z]
            if _partial_correlation_pvalue(xc, yc, [z]) < alpha:
                conditional_null_rejects += 1

            for effect in effect_sizes:
                # H1: standardized bivariate Gaussian with target correlation effect.
                xe = [rng.gauss(0.0, 1.0) for _ in range(n)]
                ye = [effect * value + (1.0 - effect * effect) ** 0.5
                      * rng.gauss(0.0, 1.0) for value in xe]
                if _partial_correlation_pvalue(xe, ye, []) < alpha:
                    power_by_effect[str(effect)] += 1

        records.append({
            "sample_size": n,
            "marginal_null_type_i": _rate_record(marginal_null_rejects, repetitions),
            "conditional_null_type_i": _rate_record(conditional_null_rejects, repetitions),
            "marginal_power": {
                effect: _rate_record(count, repetitions)
                for effect, count in power_by_effect.items()
            },
        })
    return {
        "protocol": "m54-pc-fisher-z-calibration-v0.1",
        "seed": seed,
        "repetitions_per_cell": repetitions,
        "alpha": alpha,
        "sample_sizes": list(sample_sizes),
        "effect_sizes": list(effect_sizes),
        "records": records,
        "limitations": [
            "linear-Gaussian synthetic data only",
            "single-target partial-correlation test, not full PC/FCI",
            "not calibrated for arbitrary dependence, selection, or hidden confounding",
            "Monte Carlo intervals quantify simulation error only",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = calibrate(repetitions=args.repetitions, seed=args.seed)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
