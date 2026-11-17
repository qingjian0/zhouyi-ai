"""E12-A20-0: exact finite-domain factor-graph reference inference.

This is a small, deterministic reference solver for validating factor semantics.
It is NOT yet a parallel message-passing engine or a scalable neural architecture.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Iterable


_FACTOR_KINDS = {"HARD", "SOFT", "EVIDENCE", "PRIOR"}


@dataclass(frozen=True, order=True)
class Variable:
    variable_id: str
    domain: tuple[str, ...]
    variable_type: str = "categorical"
    scope: str = "default"

    def __post_init__(self):
        if not isinstance(self.variable_id, str) or not self.variable_id.strip():
            raise ValueError("variable_id is required")
        if not isinstance(self.variable_type, str) or not self.variable_type.strip():
            raise ValueError("variable_type is required")
        if not isinstance(self.scope, str) or not self.scope.strip():
            raise ValueError("scope is required")
        if not self.domain or any(not isinstance(x, str) or not x.strip() for x in self.domain):
            raise ValueError("domain must contain non-empty string values")
        if tuple(sorted(set(self.domain))) != self.domain:
            raise ValueError("domain values must be sorted and unique")


@dataclass(frozen=True)
class Factor:
    factor_id: str
    variable_ids: tuple[str, ...]
    kind: str
    costs: tuple[tuple[tuple[str, ...], float], ...] = ()
    forbidden_assignments: tuple[tuple[str, ...], ...] = ()
    default_cost: float | None = 0.0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.factor_id, str) or not self.factor_id.strip():
            raise ValueError("factor_id is required")
        if not self.variable_ids or any(not isinstance(x, str) or not x.strip() for x in self.variable_ids):
            raise ValueError("factor must reference at least one variable")
        if len(set(self.variable_ids)) != len(self.variable_ids):
            raise ValueError("factor variable IDs must be unique")
        if self.kind not in _FACTOR_KINDS:
            raise ValueError("unsupported factor kind")
        if tuple(sorted(set(self.evidence_refs))) != self.evidence_refs:
            raise ValueError("evidence_refs must be sorted and unique")
        if any(not isinstance(x, str) or not x.strip() for x in self.evidence_refs):
            raise ValueError("evidence refs must be non-empty strings")
        if self.kind == "HARD":
            if self.costs or self.default_cost is not None:
                raise ValueError("hard factors use forbidden_assignments, not costs")
        else:
            if self.forbidden_assignments:
                raise ValueError("only hard factors may declare forbidden assignments")
            if isinstance(self.default_cost, bool) or not isinstance(self.default_cost, (int, float)) or not math.isfinite(self.default_cost) or self.default_cost < 0:
                raise ValueError("soft factor default_cost must be finite and non-negative")
        if self.kind == "EVIDENCE" and not self.evidence_refs:
            raise ValueError("evidence factors require evidence_refs")
        cost_keys = [key for key, _ in self.costs]
        if len(cost_keys) != len(set(cost_keys)):
            raise ValueError("duplicate factor cost assignments")
        if any(not isinstance(key, tuple) or len(key) != len(self.variable_ids)
               or any(not isinstance(v, str) for v in key) for key in cost_keys):
            raise ValueError("factor cost assignment has invalid arity or values")
        for _, cost in self.costs:
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise ValueError("factor costs must be finite and non-negative")
        if len(set(self.forbidden_assignments)) != len(self.forbidden_assignments):
            raise ValueError("duplicate forbidden assignments")
        if any(not isinstance(key, tuple) or len(key) != len(self.variable_ids)
               or any(not isinstance(v, str) for v in key)
               for key in self.forbidden_assignments):
            raise ValueError("forbidden assignment has invalid arity or values")


@dataclass(frozen=True)
class Problem:
    variables: tuple[Variable, ...]
    factors: tuple[Factor, ...]

    def __post_init__(self):
        if not self.variables:
            raise ValueError("problem must contain variables")
        variable_ids = [v.variable_id for v in self.variables]
        factor_ids = [f.factor_id for f in self.factors]
        if len(variable_ids) != len(set(variable_ids)):
            raise ValueError("duplicate variable IDs")
        if len(factor_ids) != len(set(factor_ids)):
            raise ValueError("duplicate factor IDs")
        domains = {v.variable_id: set(v.domain) for v in self.variables}
        for factor in self.factors:
            if any(variable_id not in domains for variable_id in factor.variable_ids):
                raise ValueError("factor references unknown variable")
            for key, _ in factor.costs:
                if any(value not in domains[var_id]
                       for var_id, value in zip(factor.variable_ids, key)):
                    raise ValueError("factor cost references value outside variable domain")
            for key in factor.forbidden_assignments:
                if any(value not in domains[var_id]
                       for var_id, value in zip(factor.variable_ids, key)):
                    raise ValueError("forbidden assignment references value outside variable domain")


@dataclass(frozen=True)
class Budget:
    max_assignments: int = 100_000
    top_k: int = 20

    def __post_init__(self):
        for name in ("max_assignments", "top_k"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(name + " must be a positive integer")


@dataclass(frozen=True)
class Hypothesis:
    assignment: tuple[tuple[str, str], ...]
    energy: float
    evaluated_factor_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    factor_costs: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class InferenceResult:
    status: str
    hypotheses: tuple[Hypothesis, ...]
    assignments_examined: int
    feasible_assignments: int
    rejected_assignments: int
    hard_conflict_counts: tuple[tuple[str, int], ...]
    state_space_size: int
    budget_limit: int


def _factor_value(factor: Factor, assignment: dict[str, str]) -> float | None:
    key = tuple(assignment[var_id] for var_id in factor.variable_ids)
    if factor.kind == "HARD":
        return None if key in factor.forbidden_assignments else 0.0
    costs = dict(factor.costs)
    return float(costs.get(key, factor.default_cost))


def infer(problem: Problem, *, budget: Budget = Budget()) -> InferenceResult:
    """Enumerate assignments in canonical order; return partial results if budget ends."""
    variables = tuple(sorted(problem.variables, key=lambda item: item.variable_id))
    factors = tuple(sorted(problem.factors, key=lambda item: item.factor_id))
    state_space_size = math.prod(len(variable.domain) for variable in variables)
    assignments_examined = 0
    feasible_assignments = 0
    rejected_assignments = 0
    conflict_counts = {factor.factor_id: 0 for factor in factors if factor.kind == "HARD"}
    hypotheses = []

    domain_product = itertools.product(*(variable.domain for variable in variables))
    for values in domain_product:
        if assignments_examined >= budget.max_assignments:
            break
        assignments_examined += 1
        assignment = {variable.variable_id: value for variable, value in zip(variables, values)}
        factor_costs = []
        conflicts = []
        for factor in factors:
            value = _factor_value(factor, assignment)
            if value is None:
                conflicts.append(factor.factor_id)
            else:
                factor_costs.append((factor.factor_id, value))
        if conflicts:
            rejected_assignments += 1
            for factor_id in conflicts:
                conflict_counts[factor_id] += 1
            continue
        feasible_assignments += 1
        energy = math.fsum(cost for _, cost in factor_costs)
        evidence_refs = tuple(sorted({ref for factor in factors for ref in factor.evidence_refs}))
        hypotheses.append(Hypothesis(
            tuple((variable.variable_id, assignment[variable.variable_id]) for variable in variables),
            energy,
            tuple(factor.factor_id for factor in factors),
            evidence_refs,
            tuple(factor_costs),
        ))

    exhausted = assignments_examined < state_space_size
    status = "BUDGET_EXHAUSTED" if exhausted else (
        "CONVERGED" if hypotheses else "NO_FEASIBLE_ASSIGNMENT"
    )
    hypotheses.sort(key=lambda item: (item.energy, item.assignment))
    return InferenceResult(
        status,
        tuple(hypotheses[:budget.top_k]),
        assignments_examined,
        feasible_assignments,
        rejected_assignments,
        tuple(sorted(conflict_counts.items())),
        state_space_size,
        budget.max_assignments,
    )
