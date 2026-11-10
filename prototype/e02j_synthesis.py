"""E02-J Level-A typed expression synthesis core.

This is an executable program-synthesis prototype over a declared, finite
integer DSL. It tests composition of known primitives; it does NOT establish
discovery of new primitive operators or open-world intelligence.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from numbers import Integral
from typing import Callable, Sequence


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple["Expr", ...] = ()
    value: int | None = None

    def __post_init__(self) -> None:
        if self.op not in {"var", "const", "add", "sub", "mul"}:
            raise ValueError(f"unsupported expression operator: {self.op}")
        if self.op in {"var", "const"}:
            if self.args or isinstance(self.value, bool) or not isinstance(self.value, Integral):
                raise ValueError("variable and constant nodes require one integer value and no children")
            if self.op == "var" and self.value < 0:
                raise ValueError("variable index must be non-negative")
        elif len(self.args) != 2 or self.value is not None:
            raise ValueError("binary operator nodes require exactly two children and no value")

    def render(self) -> str:
        if self.op == "var":
            return f"x{self.value}"
        if self.op == "const":
            return str(self.value)
        left, right = self.args
        symbol = {"add": "+", "sub": "-", "mul": "*"}[self.op]
        return f"({left.render()} {symbol} {right.render()})"


def variable(index: int) -> Expr:
    if isinstance(index, bool) or not isinstance(index, Integral) or index < 0:
        raise ValueError("variable index must be a non-negative integer")
    return Expr("var", value=int(index))


def constant(value: int, modulus: int) -> Expr:
    if isinstance(modulus, bool) or not isinstance(modulus, Integral) or modulus < 2:
        raise ValueError("modulus must be an integer >= 2")
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError("constant value must be an integer")
    return Expr("const", value=int(value) % int(modulus))


def evaluate(expr: Expr, inputs: Sequence[int], modulus: int) -> int:
    if isinstance(modulus, bool) or not isinstance(modulus, Integral) or modulus < 2:
        raise ValueError("modulus must be an integer >= 2")
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in inputs):
        raise ValueError("input values must be integers")
    if expr.op == "var":
        assert expr.value is not None
        if expr.value >= len(inputs):
            raise ValueError("expression references an unavailable input")
        return int(inputs[expr.value]) % int(modulus)
    if expr.op == "const":
        assert expr.value is not None
        return int(expr.value) % int(modulus)
    if expr.op not in {"add", "sub", "mul"} or len(expr.args) != 2:
        raise ValueError(f"unsupported or malformed operator: {expr.op}")
    left = evaluate(expr.args[0], inputs, modulus)
    right = evaluate(expr.args[1], inputs, modulus)
    if expr.op == "add":
        return (left + right) % int(modulus)
    if expr.op == "sub":
        return (left - right) % int(modulus)
    return (left * right) % int(modulus)


def _depth(expr: Expr) -> int:
    return 0 if not expr.args else 1 + max(_depth(arg) for arg in expr.args)


def _size(expr: Expr) -> int:
    return 1 + sum(_size(arg) for arg in expr.args)


def _semantic_key(expr: Expr, domain: Sequence[tuple[int, ...]], modulus: int) -> tuple[int, ...]:
    return tuple(evaluate(expr, row, modulus) for row in domain)


def _canonical_pair(op: str, left: Expr, right: Expr) -> tuple[Expr, Expr]:
    if op in {"add", "mul"} and left.render() > right.render():
        return right, left
    return left, right


def enumerate_programs(
    variable_indices: Sequence[int],
    *,
    modulus: int = 3,
    max_depth: int = 2,
    domain: Sequence[tuple[int, ...]] | None = None,
) -> list[Expr]:
    """Generate typed integer ASTs bottom-up and semantic-deduplicate them.

    variable_indices are the only input positions available to the grammar.
    The optional domain is used only to remove semantically equivalent ASTs;
    it supplies no target labels or hidden-rule information.
    """
    if isinstance(modulus, bool) or not isinstance(modulus, Integral) or modulus < 2:
        raise ValueError("modulus must be an integer >= 2")
    if isinstance(max_depth, bool) or not isinstance(max_depth, Integral) or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")
    indices = tuple(variable_indices)
    if (not indices or any(isinstance(i, bool) or not isinstance(i, Integral) or i < 0 for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError("variable_indices must be unique non-negative integers")
    indices = tuple(int(i) for i in indices)
    if domain is None:
        domain = tuple(product(range(modulus), repeat=len(indices)))
        # Domain rows are role-ordered; map each role to its original position.
        width = max(indices) + 1
        expanded = []
        for row in domain:
            full = [0] * width
            for index, value in zip(indices, row):
                full[index] = value
            expanded.append(tuple(full))
        domain = tuple(expanded)
    else:
        domain = tuple(tuple(row) for row in domain)
        if any(max(indices) >= len(row) for row in domain):
            raise ValueError("domain row does not contain every selected variable")

    leaves = [variable(index) for index in indices]
    leaves.extend(constant(value, modulus) for value in range(modulus))
    retained: dict[tuple[int, ...], Expr] = {}
    frontier = leaves
    for expr in leaves:
        retained.setdefault(_semantic_key(expr, domain, modulus), expr)

    all_by_depth: list[Expr] = list(leaves)
    for _ in range(max_depth):
        next_frontier: list[Expr] = []
        pool = all_by_depth
        for op in ("add", "sub", "mul"):
            for left in pool:
                for right in pool:
                    ordered_left, ordered_right = _canonical_pair(op, left, right)
                    candidate = Expr(op, (ordered_left, ordered_right))
                    if _depth(candidate) > max_depth:
                        continue
                    key = _semantic_key(candidate, domain, modulus)
                    previous = retained.get(key)
                    if previous is None or (_size(candidate), candidate.render()) < (
                        _size(previous), previous.render()
                    ):
                        retained[key] = candidate
                        next_frontier.append(candidate)
        all_by_depth.extend(next_frontier)
    return sorted(retained.values(), key=lambda item: (_size(item), item.render()))


def synthesize(
    observations: Sequence[tuple[tuple[int, ...], int]],
    programs: Sequence[Expr],
    *,
    modulus: int = 3,
) -> Expr | None:
    """Return the shortest program consistent with all observed examples."""
    if not observations:
        raise ValueError("at least one observation is required")
    for inputs, output in observations:
        if not 0 <= output < modulus:
            raise ValueError("observed output is outside the declared type")
    for expr in programs:
        if all(evaluate(expr, inputs, modulus) == output
               for inputs, output in observations):
            return expr
    return None


CounterexampleOracle = Callable[[Expr], tuple[tuple[int, ...], int] | None]


@dataclass(frozen=True)
class SynthesisResult:
    expression: Expr | None
    observations: tuple[tuple[tuple[int, ...], int], ...]
    counterexamples: int
    status: str


def cegis(
    initial_observations: Sequence[tuple[tuple[int, ...], int]],
    programs: Sequence[Expr],
    counterexample_oracle: CounterexampleOracle,
    *,
    modulus: int = 3,
    query_budget: int = 20,
) -> SynthesisResult:
    """Counterexample-guided synthesis; oracle reveals one counterexample at a time."""
    if query_budget < 0:
        raise ValueError("query_budget must be non-negative")
    observations = list(initial_observations)
    seen = {inputs for inputs, _ in observations}
    for _ in range(query_budget):
        candidate = synthesize(observations, programs, modulus=modulus)
        if candidate is None:
            return SynthesisResult(None, tuple(observations), len(observations) - len(initial_observations), "no_candidate")
        counterexample = counterexample_oracle(candidate)
        if counterexample is None:
            return SynthesisResult(candidate, tuple(observations), len(observations) - len(initial_observations), "verified")
        inputs, output = counterexample
        if inputs in seen:
            raise RuntimeError("counterexample oracle repeated an observed input")
        seen.add(inputs)
        observations.append((inputs, output))
    # Preserve the best consistent proposal, but do not label it verified:
    # no oracle call remains to check it after the final counterexample.
    candidate = synthesize(observations, programs, modulus=modulus)
    return SynthesisResult(candidate, tuple(observations), len(observations) - len(initial_observations), "budget_exhausted")


def ternary_domain(variable_indices: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    """Full evaluator domain for selected ternary roles, expanded to input positions."""
    indices = tuple(variable_indices)
    if (not indices or any(isinstance(i, bool) or not isinstance(i, Integral) or i < 0 for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError("variable_indices must be unique non-negative integers")
    indices = tuple(int(i) for i in indices)
    width = max(indices) + 1
    rows = []
    for role_values in product(range(3), repeat=len(indices)):
        row = [0] * width
        for index, value in zip(indices, role_values):
            row[index] = value
        rows.append(tuple(row))
    return tuple(rows)
