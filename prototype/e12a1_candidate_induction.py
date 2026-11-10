"""E12-A1: a tiny, auditable candidate-predicate induction prototype.

This is a finite DSL experiment, not open-world concept learning. Candidate
expressions are generated from learner-visible observations, then ranked on
Support and an independent Gate. Locked Test and oracle truth are deliberately
absent from the learner API.
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class Example:
    values: tuple[int, ...]
    label: int


@dataclass(frozen=True, order=True)
class Candidate:
    op: str
    args: tuple[int, ...]

    @property
    def expression(self) -> str:
        if self.op in {"ge", "eq"}:
            return f"x{self.args[0]} { '>=' if self.op == 'ge' else '==' } {self.args[1]}"
        if self.op in {"even", "odd"}:
            return f"x{self.args[0]} is {self.op}"
        if self.op in {"gt", "lt", "eq_pair"}:
            symbol = {"gt": ">", "lt": "<", "eq_pair": "=="}[self.op]
            return f"x{self.args[0]} {symbol} x{self.args[1]}"
        if self.op == "and":
            return f"({self.args[0]}) AND ({self.args[1]})"
        return f"{self.op}{self.args}"


def evaluate(candidate: Candidate, values: tuple[int, ...],
             atoms: tuple[Candidate, ...] = ()) -> int:
    op, args = candidate.op, candidate.args
    if op == "ge":
        return int(values[args[0]] >= args[1])
    if op == "eq":
        return int(values[args[0]] == args[1])
    if op == "even":
        return int(values[args[0]] % 2 == 0)
    if op == "odd":
        return int(values[args[0]] % 2 == 1)
    if op == "gt":
        return int(values[args[0]] > values[args[1]])
    if op == "lt":
        return int(values[args[0]] < values[args[1]])
    if op == "eq_pair":
        return int(values[args[0]] == values[args[1]])
    if op == "and":
        left, right = atoms[args[0]], atoms[args[1]]
        return evaluate(left, values) & evaluate(right, values)
    raise ValueError(f"unknown candidate operation: {op}")


def propose_candidates(support: Iterable[Example],
                       candidate_budget: int = 512) -> tuple[Candidate, ...]:
    """Propose a bounded DSL from Support values only; labels are not read."""
    rows = tuple(support)
    if not rows:
        raise ValueError("support must not be empty")
    if candidate_budget <= 0:
        raise ValueError("candidate_budget must be positive")
    width = len(rows[0].values)
    if any(len(row.values) != width for row in rows):
        raise ValueError("all observations must have the same feature width")

    atoms: set[Candidate] = set()
    for feature in range(width):
        observed = sorted({row.values[feature] for row in rows})
        for threshold in observed:
            atoms.add(Candidate("ge", (feature, threshold)))
            atoms.add(Candidate("eq", (feature, threshold)))
        atoms.add(Candidate("even", (feature,)))
        atoms.add(Candidate("odd", (feature,)))

    for left in range(width):
        for right in range(left + 1, width):
            atoms.add(Candidate("gt", (left, right)))
            atoms.add(Candidate("lt", (left, right)))
            atoms.add(Candidate("eq_pair", (left, right)))

    ordered_atoms = tuple(sorted(atoms))
    candidates = set(ordered_atoms)
    for left_index, right_index in itertools.combinations(
        range(len(ordered_atoms)), 2
    ):
        candidates.add(Candidate("and", (left_index, right_index)))

    conjunctions = tuple(sorted(
        candidate for candidate in candidates if candidate.op == "and"
    ))
    # Keep the atomic vocabulary first so conjunction indices remain stable
    # even when a strict candidate budget truncates the search.
    ordered = ordered_atoms + conjunctions
    return ordered[:candidate_budget]


def render_expression(candidate: Candidate,
                      atoms: tuple[Candidate, ...]) -> str:
    """Render a candidate with readable nested atom expressions."""
    if candidate.op == "and":
        left, right = (atoms[index] for index in candidate.args)
        return f"({left.expression}) AND ({right.expression})"
    return candidate.expression


def _accuracy(candidate: Candidate, examples: tuple[Example, ...],
              atoms: tuple[Candidate, ...]) -> float:
    if not examples:
        raise ValueError("evaluation split must not be empty")
    correct = sum(
        evaluate(candidate, row.values, atoms) == row.label
        for row in examples
    )
    return correct / len(examples)


def induce(support: Iterable[Example], gate: Iterable[Example],
           candidate_budget: int = 512) -> dict:
    """Return a candidate decision using Support + Gate, never Locked Test."""
    support_rows, gate_rows = tuple(support), tuple(gate)
    candidates = propose_candidates(support_rows, candidate_budget)
    # The atom indices used by AND are based on the full, sorted atomic list.
    all_atoms = tuple(sorted({
        candidate for candidate in candidates if candidate.op != "and"
    }))
    # Collapse candidates with identical predictions on Support + Gate.
    # This prevents syntactic duplicates from being mistaken for distinct
    # explanations (for example, equivalent integer thresholds).
    equivalence_classes = {}
    for candidate in candidates:
        signature = tuple(
            evaluate(candidate, row.values, all_atoms)
            for row in support_rows + gate_rows
        )
        train_score = _accuracy(candidate, support_rows, all_atoms)
        gate_score = _accuracy(candidate, gate_rows, all_atoms)
        complexity = 1 if candidate.op != "and" else 2
        rank = (complexity, candidate.op, candidate.args)
        current = equivalence_classes.get(signature)
        item = (gate_score, train_score, -complexity, candidate, rank)
        if current is None or rank < current[4]:
            equivalence_classes[signature] = item

    scored = tuple(equivalence_classes.values())
    best_key = max(item[:3] for item in scored)
    winners = [item[3] for item in scored if item[:3] == best_key]
    if len(winners) != 1:
        return {
            "status": "AMBIGUOUS",
            "selected": None,
            "equivalent_best": [item.expression for item in winners],
            "candidate_count": len(candidates),
            "behavioral_class_count": len(equivalence_classes),
            "budget": candidate_budget,
        }
    selected = winners[0]
    return {
        "status": "CANDIDATE_SELECTED",
        "selected": render_expression(selected, all_atoms),
        "selected_op": selected.op,
        "support_accuracy": best_key[1],
        "gate_accuracy": best_key[0],
        "candidate_count": len(candidates),
        "behavioral_class_count": len(equivalence_classes),
        "budget": candidate_budget,
    }




def make_benchmark() -> tuple[tuple[Example, ...], tuple[Example, ...],
                              tuple[Example, ...]]:
    """A small conjunction task with a held-out feature-combination split."""
    rows = [
        Example((a, b), int(a >= 2 and b >= 2))
        for a, b in itertools.product(range(4), repeat=2)
    ]
    # Keep corners for Gate; hold out a diagonal slice for Locked Test.
    gate_points = {(0, 0), (3, 3), (1, 3), (3, 1)}
    test_points = {(0, 3), (3, 0), (2, 2)}
    support = tuple(row for row in rows
                    if row.values not in gate_points | test_points)
    gate = tuple(row for row in rows if row.values in gate_points)
    locked_test = tuple(row for row in rows if row.values in test_points)
    return support, gate, locked_test


def run_demo() -> dict:
    support, gate, locked_test = make_benchmark()
    result = induce(support, gate)
    # Test labels are consumed only here, after candidate selection is frozen.
    if result["selected"] is not None:
        candidates = propose_candidates(support, candidate_budget=512)
        atoms = tuple(candidate for candidate in candidates
                      if candidate.op != "and")
        selected = next(
            candidate for candidate in candidates
            if render_expression(candidate, atoms) == result["selected"]
        )
        test_accuracy = _accuracy(selected, locked_test, atoms)
    else:
        test_accuracy = None
    return {
        "experiment": "E12-A1-candidate-predicate-induction-smoke-test",
        "support_count": len(support),
        "gate_count": len(gate),
        "locked_test_count": len(locked_test),
        "learner_result": result,
        "locked_test_accuracy": test_accuracy,
        "scope": (
            "Two integer channels and a finite threshold/parity/relational/"
            "conjunction DSL. Smoke test only; no open-world or natural-language "
            "primitive discovery claim."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_demo()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
