"""Paired multi-seed M55 experiment runner for implemented M54 baselines.

Scenarios are synthetic stress cases, not a substitute for real-world causal
validation. Evaluator truth is supplied only to the scoring harness.
"""
import random

from prototype.yixiang_fair_baselines_m54 import (
    EvaluatorTruth, correlation_screen_baseline, random_baseline,
    run_fair_comparison,
)
from prototype.yixiang_pc_skeleton_m54 import pc_skeleton_baseline


METHODS = ("random", "correlation", "pc_skeleton")
SCENARIOS = (
    "linear_gaussian",
    "linear_weak",
    "linear_near_null",
    "linear_null",
    "nonlinear_quadratic",
    "nonlinear_interaction",
    "non_gaussian_noise",
    "latent_common_cause",
    "selection_collider",
    "measurement_error_proxy",
    "collinear_linear",
    "mechanism_heterogeneity",
)


def _laplace(rng, scale=0.7):
    magnitude = rng.expovariate(1.0 / scale)
    return magnitude if rng.random() < 0.5 else -magnitude


def generate_scenario(name, *, n=240, seed=0):
    if name not in SCENARIOS:
        raise ValueError("unknown_scenario")
    if not isinstance(n, int) or isinstance(n, bool) or n < 80:
        raise ValueError("n_must_be_integer_at_least_80")
    rng = random.Random(seed)
    rows = []
    while len(rows) < n:
        x, z, w = (rng.gauss(0.0, 1.0) for _ in range(3))
        if name == "linear_gaussian":
            y = 1.25 * x + rng.gauss(0.0, 0.8)
            parents = ("x",)
            values = (x, z, w, y)
        elif name == "linear_weak":
            y = 0.30 * x + rng.gauss(0.0, 0.8)
            parents = ("x",)
            values = (x, z, w, y)
        elif name == "linear_near_null":
            y = 0.10 * x + rng.gauss(0.0, 0.8)
            parents = ("x",)
            values = (x, z, w, y)
        elif name == "linear_null":
            y = rng.gauss(0.0, 0.8)
            parents = ()
            values = (x, z, w, y)
        elif name == "nonlinear_quadratic":
            y = (x * x - 1.0) + rng.gauss(0.0, 0.6)
            parents = ("x",)
            values = (x, z, w, y)
        elif name == "nonlinear_interaction":
            y = x * z + rng.gauss(0.0, 0.6)
            parents = ("x", "z")
            values = (x, z, w, y)
        elif name == "non_gaussian_noise":
            y = 1.1 * x + _laplace(rng)
            parents = ("x",)
            values = (x, z, w, y)
        elif name == "latent_common_cause":
            latent = rng.gauss(0.0, 1.0)
            x = latent + rng.gauss(0.0, 0.35)
            y = 1.3 * latent + rng.gauss(0.0, 0.35)
            parents = ()
            values = (x, z, w, y)
        elif name == "selection_collider":
            # X and Y are independent causes of an unobserved selection node.
            # Conditioning the sample on S creates selection-induced association.
            y = rng.gauss(0.0, 1.0)
            selection_score = x + y + rng.gauss(0.0, 0.2)
            if selection_score < 0.9:
                continue
            parents = ()
            values = (x, z, w, y)
        elif name == "measurement_error_proxy":
            latent = rng.gauss(0.0, 1.0)
            x = latent + rng.gauss(0.0, 0.9)
            y = 1.1 * latent + rng.gauss(0.0, 0.5)
            parents = ()
            values = (x, z, w, y)
        elif name == "collinear_linear":
            z = x + rng.gauss(0.0, 0.05)
            y = 1.0 * x + rng.gauss(0.0, 0.8)
            parents = ("x",)
            values = (x, z, w, y)
        else:
            # A hidden regime flips the sign of the direct mechanism.
            # The pooled marginal association can cancel although x is causal in each regime.
            regime_sign = 1.0 if len(rows) % 2 == 0 else -1.0
            y = regime_sign * x + rng.gauss(0.0, 0.4)
            parents = ("x",)
            values = (x, z, w, y)
        row = {"unit_id": len(rows), "x": values[0], "z": values[1],
               "w": values[2], "y": values[3]}
        rows.append(row)
    return rows, parents


def run_paired_suite(*, seeds=range(20), n=240, scenarios=SCENARIOS):
    """Run all implemented baselines on identical train-only scenario/seed data."""
    seeds = tuple(seeds)
    records = []
    for scenario in scenarios:
        if scenario not in SCENARIOS:
            raise ValueError("unknown_scenario")
        for seed in seeds:
            rows, parents = generate_scenario(scenario, n=n, seed=seed)
            train_end = int(n * 0.7)
            validation_end = int(n * 0.85)
            parent_count = max(1, len(parents))
            captured = {}

            def capture(name, adapter):
                def wrapped(context):
                    proposal = adapter(context)
                    captured[name] = tuple(proposal.predicted_parents)
                    return proposal
                return wrapped

            baseline_set = (
                ("random", capture("random", lambda context, current_seed=seed:
                    random_baseline(context, seed=current_seed, parent_count=parent_count))),
                ("correlation", capture("correlation", lambda context:
                    correlation_screen_baseline(context, parent_count=parent_count))),
                ("pc_skeleton", capture("pc_skeleton", pc_skeleton_baseline)),
            )
            comparison = run_fair_comparison(
                rows=rows,
                train_ids=range(train_end),
                validation_ids=range(train_end, validation_end),
                test_ids=range(validation_end, n),
                candidate_variables=("x", "z", "w"),
                target="y",
                evaluator_truth=EvaluatorTruth(tuple(parents)),
                baselines=baseline_set,
                max_samples=train_end,
                max_interventions=0,
                max_cost=0.0,
                interventions_allowed=False,
                min_interventions_for_commit=0,
            )
            for result in comparison.results:
                records.append({
                    "scenario": scenario,
                    "seed": seed,
                    "sample_size": n,
                    "method": result.baseline_id,
                    "predicted_parents": captured[result.baseline_id],
                    "true_parents": tuple(parents),
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1": result.f1,
                    "shd": result.structural_hamming_distance,
                    "budget_violation": result.budget_violation,
                    "invalid_proposal": result.invalid_proposal,
                })
    return records
