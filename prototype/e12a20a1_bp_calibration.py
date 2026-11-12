"""Deterministic calibration of A20-1 belief propagation against A20-0 exact inference."""
from __future__ import annotations

import argparse
import itertools
import json
import random
from dataclasses import asdict

from prototype.e12a20_factor_graph import Budget, Factor, Problem, Variable, infer as infer_exact
from prototype.e12a20a1_belief_propagation import BPBudget, infer_beliefs


def make_problem(seed: int, variable_count: int = 6, *, cycle: bool = False) -> Problem:
    rng = random.Random(seed)
    domain = ("0", "1")
    variables = tuple(Variable(f"x{i}", domain) for i in range(variable_count))
    factors = []
    for index in range(variable_count):
        costs = tuple(((value,), round(rng.uniform(0.0, 2.0), 8)) for value in domain)
        factors.append(Factor(f"unary-{index}", (f"x{index}",), "PRIOR", costs, default_cost=3.0))
    edges = [(f"x{i}", f"x{i+1}") for i in range(variable_count - 1)]
    if cycle and variable_count > 2:
        # Deliberately non-lexicographic factor scope to exercise tuple ordering.
        edges.append((f"x{variable_count-1}", "x0"))
    for index, (left, right) in enumerate(edges):
        assignments = tuple(itertools.product(domain, repeat=2))
        costs = tuple((values, round(rng.uniform(0.0, 2.0), 8)) for values in assignments)
        factors.append(Factor(f"pair-{index}", (left, right), "SOFT", costs, default_cost=3.0))
    return Problem(variables, tuple(factors))


def exact_marginals(problem: Problem) -> dict[str, dict[str, float]]:
    state_space = 1
    for variable in problem.variables:
        state_space *= len(variable.domain)
    exact = infer_exact(problem, budget=Budget(max_assignments=state_space, top_k=state_space))
    weights = [__import__("math").exp(-item.energy) for item in exact.hypotheses]
    normalizer = sum(weights)
    output = {variable.variable_id: {value: 0.0 for value in variable.domain}
              for variable in problem.variables}
    for hypothesis, weight in zip(exact.hypotheses, weights):
        for variable_id, value in hypothesis.assignment:
            output[variable_id][value] += weight / normalizer
    return output


def evaluate(seed: int, variable_count: int = 6, *, cycle: bool = False) -> dict:
    problem = make_problem(seed, variable_count, cycle=cycle)
    exact = exact_marginals(problem)
    bp = infer_beliefs(problem, budget=BPBudget(
        max_iterations=200, max_message_updates=200_000,
        max_factor_entries=100_000, max_factor_evaluations=2_000_000,
        tolerance=1e-12, damping=0.5 if cycle else 1.0,
    ))
    errors = [
        abs(probability - exact[marginal.variable_id][value])
        for marginal in bp.marginals
        for value, probability in marginal.probabilities
    ]
    return {
        "seed": seed,
        "topology": "cycle" if cycle else "chain_tree",
        "variables": variable_count,
        "factor_count": len(problem.factors),
        "status": bp.status,
        "iterations": bp.iterations,
        "message_updates": bp.message_updates,
        "factor_entries": bp.factor_entries,
        "factor_evaluations": bp.factor_evaluations,
        "max_marginal_abs_error": max(errors, default=None),
        "mean_marginal_abs_error": sum(errors) / len(errors) if errors else None,
    }


def run_calibration(seeds: tuple[int, ...], variable_count: int = 6) -> dict:
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be non-empty and unique")
    tree = [evaluate(seed, variable_count, cycle=False) for seed in seeds]
    cycle = [evaluate(seed, variable_count, cycle=True) for seed in seeds]
    tree_errors = [item["max_marginal_abs_error"] for item in tree]
    cycle_errors = [item["max_marginal_abs_error"] for item in cycle if item["max_marginal_abs_error"] is not None]
    return {
        "protocol": "A20-1 BP vs A20-0 exact marginal calibration",
        "seeds": list(seeds),
        "variable_count": variable_count,
        "tree": {
            "runs": tree,
            "converged": sum(item["status"] == "CONVERGED" for item in tree),
            "max_abs_error": max(tree_errors, default=None),
        },
        "cycle": {
            "runs": cycle,
            "converged": sum(item["status"] == "CONVERGED" for item in cycle),
            "max_abs_error": max(cycle_errors, default=None),
        },
        "interpretation": {
            "tree": "Exact sum-product marginals are expected on these tree-structured graphs.",
            "cycle": "Loopy belief propagation is approximate; errors and convergence are measured, not assumed.",
            "performance": "Operation counts are reported; this script makes no wall-clock speedup claim.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--variables", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.seeds < 1 or args.variables < 2:
        parser.error("--seeds must be positive and --variables must be at least 2")
    report = run_calibration(tuple(range(args.start_seed, args.start_seed + args.seeds)), args.variables)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
