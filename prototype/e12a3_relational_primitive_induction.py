"""E12-A3: discover typed relations between observed feature pairs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Kind = Literal["numeric", "categorical"]
Relation = Literal["LT", "GT", "EQ", "SAME", "DIFFERENT", "SAME_PARITY"]
Scalar = int | float | str

@dataclass(frozen=True, order=True)
class FeatureSpec:
    name: str
    kind: Kind

@dataclass(frozen=True)
class Example:
    values: tuple[tuple[str, Scalar], ...]
    label: int
    def value(self, name: str) -> Scalar:
        for key, value in self.values:
            if key == name:
                return value
        raise KeyError(name)

@dataclass(frozen=True, order=True)
class RelationalPredicate:
    left: str
    right: str
    kind: Kind
    relation: Relation

    def evaluate(self, left_value: Scalar, right_value: Scalar) -> int:
        if self.kind == "numeric":
            if (isinstance(left_value, bool) or isinstance(right_value, bool)
                or not isinstance(left_value, (int, float))
                or not isinstance(right_value, (int, float))):
                raise TypeError("numeric relation requires numeric inputs")
            if self.relation == "LT": return int(left_value < right_value)
            if self.relation == "GT": return int(left_value > right_value)
            if self.relation == "EQ": return int(left_value == right_value)
            if self.relation == "SAME_PARITY":
                if not isinstance(left_value, int) or not isinstance(right_value, int):
                    raise TypeError("SAME_PARITY requires integer inputs")
                return int(left_value % 2 == right_value % 2)
        if self.kind == "categorical":
            if not isinstance(left_value, str) or not isinstance(right_value, str):
                raise TypeError("categorical relation requires string inputs")
            if self.relation == "SAME": return int(left_value == right_value)
            if self.relation == "DIFFERENT": return int(left_value != right_value)
        raise ValueError(f"unsupported relation: {self}")

@dataclass(frozen=True)
class LearnerView:
    schema: tuple[FeatureSpec, ...]
    train: tuple[Example, ...]
    gate: tuple[Example, ...]

def validate_view(view: LearnerView) -> None:
    names = [s.name for s in view.schema]
    if not names or any(not n for n in names) or len(names) != len(set(names)):
        raise ValueError("schema needs unique, non-empty feature names")
    if not view.train or not view.gate:
        raise ValueError("Train and Gate must be non-empty")
    for spec in view.schema:
        if spec.kind not in ("numeric", "categorical"):
            raise ValueError(f"unsupported feature kind: {spec.kind}")
    for ex in (*view.train, *view.gate):
        if ex.label not in (0, 1):
            raise ValueError("labels must be binary")
        if len(ex.values) != len(names) or {k for k, _ in ex.values} != set(names):
            raise ValueError("each example must contain exactly the declared features")
        for spec in view.schema:
            value = ex.value(spec.name)
            if spec.kind == "numeric":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{spec.name} must be numeric")
            elif not isinstance(value, str):
                raise TypeError(f"{spec.name} must be categorical string")

def propose_relations(view: LearnerView) -> tuple[RelationalPredicate, ...]:
    """Generate relation candidates from Train schema/types only."""
    validate_view(view)
    result: set[RelationalPredicate] = set()
    for i, left in enumerate(view.schema):
        for right in view.schema[i + 1:]:
            if left.kind != right.kind:
                continue
            if left.kind == "numeric":
                result.update(RelationalPredicate(left.name, right.name, "numeric", op)
                              for op in ("LT", "GT", "EQ"))
                lv = [ex.value(left.name) for ex in view.train]
                rv = [ex.value(right.name) for ex in view.train]
                if all(isinstance(v, int) and not isinstance(v, bool) for v in (*lv, *rv)):
                    result.add(RelationalPredicate(left.name, right.name, "numeric", "SAME_PARITY"))
            else:
                result.add(RelationalPredicate(left.name, right.name, "categorical", "SAME"))
                result.add(RelationalPredicate(left.name, right.name, "categorical", "DIFFERENT"))
    return tuple(sorted(result))

def _matches(predicate: RelationalPredicate, examples: tuple[Example, ...]) -> bool:
    return all(predicate.evaluate(ex.value(predicate.left), ex.value(predicate.right)) == ex.label
               for ex in examples)

def infer(view: LearnerView, candidate_budget: int | None = None) -> dict:
    """Propose from Train, validate on Gate, and preserve ambiguity/abstention."""
    candidates = propose_relations(view)
    if candidate_budget is not None and candidate_budget < 0:
        raise ValueError("candidate_budget must be non-negative")
    evaluated = candidates if candidate_budget is None else candidates[:candidate_budget]
    train_ok = tuple(p for p in evaluated if _matches(p, view.train))
    gate_ok = tuple(p for p in train_ok if _matches(p, view.gate))
    if len(evaluated) < len(candidates):
        status, selected = "BUDGET_EXHAUSTED", None
    elif len(gate_ok) == 1:
        status, selected = "IDENTIFIABLE_WITHIN_RELATIONAL_GRAMMAR", gate_ok[0]
    elif len(gate_ok) > 1:
        status, selected = "AMBIGUOUS", None
    else:
        status, selected = "INCONSISTENT", None
    return {"status": status, "candidate_count": len(candidates),
            "evaluated_count": len(evaluated), "train_consistent_count": len(train_ok),
            "gate_consistent_count": len(gate_ok), "candidates": gate_ok,
            "selected": selected}

def demo_view() -> LearnerView:
    schema = (FeatureSpec("a", "numeric"), FeatureSpec("b", "numeric"),
              FeatureSpec("c", "categorical"), FeatureSpec("d", "categorical"))
    train = (
        Example((("a",1),("b",3),("c","red"),("d","red")),1),
        Example((("a",4),("b",2),("c","red"),("d","blue")),0),
        Example((("a",2),("b",5),("c","blue"),("d","blue")),1),
        Example((("a",7),("b",6),("c","blue"),("d","red")),0))
    gate = (Example((("a",0),("b",2),("c","green"),("d","green")),1),
            Example((("a",5),("b",1),("c","green"),("d","yellow")),0))
    return LearnerView(schema, train, gate)
