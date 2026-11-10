"""E12-A3: budgeted multi-proposer primitive discovery.

The module deliberately separates proposal generation from Gate evaluation.
It is a transparent research baseline, not an open-ended concept learner.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import random
from typing import Any, Iterable, Mapping, Sequence


Scalar = int | float | str


@dataclass(frozen=True)
class Observation:
    observation_id: str
    values: tuple[tuple[str, Scalar], ...]
    label: int

    def as_dict(self) -> dict[str, Scalar]:
        return dict(self.values)


@dataclass(frozen=True, order=True)
class PredicateExpr:
    feature: str
    operator: str
    value: Scalar | None = None
    other_feature: str | None = None

    def canonical(self) -> str:
        return json.dumps(
            {"feature": self.feature, "operator": self.operator,
             "value": self.value, "other_feature": self.other_feature},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )

    def evaluate(self, values: Mapping[str, Scalar]) -> int:
        if self.feature not in values:
            raise KeyError(self.feature)
        left = values[self.feature]
        op = self.operator
        if op == "EQ":
            return int(left == self.value)
        if op == "GE":
            if isinstance(left, bool) or not isinstance(left, (int, float)):
                raise TypeError("GE requires a numeric feature")
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise TypeError("GE requires a numeric threshold")
            return int(left >= self.value)
        if op == "PARITY":
            if isinstance(left, bool) or not isinstance(left, int):
                raise TypeError("PARITY requires an integer feature")
            if isinstance(self.value, bool) or self.value not in (0, 1):
                raise TypeError("PARITY threshold must be 0 or 1")
            return int(left % 2 == self.value)
        if op == "SAME":
            if self.other_feature is None or self.other_feature not in values:
                raise KeyError(self.other_feature)
            return int(left == values[self.other_feature])
        if op == "DIFF_GE":
            if self.other_feature is None or self.other_feature not in values:
                raise KeyError(self.other_feature)
            right = values[self.other_feature]
            if (isinstance(left, bool) or isinstance(right, bool)
                    or not isinstance(left, (int, float))
                    or not isinstance(right, (int, float))):
                raise TypeError("DIFF_GE requires numeric features")
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise TypeError("DIFF_GE requires a numeric threshold")
            return int(left - right >= self.value)
        raise ValueError(f"unsupported operator: {op}")


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    family: str
    family_version: str
    expression: PredicateExpr
    source_observation_ids: tuple[str, ...]
    proposal_cost: int = 1
    parent_ids: tuple[str, ...] = ()

    @property
    def canonical_expression(self) -> str:
        return self.expression.canonical()


@dataclass(frozen=True)
class CandidateSignature:
    dataset_id: str
    outputs: tuple[int, ...]


@dataclass(frozen=True)
class BudgetAllocation:
    total_budget: int
    allocations: tuple[tuple[str, int], ...]

    def as_dict(self) -> dict[str, int]:
        return dict(self.allocations)


class LifecycleState(str, Enum):
    PROPOSED = "PROPOSED"
    TYPE_CHECKED = "TYPE_CHECKED"
    SUPPORT_SCREENED = "SUPPORT_SCREENED"
    GATE_VALIDATED = "GATE_VALIDATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class LifecycleEvent:
    candidate_id: str
    from_state: str | None
    to_state: str
    evidence_ids: tuple[str, ...]
    reason: str


def _proposal(family: str, expr: PredicateExpr, source_ids: Iterable[str],
              version: str = "1", parents: tuple[str, ...] = ()) -> Proposal:
    raw = f"{family}|{version}|{expr.canonical()}"
    pid = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return Proposal(pid, family, version, expr, tuple(sorted(set(source_ids))),
                    1, parents)


def validate_observations(rows: Sequence[Observation]) -> None:
    if not rows:
        raise ValueError("observation set must not be empty")
    ids = [row.observation_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("observation IDs must be unique")
    schema = set(dict(rows[0].values))
    if not schema or len(rows[0].values) != len(schema):
        raise ValueError("feature names must be non-empty and unique")
    feature_kinds: dict[str, type] = {}
    for row in rows:
        if isinstance(row.label, bool) or row.label not in (0, 1):
            raise ValueError("labels must be integer 0 or 1")
        row_values = dict(row.values)
        if len(row.values) != len(row_values) or set(row_values) != schema:
            raise ValueError("all observations must share one exact schema")
        for name, value in row_values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                raise TypeError(f"unsupported scalar for feature {name}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"feature {name} must be finite")
            kind = str if isinstance(value, str) else float
            previous = feature_kinds.setdefault(name, kind)
            if previous is not kind:
                raise TypeError(f"feature {name} mixes numeric and categorical values")


def propose_statistical(rows: Sequence[Observation]) -> tuple[Proposal, ...]:
    validate_observations(rows)
    out: dict[str, Proposal] = {}
    source_ids = [r.observation_id for r in rows]
    for feature in sorted(dict(rows[0].values)):
        vals = [r.as_dict()[feature] for r in rows]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            nums = sorted(set(vals))
            for value in nums:
                expressions = [PredicateExpr(feature, "GE", value),
                               PredicateExpr(feature, "EQ", value)]
                for expr in expressions:
                    p = _proposal("STAT", expr, source_ids)
                    out[p.canonical_expression] = p
            if all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
                for parity in (0, 1):
                    p = _proposal("STAT", PredicateExpr(feature, "PARITY", parity), source_ids)
                    out[p.canonical_expression] = p
        else:
            for value in sorted(set(vals), key=lambda x: (type(x).__name__, str(x))):
                p = _proposal("STAT", PredicateExpr(feature, "EQ", value), source_ids)
                out[p.canonical_expression] = p
    return tuple(sorted(out.values(), key=lambda p: (p.family, p.canonical_expression)))


def propose_relational(rows: Sequence[Observation]) -> tuple[Proposal, ...]:
    validate_observations(rows)
    names = sorted(dict(rows[0].values))
    out: dict[str, Proposal] = {}
    source_ids = [r.observation_id for r in rows]
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            lv = [r.as_dict()[left] for r in rows]
            rv = [r.as_dict()[right] for r in rows]
            if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (*lv, *rv)):
                deltas = sorted(set(x - y for x, y in zip(lv, rv)))  # type: ignore[operator]
                for delta in deltas:
                    p = _proposal("RELATIONAL",
                                  PredicateExpr(left, "DIFF_GE", delta, right), source_ids)
                    out[p.canonical_expression] = p
            elif all(isinstance(x, str) for x in (*lv, *rv)):
                p = _proposal("RELATIONAL", PredicateExpr(left, "SAME", None, right), source_ids)
                out[p.canonical_expression] = p
    return tuple(sorted(out.values(), key=lambda p: p.canonical_expression))


def propose_random(rows: Sequence[Observation], seed: int,
                   count: int = 16) -> tuple[Proposal, ...]:
    validate_observations(rows)
    if count < 0:
        raise ValueError("count must be non-negative")
    rng = random.Random(seed)
    names = sorted(dict(rows[0].values))
    out: dict[str, Proposal] = {}
    source_ids = [r.observation_id for r in rows]
    for _ in range(count):
        feature = rng.choice(names)
        vals = [r.as_dict()[feature] for r in rows]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            value = rng.choice(vals)
            op = rng.choice(("GE", "EQ"))
        else:
            value, op = rng.choice(vals), "EQ"
        p = _proposal("RANDOM", PredicateExpr(feature, op, value), source_ids)
        out[p.canonical_expression] = p
    return tuple(sorted(out.values(), key=lambda p: p.canonical_expression))


def propose_exhaustive(rows: Sequence[Observation], limit: int = 128) -> tuple[Proposal, ...]:
    """Bounded enumeration of the same simple grammar; not open-world search."""
    validate_observations(rows)
    if limit < 0:
        raise ValueError("limit must be non-negative")
    candidates = list(propose_statistical(rows)) + list(propose_relational(rows))
    unique = {p.canonical_expression: p for p in candidates}
    ordered = sorted(unique.values(), key=lambda p: (p.family, p.canonical_expression))
    return tuple(_proposal("EXHAUSTIVE", p.expression, p.source_observation_ids)
                 for p in ordered[:limit])


def observed_signature(proposal: Proposal, rows: Sequence[Observation],
                       dataset_id: str) -> CandidateSignature:
    return CandidateSignature(dataset_id, tuple(
        proposal.expression.evaluate(row.as_dict()) for row in rows
    ))


def group_empirical_equivalence(proposals: Sequence[Proposal],
                                rows: Sequence[Observation],
                                dataset_id: str) -> dict[CandidateSignature, tuple[str, ...]]:
    """Group equal behavior on this named dataset only; not global equivalence."""
    groups: dict[CandidateSignature, list[str]] = {}
    for proposal in proposals:
        sig = observed_signature(proposal, rows, dataset_id)
        groups.setdefault(sig, []).append(proposal.proposal_id)
    return {sig: tuple(sorted(ids)) for sig, ids in groups.items()}


def allocate_equal_budget(families: Sequence[str], total_budget: int) -> BudgetAllocation:
    names = tuple(sorted(set(families)))
    if total_budget < 0:
        raise ValueError("total_budget must be non-negative")
    if not names:
        if total_budget:
            raise ValueError("cannot allocate positive budget to no families")
        return BudgetAllocation(0, ())
    base, remainder = divmod(total_budget, len(names))
    allocations = tuple((name, base + int(i < remainder)) for i, name in enumerate(names))
    return BudgetAllocation(total_budget, allocations)


def allocate_round_robin(proposals: Mapping[str, Sequence[Proposal]],
                         total_budget: int) -> tuple[Proposal, ...]:
    if total_budget < 0:
        raise ValueError("total_budget must be non-negative")
    families = sorted(proposals)
    # Preserve caller-supplied deterministic order. Benchmark callers may
    # provide a seeded shuffle to avoid lexical-prefix selection bias.
    queues = {name: list(proposals[name]) for name in families}
    selected: list[Proposal] = []
    while len(selected) < total_budget:
        progressed = False
        for name in families:
            if queues[name] and len(selected) < total_budget:
                selected.append(queues[name].pop(0))
                progressed = True
        if not progressed:
            break
    return tuple(selected)


def evaluate_gate(proposals: Sequence[Proposal], gate: Sequence[Observation]) -> dict[str, Any]:
    validate_observations(gate)
    results = {}
    for p in proposals:
        correct = sum(p.expression.evaluate(row.as_dict()) == row.label for row in gate)
        results[p.proposal_id] = {
            "correct": correct, "total": len(gate),
            "accuracy": correct / len(gate),
            "gate_observation_ids": [row.observation_id for row in gate],
        }
    return results


def lifecycle_transition(candidate_id: str, current: LifecycleState | None,
                         target: LifecycleState, evidence_ids: Iterable[str],
                         reason: str) -> LifecycleEvent:
    allowed = {
        None: {LifecycleState.PROPOSED},
        LifecycleState.PROPOSED: {LifecycleState.TYPE_CHECKED, LifecycleState.REJECTED},
        LifecycleState.TYPE_CHECKED: {LifecycleState.SUPPORT_SCREENED, LifecycleState.REJECTED},
        LifecycleState.SUPPORT_SCREENED: {LifecycleState.GATE_VALIDATED, LifecycleState.AMBIGUOUS,
                                           LifecycleState.REJECTED, LifecycleState.SUSPENDED},
        LifecycleState.GATE_VALIDATED: {LifecycleState.ACCEPTED, LifecycleState.AMBIGUOUS,
                                         LifecycleState.REJECTED, LifecycleState.SUSPENDED},
        LifecycleState.ACCEPTED: {LifecycleState.SUSPENDED, LifecycleState.RETIRED},
        LifecycleState.AMBIGUOUS: {LifecycleState.SUPPORT_SCREENED, LifecycleState.SUSPENDED,
                                   LifecycleState.RETIRED},
        LifecycleState.SUSPENDED: {LifecycleState.SUPPORT_SCREENED, LifecycleState.RETIRED},
        LifecycleState.REJECTED: {LifecycleState.RETIRED},
        LifecycleState.RETIRED: set(),
    }
    if target not in allowed[current]:
        raise ValueError(f"invalid lifecycle transition: {current} -> {target}")
    if not reason.strip():
        raise ValueError("transition reason must be non-empty")
    return LifecycleEvent(candidate_id, current.value if current else None,
                          target.value, tuple(sorted(set(evidence_ids))), reason)


def demo_rows() -> tuple[Observation, ...]:
    return (
        Observation("o1", (("temperature", 10), ("speed", 1), ("weather", "dry")), 0),
        Observation("o2", (("temperature", 15), ("speed", 2), ("weather", "dry")), 0),
        Observation("o3", (("temperature", 20), ("speed", 3), ("weather", "wet")), 1),
        Observation("o4", (("temperature", 25), ("speed", 4), ("weather", "wet")), 1),
    )


def run_demo(seed: int = 7, budget: int = 24) -> dict[str, Any]:
    rows = demo_rows()
    proposals = {
        "STAT": propose_statistical(rows),
        "RELATIONAL": propose_relational(rows),
        "RANDOM": propose_random(rows, seed=seed, count=32),
        "EXHAUSTIVE": propose_exhaustive(rows, limit=64),
    }
    allocation = allocate_equal_budget(tuple(proposals), budget)
    selected = allocate_round_robin(proposals, budget)
    return {
        "seed": seed,
        "budget": budget,
        "allocation": allocation.as_dict(),
        "proposed_counts": {k: len(v) for k, v in proposals.items()},
        "selected_count": len(selected),
        "selected_by_family": {
            family: sum(p.family == family for p in selected) for family in proposals
        },
        "support_equivalence_groups": len(group_empirical_equivalence(
            selected, rows, "demo-support-v1"
        )),
        "note": "Synthetic protocol smoke test only; not a benchmark result.",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
