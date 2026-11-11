"""N0.11: bounded symbolic operator induction from state transitions.

This is a deliberately small DSL synthesis baseline. It discovers short
compositions of typed primitive transformations from input/output examples.
It does not claim to discover semantic Yijing operators from raw language.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
import math
from typing import Iterable, Sequence


State = tuple[float, ...]


class InductionError(ValueError):
    """Invalid transition data, grammar, or search budget."""


@dataclass(frozen=True, order=True)
class Primitive:
    kind: str
    a: int
    b: int = -1

    def __str__(self) -> str:
        if self.kind in {"neg", "abs"}:
            return f"{self.kind}({self.a})"
        if self.kind == "swap":
            return f"swap({self.a},{self.b})"
        return f"{self.kind}({self.a},{self.b})"


@dataclass(frozen=True)
class Transition:
    before: State
    after: State


@dataclass(frozen=True)
class OperatorProgram:
    steps: tuple[Primitive, ...]

    def apply(self, state: Sequence[float]) -> State:
        current = tuple(float(value) for value in state)
        if not current or any(not math.isfinite(value) for value in current):
            raise InductionError("state must be non-empty and finite")
        for op in self.steps:
            if not 0 <= op.a < len(current):
                raise InductionError("operator index out of range")
            if op.kind in {"neg", "abs"}:
                values = list(current)
                values[op.a] = -values[op.a] if op.kind == "neg" else abs(values[op.a])
                current = tuple(values)
                continue
            if not 0 <= op.b < len(current) or op.a == op.b and op.kind == "swap":
                raise InductionError("invalid binary operator indices")
            values = list(current)
            if op.kind == "swap":
                values[op.a], values[op.b] = values[op.b], values[op.a]
            elif op.kind == "add":
                values[op.a] += values[op.b]
            elif op.kind == "sub":
                values[op.a] -= values[op.b]
            elif op.kind == "max":
                values[op.a] = max(values[op.a], values[op.b])
            elif op.kind == "min":
                values[op.a] = min(values[op.a], values[op.b])
            else:
                raise InductionError(f"unknown primitive: {op.kind}")
            current = tuple(values)
        return current

    def __str__(self) -> str:
        return " -> ".join(str(step) for step in self.steps)


@dataclass(frozen=True)
class InductionCandidate:
    program: OperatorProgram
    train_support: int
    train_total: int
    validation_support: int | None = None
    validation_total: int | None = None

    @property
    def train_accuracy(self) -> float:
        return self.train_support / self.train_total if self.train_total else 0.0

    @property
    def validation_accuracy(self) -> float | None:
        if self.validation_support is None or not self.validation_total:
            return None
        return self.validation_support / self.validation_total


@dataclass(frozen=True)
class InductionReport:
    candidates: tuple[InductionCandidate, ...]
    programs_examined: int
    search_truncated: bool
    grammar_size: int
    max_depth: int


class OperatorInducer:
    """Enumerate a bounded typed DSL and score programs on observed transitions.

    Search is intentionally transparent and exhaustive within its budget.
    The grammar contains coordinate-wise negation/absolute value, swaps, and
    directed binary arithmetic/order operations. It is a baseline for testing
    induction methodology, not a universal operator language.
    """

    def __init__(
        self, dimension: int, *, max_depth: int = 2,
        max_programs: int = 100_000, tolerance: float = 1e-8,
    ) -> None:
        if dimension < 2 or max_depth < 1 or max_programs < 1 or tolerance < 0:
            raise InductionError("invalid grammar or search configuration")
        self.dimension = dimension
        self.max_depth = max_depth
        self.max_programs = max_programs
        self.tolerance = tolerance
        self.grammar = self._build_grammar()

    def _build_grammar(self) -> tuple[Primitive, ...]:
        d = self.dimension
        ops = [Primitive(kind, i) for kind in ("neg", "abs") for i in range(d)]
        ops.extend(
            Primitive("swap", i, j)
            for i, j in combinations(range(d), 2)
        )
        ops.extend(
            Primitive(kind, i, j)
            for kind in ("add", "sub", "max", "min")
            for i in range(d) for j in range(d) if i != j
        )
        return tuple(ops)

    def _matches(self, actual: Sequence[float], expected: Sequence[float]) -> bool:
        return len(actual) == len(expected) and all(
            abs(a - b) <= self.tolerance for a, b in zip(actual, expected)
        )

    def _validate_transitions(self, rows: Iterable[Transition]) -> tuple[Transition, ...]:
        data = tuple(rows)
        if not data:
            raise InductionError("at least one transition is required")
        for row in data:
            if len(row.before) != self.dimension or len(row.after) != self.dimension:
                raise InductionError("transition dimension mismatch")
            if any(not math.isfinite(v) for v in row.before + row.after):
                raise InductionError("transition values must be finite")
        return data

    def _programs(self):
        emitted = 0
        for depth in range(1, self.max_depth + 1):
            for steps in product(self.grammar, repeat=depth):
                if emitted >= self.max_programs:
                    return
                emitted += 1
                yield OperatorProgram(tuple(steps))

    def discover(
        self, training: Iterable[Transition], *,
        validation: Iterable[Transition] = (),
        result_limit: int = 20,
    ) -> InductionReport:
        train = self._validate_transitions(training)
        valid = self._validate_transitions(validation) if validation else ()
        if result_limit < 1:
            raise InductionError("result_limit must be positive")
        candidates = []
        examined = 0
        total_programs = sum(len(self.grammar) ** depth for depth in range(1, self.max_depth + 1))
        truncated = False
        for program in self._programs():
            if examined >= self.max_programs:
                truncated = True
                break
            examined += 1
            support = sum(
                self._matches(program.apply(row.before), row.after)
                for row in train
            )
            if support != len(train):
                continue
            validation_support = sum(
                self._matches(program.apply(row.before), row.after)
                for row in valid
            ) if valid else None
            candidates.append(InductionCandidate(
                program=program,
                train_support=support,
                train_total=len(train),
                validation_support=validation_support,
                validation_total=len(valid) if valid else None,
            ))
        truncated = total_programs > examined
        # Validation labels are reporting-only. Never use them to rank,
        # select, or prune candidate programs; doing so would turn the
        # validation set into a model-selection set and leak evaluation data.
        candidates.sort(key=lambda item: (
            len(item.program.steps),
            str(item.program),
        ))
        return InductionReport(
            candidates=tuple(candidates[:result_limit]),
            programs_examined=examined,
            search_truncated=truncated,
            grammar_size=len(self.grammar),
            max_depth=self.max_depth,
        )

    def evaluate(
        self, program: OperatorProgram, transitions: Iterable[Transition]
    ) -> InductionCandidate:
        rows = self._validate_transitions(transitions)
        support = sum(
            self._matches(program.apply(row.before), row.after) for row in rows
        )
        return InductionCandidate(program, support, len(rows))
