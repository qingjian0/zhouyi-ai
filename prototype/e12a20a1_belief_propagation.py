"""E12-A20-1: synchronous sum-product belief propagation.

Uses E12-A20-0 factor semantics and exact local factor tables. This is a
reference message-passing implementation, not a claim of universal speedup.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from prototype.e12a20_factor_graph import Factor, Problem


@dataclass(frozen=True)
class BPBudget:
    max_iterations: int = 100
    max_message_updates: int = 100_000
    max_factor_entries: int = 100_000
    max_factor_evaluations: int = 1_000_000
    tolerance: float = 1e-10
    damping: float = 0.5

    def __post_init__(self):
        for name in ("max_iterations", "max_message_updates", "max_factor_entries", "max_factor_evaluations"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(name + " must be a positive integer")
        if isinstance(self.tolerance, bool) or not isinstance(self.tolerance, (int, float)) or not math.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("tolerance must be finite and positive")
        if isinstance(self.damping, bool) or not isinstance(self.damping, (int, float)) or not math.isfinite(self.damping) or not 0 < self.damping <= 1:
            raise ValueError("damping must be in (0, 1]")


@dataclass(frozen=True)
class Marginal:
    variable_id: str
    probabilities: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class BPResult:
    status: str
    marginals: tuple[Marginal, ...]
    iterations: int
    message_updates: int
    factor_entries: int
    factor_evaluations: int
    max_message_delta: float
    evidence_refs: tuple[str, ...]


def _logsumexp(values):
    values = tuple(values)
    if not values or all(value == -math.inf for value in values):
        return -math.inf
    maximum = max(values)
    return maximum + math.log(math.fsum(math.exp(value - maximum) for value in values if value != -math.inf))


def _normalize(log_values):
    normalizer = _logsumexp(log_values)
    if normalizer == -math.inf:
        return tuple(-math.inf for _ in log_values)
    return tuple(value - normalizer if value != -math.inf else -math.inf for value in log_values)


def _probabilities(log_values):
    normalized = _normalize(log_values)
    if all(value == -math.inf for value in normalized):
        return tuple(0.0 for _ in normalized)
    return tuple(math.exp(value) if value != -math.inf else 0.0 for value in normalized)


def _factor_log_potential(factor: Factor, values: tuple[str, ...]) -> float:
    key_to_cost = dict(factor.costs)
    if factor.kind == "HARD":
        return -math.inf if values in factor.forbidden_assignments else 0.0
    cost = key_to_cost.get(values, factor.default_cost)
    return -float(cost)


def _damp(old, new, amount):
    if amount == 1.0:
        return _normalize(new)
    left = math.log1p(-amount)
    right = math.log(amount)
    mixed = []
    for old_value, new_value in zip(old, new):
        a = left + old_value if old_value != -math.inf else -math.inf
        b = right + new_value if new_value != -math.inf else -math.inf
        mixed.append(_logsumexp((a, b)))
    return _normalize(mixed)


def _delta(old, new):
    a, b = _probabilities(old), _probabilities(new)
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def infer_beliefs(problem: Problem, *, budget: BPBudget = BPBudget()) -> BPResult:
    """Run deterministic synchronous sum-product updates in log space."""
    variables = {item.variable_id: item for item in problem.variables}
    factors = {item.factor_id: item for item in problem.factors}
    edges = tuple(sorted((factor.factor_id, variable_id)
                         for factor in problem.factors
                         for variable_id in factor.variable_ids))
    factor_entries = sum(
        math.prod(len(variables[var_id].domain) for var_id in factor.variable_ids)
        for factor in problem.factors
    )
    factor_evaluations_per_iteration = sum(
        len(factor.variable_ids) * math.prod(len(variables[var_id].domain) for var_id in factor.variable_ids)
        for factor in problem.factors
    )
    evidence_refs = tuple(sorted({ref for factor in problem.factors for ref in factor.evidence_refs}))
    if factor_entries > budget.max_factor_entries or factor_evaluations_per_iteration > budget.max_factor_evaluations:
        return BPResult("BUDGET_EXHAUSTED", (), 0, 0, factor_entries, 0, math.inf, evidence_refs)

    variable_neighbors = {
        variable_id: tuple(factor_id for factor_id, edge_variable in edges if edge_variable == variable_id)
        for variable_id in variables
    }
    # Preserve each factor's declared scope order: cost/forbidden tuples are
    # encoded in Factor.variable_ids order, not lexicographic edge order.
    factor_neighbors = {
        factor_id: tuple(factors[factor_id].variable_ids)
        for factor_id in factors
    }
    vf = {}
    fv = {}
    for factor_id, variable_id in edges:
        uniform = -math.log(len(variables[variable_id].domain))
        vf[(variable_id, factor_id)] = tuple(uniform for _ in variables[variable_id].domain)
        fv[(factor_id, variable_id)] = tuple(uniform for _ in variables[variable_id].domain)

    updates_per_iteration = 2 * len(edges)
    iterations = 0
    updates = 0
    factor_evaluations = 0
    max_delta = math.inf
    status = "ITERATION_LIMIT"

    for iteration in range(1, budget.max_iterations + 1):
        if (updates + updates_per_iteration > budget.max_message_updates
                or factor_evaluations + factor_evaluations_per_iteration > budget.max_factor_evaluations):
            status = "BUDGET_EXHAUSTED"
            break
        next_vf = {}
        next_fv = {}

        # Variable -> factor messages, all read from the previous iteration.
        for factor_id, variable_id in edges:
            variable = variables[variable_id]
            incoming = [fv[(other_factor, variable_id)]
                        for other_factor in variable_neighbors[variable_id]
                        if other_factor != factor_id]
            raw = tuple(math.fsum(message[index] for message in incoming)
                        for index in range(len(variable.domain)))
            next_vf[(variable_id, factor_id)] = _damp(
                vf[(variable_id, factor_id)], _normalize(raw), budget.damping
            )

        # Factor -> variable messages, also read only from previous iteration.
        for factor_id, variable_id in edges:
            factor = factors[factor_id]
            scope = factor_neighbors[factor_id]
            target_domain = variables[variable_id].domain
            accumulators = [[] for _ in target_domain]
            other_ids = tuple(item for item in scope if item != variable_id)
            other_domains = tuple(variables[item].domain for item in other_ids)
            for other_values in itertools.product(*other_domains):
                partial = dict(zip(other_ids, other_values))
                incoming_sum = math.fsum(
                    vf[(other_id, factor_id)][variables[other_id].domain.index(partial[other_id])]
                    for other_id in other_ids
                )
                for target_value_index, target_value in enumerate(target_domain):
                    assignment = dict(partial)
                    assignment[variable_id] = target_value
                    ordered_values = tuple(assignment[item] for item in scope)
                    potential = _factor_log_potential(factor, ordered_values)
                    if potential != -math.inf and incoming_sum != -math.inf:
                        accumulators[target_value_index].append(potential + incoming_sum)
            raw = tuple(_logsumexp(values) for values in accumulators)
            next_fv[(factor_id, variable_id)] = _damp(
                fv[(factor_id, variable_id)], _normalize(raw), budget.damping
            )

        deltas = [_delta(vf[key], next_vf[key]) for key in vf]
        deltas.extend(_delta(fv[key], next_fv[key]) for key in fv)
        max_delta = max(deltas, default=0.0)
        vf, fv = next_vf, next_fv
        iterations = iteration
        updates += updates_per_iteration
        factor_evaluations += factor_evaluations_per_iteration
        if max_delta <= budget.tolerance:
            status = "CONVERGED"
            break

    marginals = []
    inconsistent = False
    for variable_id in sorted(variables):
        variable = variables[variable_id]
        incoming = [fv[(factor_id, variable_id)] for factor_id in variable_neighbors[variable_id]]
        raw = tuple(math.fsum(message[index] for message in incoming)
                    for index in range(len(variable.domain)))
        probs = _probabilities(raw)
        if math.fsum(probs) == 0.0:
            inconsistent = True
        else:
            total = math.fsum(probs)
            probs = tuple(value / total for value in probs)
        marginals.append(Marginal(variable_id, tuple(zip(variable.domain, probs))))

    if inconsistent:
        status = "INCONSISTENT_MESSAGES"
    return BPResult(status, tuple(marginals), iterations, updates,
                    factor_entries, factor_evaluations, max_delta, evidence_refs)
