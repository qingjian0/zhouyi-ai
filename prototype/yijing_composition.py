"""Bounded composition planning for typed YJ-01 operator contracts.

This planner validates *contract-level* compositions only. It does not execute
operators or claim that a type-compatible chain is semantically valid; runtime
preconditions, evidence and context must still be checked by each operator.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from prototype.yijing_operators import OPERATOR_REGISTRY, OperatorContract


@dataclass(frozen=True)
class OperatorPlan:
    operators: tuple[str, ...]
    available_types: tuple[str, ...]
    target_type: str


@dataclass(frozen=True)
class PlanningReport:
    plans: tuple[OperatorPlan, ...]
    explored_states: int
    budget_exhausted: bool


class CompositionPlanningError(ValueError):
    pass


class CompositionPlanner:
    def __init__(self, registry: Mapping[str, OperatorContract] = OPERATOR_REGISTRY):
        self.registry = dict(registry)
        if any(name != contract.name for name, contract in self.registry.items()):
            raise CompositionPlanningError("registry keys must match contract names")

    @staticmethod
    def _can_apply(contract: OperatorContract, available: Counter[str]) -> bool:
        required = Counter(contract.input_types)
        return all(available[k] >= count for k, count in required.items())

    def plan(
        self,
        input_types: Sequence[str],
        target_type: str,
        *,
        max_depth: int = 4,
        max_plans: int = 32,
        max_states: int = 10_000,
    ) -> PlanningReport:
        if not input_types or not target_type:
            raise CompositionPlanningError("input_types and target_type are required")
        if max_depth < 1 or max_plans < 1 or max_states < 1:
            raise CompositionPlanningError("planning budgets must be positive")
        if any(not item for item in input_types):
            raise CompositionPlanningError("input type names cannot be empty")

        initial = Counter(input_types)
        plans: list[OperatorPlan] = []
        explored = 0
        exhausted = False

        def visit(
            available: Counter[str],
            path: tuple[str, ...],
            used: frozenset[str],
        ) -> None:
            nonlocal explored, exhausted
            if len(plans) >= max_plans or explored >= max_states:
                exhausted = True
                return
            explored += 1
            if path and available[target_type] > initial[target_type]:
                plans.append(OperatorPlan(
                    operators=path,
                    available_types=tuple(sorted(
                        item for item, count in available.items()
                        for _ in range(count)
                    )),
                    target_type=target_type,
                ))
                return
            if len(path) >= max_depth:
                return

            for name in sorted(self.registry):
                if name in used:
                    continue
                contract = self.registry[name]
                if not self._can_apply(contract, available):
                    continue
                next_available = available.copy()
                next_available[contract.output_type] += 1
                visit(next_available, path + (name,), used | {name})
                if len(plans) >= max_plans or explored >= max_states:
                    exhausted = True
                    return

        visit(initial, (), frozenset())
        return PlanningReport(tuple(plans), explored, exhausted)

    def parallel_frontier(self, input_types: Iterable[str]) -> tuple[str, ...]:
        """Return all operators independently applicable to the same input set."""
        available = Counter(input_types)
        return tuple(
            name for name, contract in sorted(self.registry.items())
            if self._can_apply(contract, available)
        )
