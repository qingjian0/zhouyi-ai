"""Typed Boolean relation operators for the next CPG-EI benchmark track.

This module defines deterministic rule semantics only. It deliberately does not
claim that the current learner can discover these operators from observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable


OPERATORS = ("xor", "and", "or", "nand", "implies", "threshold", "conditional_xor")


@dataclass(frozen=True)
class RelationRule:
    operator: str
    support: tuple[int, ...]
    threshold: int | None = None
    context_index: int | None = None
    context_value: int = 1

    def validate(self, input_dim: int) -> None:
        if self.operator not in OPERATORS:
            raise ValueError(f"unsupported operator: {self.operator}")
        if not self.support or len(set(self.support)) != len(self.support):
            raise ValueError("support must be non-empty and contain unique ordered indices")
        if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= input_dim
               for i in self.support):
            raise ValueError("support index is outside input dimensions")
        if self.operator == "implies" and len(self.support) != 2:
            raise ValueError("implies requires exactly two ordered roles: antecedent, consequent")
        if self.operator == "threshold":
            if (isinstance(self.threshold, bool) or not isinstance(self.threshold, int)
                    or not 1 <= self.threshold <= len(self.support)):
                raise ValueError("threshold must be between 1 and support arity")
        elif self.threshold is not None:
            raise ValueError("threshold is only valid for threshold operator")
        if self.operator == "conditional_xor":
            if (isinstance(self.context_index, bool) or not isinstance(self.context_index, int)
                    or not 0 <= self.context_index < input_dim):
                raise ValueError("conditional_xor requires a valid context_index")
            if self.context_value not in (0, 1):
                raise ValueError("context_value must be binary")
        elif self.context_index is not None or self.context_value != 1:
            raise ValueError("context fields are only valid for conditional_xor")


def evaluate_rule(state: Iterable[int], rule: RelationRule) -> int:
    values = tuple(state)
    if not values or any(isinstance(v, bool) is False and v not in (0, 1) for v in values):
        raise ValueError("state must contain only binary values")
    if any(v not in (0, 1) for v in values):
        raise ValueError("state must contain only binary values")
    rule.validate(len(values))
    selected = tuple(values[index] for index in rule.support)
    op = rule.operator
    if op == "xor":
        return sum(selected) % 2
    if op == "and":
        return int(all(selected))
    if op == "or":
        return int(any(selected))
    if op == "nand":
        return int(not all(selected))
    if op == "implies":
        antecedent, consequent = selected
        return int((not antecedent) or consequent)
    if op == "threshold":
        return int(sum(selected) >= rule.threshold)
    if op == "conditional_xor":
        if values[rule.context_index] != rule.context_value:
            return 0
        return sum(selected) % 2
    raise AssertionError("validated operator was not dispatched")


def truth_table(input_dim: int, rule: RelationRule) -> tuple[tuple[tuple[int, ...], int], ...]:
    if isinstance(input_dim, bool) or not isinstance(input_dim, int) or input_dim < 1:
        raise ValueError("input_dim must be a positive integer")
    rule.validate(input_dim)
    return tuple(
        (state, evaluate_rule(state, rule))
        for state in product((0, 1), repeat=input_dim)
    )


def rule_manifest(rule: RelationRule, input_dim: int) -> dict:
    rule.validate(input_dim)
    return {
        "operator": rule.operator,
        "support": list(rule.support),
        "role_order": list(rule.support) if rule.operator == "implies" else None,
        "threshold": rule.threshold,
        "context_index": rule.context_index,
        "context_value": rule.context_value if rule.operator == "conditional_xor" else None,
        "input_dim": input_dim,
    }
