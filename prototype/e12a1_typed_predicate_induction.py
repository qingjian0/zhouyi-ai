"""E12-A1: typed, observation-grounded predicate proposal baseline."""
from __future__ import annotations
import argparse, json
from dataclasses import asdict, dataclass
from typing import Literal

FeatureKind = Literal["numeric", "categorical"]
Operator = Literal["GE", "GT", "LE", "LT", "EQ", "PARITY"]
Scalar = int | float | str

@dataclass(frozen=True, order=True)
class FeatureSpec:
    name: str
    kind: FeatureKind

@dataclass(frozen=True)
class Example:
    values: tuple[tuple[str, Scalar], ...]
    label: int
    def value(self, name: str) -> Scalar:
        for key, value in self.values:
            if key == name: return value
        raise KeyError(name)

@dataclass(frozen=True)
class LearnerView:
    schema: tuple[FeatureSpec, ...]
    train: tuple[Example, ...]
    gate: tuple[Example, ...]

@dataclass(frozen=True, order=True)
class Predicate:
    feature: str
    input_kind: FeatureKind
    operator: Operator
    threshold: Scalar | None = None
    @property
    def complexity(self) -> int:
        return 1 if self.operator in ("EQ", "PARITY") else 2
    def _numeric_threshold(self) -> int | float:
        if isinstance(self.threshold, bool) or not isinstance(self.threshold, (int, float)):
            raise TypeError("numeric predicate requires numeric threshold")
        return self.threshold
    def evaluate(self, value: Scalar) -> int:
        if self.input_kind == "numeric":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{self.feature} requires numeric input")
            if self.operator == "GE": return int(value >= self._numeric_threshold())
            if self.operator == "GT": return int(value > self._numeric_threshold())
            if self.operator == "LE": return int(value <= self._numeric_threshold())
            if self.operator == "LT": return int(value < self._numeric_threshold())
            if self.operator == "EQ": return int(value == self._numeric_threshold())
            if self.operator == "PARITY":
                if not isinstance(value, int): raise TypeError("PARITY requires integers")
                if self.threshold not in (0, 1): raise TypeError("PARITY threshold must be 0 or 1")
                return int(value % 2 == self.threshold)
        elif self.input_kind == "categorical":
            if self.operator != "EQ": raise TypeError("categorical predicates support EQ only")
            if not isinstance(value, str): raise TypeError(f"{self.feature} requires categorical string")
            if not isinstance(self.threshold, str): raise TypeError("categorical EQ requires string threshold")
            return int(value == self.threshold)
        raise ValueError(f"unsupported predicate: {self}")

def validate_view(view: LearnerView) -> None:
    names = [spec.name for spec in view.schema]
    if any(not name for name in names): raise ValueError("feature names must be non-empty")
    if len(names) != len(set(names)): raise ValueError("feature names must be unique")
    for spec in view.schema:
        if spec.kind not in ("numeric", "categorical"):
            raise ValueError(f"unsupported feature kind: {spec.kind}")
    if not view.train or not view.gate: raise ValueError("Train and Gate must be non-empty")
    for example in (*view.train, *view.gate):
        if example.label not in (0, 1): raise ValueError("labels must be binary")
        if set(key for key, _ in example.values) != set(names) or len(example.values) != len(names):
            raise ValueError("each example must contain exactly the declared features")
        for spec in view.schema:
            value = example.value(spec.name)
            if spec.kind == "numeric" and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise TypeError(f"{spec.name} must be numeric")
            if spec.kind == "categorical" and not isinstance(value, str):
                raise TypeError(f"{spec.name} must be categorical string")

def propose_predicates(view: LearnerView) -> tuple[Predicate, ...]:
    """Generate typed candidates from Train values only; Gate is not inspected."""
    validate_view(view)
    candidates: set[Predicate] = set()
    for spec in view.schema:
        values = sorted({example.value(spec.name) for example in view.train})
        if spec.kind == "numeric":
            nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
            for left, right in zip(nums, nums[1:]):
                mid = (left + right) / 2
                for op in ("GE", "GT", "LE", "LT"):
                    candidates.add(Predicate(spec.name, "numeric", op, mid))
            for value in nums:
                candidates.add(Predicate(spec.name, "numeric", "EQ", value))
            if nums and all(isinstance(v, int) for v in nums):
                candidates.add(Predicate(spec.name, "numeric", "PARITY", 0))
                candidates.add(Predicate(spec.name, "numeric", "PARITY", 1))
        else:
            for value in values:
                candidates.add(Predicate(spec.name, "categorical", "EQ", value))
    return tuple(sorted(candidates))

def _matches(predicate: Predicate, examples: tuple[Example, ...]) -> bool:
    return all(predicate.evaluate(ex.value(predicate.feature)) == ex.label for ex in examples)

def infer(view: LearnerView, candidate_budget: int | None = None) -> dict:
    """Propose on Train and select on Gate; never receives evaluator truth."""
    candidates = propose_predicates(view)
    if candidate_budget is not None and candidate_budget < 0:
        raise ValueError("candidate_budget must be non-negative")
    evaluated = candidates if candidate_budget is None else candidates[:candidate_budget]
    train_ok = tuple(p for p in evaluated if _matches(p, view.train))
    gate_ok = tuple(p for p in train_ok if _matches(p, view.gate))
    if len(evaluated) < len(candidates):
        return {"status":"BUDGET_EXHAUSTED", "candidate_count":len(candidates),
                "evaluated_count":len(evaluated), "train_consistent_count":len(train_ok),
                "gate_consistent_count":len(gate_ok), "candidates":gate_ok, "selected":None}
    if len(gate_ok) == 1: status, selected = "IDENTIFIABLE", gate_ok[0]
    elif len(gate_ok) > 1: status, selected = "AMBIGUOUS", None
    else: status, selected = "INCONSISTENT", None
    return {"status":status, "candidate_count":len(candidates),
            "evaluated_count":len(evaluated), "train_consistent_count":len(train_ok),
            "gate_consistent_count":len(gate_ok), "candidates":gate_ok, "selected":selected}

def demo_view() -> LearnerView:
    schema = (FeatureSpec("temperature","numeric"), FeatureSpec("speed","numeric"),
              FeatureSpec("weather","categorical"))
    train = (
      Example((("speed",2),("temperature",12),("weather","dry")),0),
      Example((("speed",3),("temperature",15),("weather","dry")),0),
      Example((("speed",4),("temperature",22),("weather","wet")),1),
      Example((("speed",5),("temperature",27),("weather","wet")),1))
    gate = (
      Example((("speed",6),("temperature",24),("weather","wet")),1),
      Example((("speed",1),("temperature",10),("weather","dry")),0))
    return LearnerView(schema, train, gate)

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--budget",type=int,default=None)
    args=parser.parse_args()
    result=infer(demo_view(),args.budget)
    if result["selected"] is not None: result["selected"]=asdict(result["selected"])
    result["candidates"]=[asdict(x) for x in result["candidates"]]
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__ == "__main__": main()
