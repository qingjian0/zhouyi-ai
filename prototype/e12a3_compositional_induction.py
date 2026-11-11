"""E12-A3-M0: bounded sparse composition induction over E12-A1 predicates.

This is a deterministic symbolic baseline, not a neural model or a claim of
open-ended concept discovery. Candidate search is bounded and abstains when
the declared search space exceeds its budget.
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from prototype.e12a1_typed_predicate_induction import (
    Example,
    FeatureSpec,
    LearnerView,
    Predicate,
    demo_view,
    propose_predicates,
    validate_view,
)


COMMUTATIVE = {"AND", "OR", "XOR", "ALL_OF", "ANY_OF"}
UNARY = {"NOT"}
BINARY = {"AND", "OR", "XOR"}
NARY = {"ALL_OF", "ANY_OF"}


@dataclass(frozen=True)
class Expr:
    op: str
    children: tuple["Expr | Predicate", ...]

    @property
    def complexity(self) -> int:
        return 1 + sum(child.complexity if isinstance(child, Expr) else child.complexity
                       for child in self.children)

    @property
    def depth(self) -> int:
        return 1 + max((child.depth if isinstance(child, Expr) else 0
                        for child in self.children), default=0)

    def evaluate(self, example: Example) -> int:
        values = tuple(
            child.evaluate(example) if isinstance(child, Expr)
            else child.evaluate(example.value(child.feature))
            for child in self.children
        )
        if self.op == "NOT":
            return 1 - values[0]
        if self.op in ("AND", "ALL_OF"):
            return int(all(values))
        if self.op in ("OR", "ANY_OF"):
            return int(any(values))
        if self.op == "XOR":
            return values[0] ^ values[1]
        raise ValueError(f"unsupported operator: {self.op}")


Candidate = Predicate | Expr


def _predicate_key(p: Predicate) -> tuple:
    return ("P", p.feature, p.input_kind, p.operator, type(p.threshold).__name__, repr(p.threshold))


def canonical_key(candidate: Candidate) -> tuple:
    if isinstance(candidate, Predicate):
        return _predicate_key(candidate)
    children = tuple(canonical_key(child) for child in candidate.children)
    if candidate.op in COMMUTATIVE:
        children = tuple(sorted(children))
    return ("E", candidate.op, children)


def _leaf_features(candidate: Candidate) -> frozenset[str]:
    if isinstance(candidate, Predicate):
        return frozenset((candidate.feature,))
    result: set[str] = set()
    for child in candidate.children:
        result.update(_leaf_features(child))
    return frozenset(result)


def _candidate_order(candidate: Candidate) -> tuple:
    return (candidate.complexity, candidate.depth if isinstance(candidate, Expr) else 0, repr(canonical_key(candidate)))


def generate_candidates(
    primitives: Iterable[Predicate],
    *,
    max_arity: int = 4,
    max_depth: int = 2,
    max_nodes: int = 15,
    max_candidates: int = 20_000,
) -> tuple[Candidate, ...]:
    """Generate a bounded, deterministic set of sparse typed-primitive DAGs.

    Primitive predicates are already typed by A1. Boolean operators only accept
    their binary outputs. Nested candidates combine disjoint feature supports
    to avoid trivial self-reuse in the initial baseline.
    """
    if max_arity < 2 or max_arity > 4:
        raise ValueError("max_arity must be between 2 and 4")
    if max_depth < 1 or max_depth > 2:
        raise ValueError("max_depth must be 1 or 2")
    if max_nodes < 1 or max_candidates < 1:
        raise ValueError("max_nodes and max_candidates must be positive")

    base = tuple(sorted(set(primitives), key=_predicate_key))
    if not base:
        raise ValueError("at least one primitive is required")

    candidates: dict[tuple, Candidate] = {}

    def add(candidate: Candidate) -> None:
        if candidate.complexity <= max_nodes:
            candidates.setdefault(canonical_key(candidate), candidate)
        if len(candidates) > max_candidates:
            raise OverflowError("candidate generation exceeded max_candidates")

    for primitive in base:
        add(primitive)
        add(Expr("NOT", (primitive,)))

    # Sparse n-ary combinations: selecting A,C,E does not require B,D.
    for arity in range(2, min(max_arity, len(base)) + 1):
        for subset in itertools.combinations(base, arity):
            add(Expr("ALL_OF", subset))
            add(Expr("ANY_OF", subset))
    for left, right in itertools.combinations(base, 2):
        add(Expr("XOR", (left, right)))

    if max_depth == 2:
        first_level = tuple(
            candidate for candidate in candidates.values()
            if isinstance(candidate, Expr) and candidate.depth == 1
        )
        for left, right in itertools.combinations(first_level, 2):
            if _leaf_features(left) & _leaf_features(right):
                continue
            for op in ("AND", "OR", "XOR"):
                add(Expr(op, (left, right)))
            if len(candidates) > max_candidates:
                raise OverflowError("candidate generation exceeded max_candidates")

    ordered = tuple(sorted(candidates.values(), key=_candidate_order))
    if len(ordered) > max_candidates:
        raise OverflowError("candidate generation exceeded max_candidates")
    return ordered


def _consistent(candidate: Candidate, examples: tuple[Example, ...]) -> bool:
    if isinstance(candidate, Predicate):
        return all(
            candidate.evaluate(example.value(candidate.feature)) == example.label
            for example in examples
        )
    return all(candidate.evaluate(example) == example.label for example in examples)


def infer_compositions(
    view: LearnerView,
    *,
    max_arity: int = 4,
    max_depth: int = 2,
    max_nodes: int = 9,
    candidate_budget: int = 20_000,
) -> dict[str, Any]:
    """Propose from Train and select with Gate; there is no Test/evaluator input."""
    validate_view(view)
    if candidate_budget < 1:
        raise ValueError("candidate_budget must be positive")
    primitives = propose_predicates(view)
    try:
        candidates = generate_candidates(
            primitives,
            max_arity=max_arity,
            max_depth=max_depth,
            max_nodes=max_nodes,
            max_candidates=candidate_budget,
        )
    except OverflowError:
        return {
            "status": "BUDGET_EXHAUSTED",
            "primitive_count": len(primitives),
            "candidate_count": None,
            "evaluated_count": 0,
            "train_consistent_count": 0,
            "gate_consistent_count": 0,
            "candidates": [],
            "selected": None,
        }

    train_ok = tuple(candidate for candidate in candidates
                     if _consistent(candidate, view.train))
    gate_ok = tuple(candidate for candidate in train_ok
                    if _consistent(candidate, view.gate))
    if len(gate_ok) == 1:
        status, selected = "IDENTIFIABLE", gate_ok[0]
    elif len(gate_ok) > 1:
        status, selected = "AMBIGUOUS", None
    else:
        status, selected = "INCONSISTENT", None

    return {
        "status": status,
        "primitive_count": len(primitives),
        "candidate_count": len(candidates),
        "evaluated_count": len(candidates),
        "train_consistent_count": len(train_ok),
        "gate_consistent_count": len(gate_ok),
        "candidates": gate_ok,
        "selected": selected,
    }


def candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    if isinstance(candidate, Predicate):
        return {"kind": "predicate", **asdict(candidate)}
    return {
        "kind": "expression",
        "op": candidate.op,
        "children": [candidate_to_dict(child) for child in candidate.children],
        "complexity": candidate.complexity,
        "depth": candidate.depth,
    }


def demo_view() -> LearnerView:
    # A,C,E form the target. B and D are independent distractors.
    schema = tuple(FeatureSpec(name, "numeric") for name in ("a", "b", "c", "d", "e"))
    rows = (
        (0, 0, 0, 1, 0),
        (1, 1, 1, 0, 1),
        (1, 0, 1, 1, 1),
        (0, 1, 0, 0, 1),
        (1, 1, 0, 1, 1),
        (0, 0, 1, 0, 1),
        (1, 0, 1, 0, 1),
        (0, 1, 1, 1, 0),
        (1, 1, 1, 1, 1),
        (0, 0, 0, 0, 0),
    )
    def make_example(row: tuple[int, ...]) -> Example:
        values = tuple((name, value) for name, value in zip(("a", "b", "c", "d", "e"), row))
        label = int(bool(row[0] and row[2] and row[4]))
        return Example(values, label)
    examples = tuple(make_example(row) for row in rows)
    return LearnerView(schema, examples[:6], examples[6:])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=30_000)
    parser.add_argument("--max-arity", type=int, default=3)
    parser.add_argument("--max-depth", type=int, default=1)
    args = parser.parse_args()
    result = infer_compositions(demo_view(), candidate_budget=args.budget, max_arity=args.max_arity, max_depth=args.max_depth)
    result["candidates"] = [candidate_to_dict(c) for c in result["candidates"]]
    if result["selected"] is not None:
        result["selected"] = candidate_to_dict(result["selected"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
