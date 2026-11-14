"""M4 transparent counterfactual condition-intervention baseline.

This module evaluates declared conditional rules under hypothetical changes.
It is not a causal discovery engine and does not turn interventions into
observational evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TruthValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class ConditionOrigin(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    ASSUMED = "assumed"
    INTERVENTION = "intervention"


class RelationState(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class ComparisonKind(str, Enum):
    INVARIANT = "invariant"
    CHANGED = "changed"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class ConditionValue:
    name: str
    value: TruthValue
    origin: ConditionOrigin
    source_ref: str = ""

    def validate(self) -> None:
        if not isinstance(self.value, TruthValue):
            raise ValueError("condition value must be a TruthValue")
        if not isinstance(self.origin, ConditionOrigin):
            raise ValueError("condition origin must be a ConditionOrigin")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("condition name is required")
        if self.origin == ConditionOrigin.OBSERVED and not self.source_ref.strip():
            raise ValueError("observed conditions require a source_ref")


@dataclass(frozen=True)
class ConditionIntervention:
    name: str
    value: TruthValue

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("intervention name is required")
        if not isinstance(self.value, TruthValue) or self.value == TruthValue.UNKNOWN:
            raise ValueError("an intervention must set a known true/false value")


@dataclass(frozen=True)
class ConditionalMapping:
    mapping_id: str
    relation_name: str
    requires_true: tuple[str, ...]
    requires_false: tuple[str, ...] = ()

    def validate(self) -> None:
        if not isinstance(self.mapping_id, str) or not self.mapping_id.strip() or not isinstance(self.relation_name, str) or not self.relation_name.strip():
            raise ValueError("mapping id and relation name are required")
        if not isinstance(self.requires_true, tuple) or not isinstance(self.requires_false, tuple):
            raise ValueError("required condition collections must be tuples")
        names = self.requires_true + self.requires_false
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("required condition names must be non-empty strings")
        if len(names) != len(set(names)):
            raise ValueError("required conditions must be unique and non-overlapping")


@dataclass(frozen=True)
class CounterfactualAssessment:
    mapping_id: str
    baseline_state: RelationState
    counterfactual_state: RelationState
    comparison: ComparisonKind
    changed_conditions: tuple[str, ...]
    unknown_conditions: tuple[str, ...]
    intervention_only: bool


def _evaluate(mapping: ConditionalMapping, values: dict[str, ConditionValue]):
    unknown = []
    violated = []
    for name in mapping.requires_true:
        item = values.get(name)
        if item is None or item.value == TruthValue.UNKNOWN:
            unknown.append(name)
        elif item.value == TruthValue.FALSE:
            violated.append(name)
    for name in mapping.requires_false:
        item = values.get(name)
        if item is None or item.value == TruthValue.UNKNOWN:
            unknown.append(name)
        elif item.value == TruthValue.TRUE:
            violated.append(name)
    if violated:
        return RelationState.INACTIVE, tuple(sorted(set(unknown))), tuple(sorted(violated))
    if unknown:
        return RelationState.UNKNOWN, tuple(sorted(set(unknown))), ()
    return RelationState.ACTIVE, (), ()


def assess_counterfactual(
    mapping: ConditionalMapping,
    baseline: tuple[ConditionValue, ...],
    interventions: tuple[ConditionIntervention, ...],
) -> CounterfactualAssessment:
    mapping.validate()
    baseline_map = {}
    for item in baseline:
        item.validate()
        if item.name in baseline_map:
            raise ValueError("baseline condition names must be unique")
        baseline_map[item.name] = item

    intervention_map = {}
    for item in interventions:
        item.validate()
        if item.name in intervention_map:
            raise ValueError("intervention names must be unique")
        intervention_map[item.name] = item

    before, before_unknown, _ = _evaluate(mapping, baseline_map)
    changed = tuple(sorted(
        name for name, intervention in intervention_map.items()
        if name not in baseline_map or baseline_map[name].value != intervention.value
    ))
    after_map = dict(baseline_map)
    for name, intervention in intervention_map.items():
        after_map[name] = ConditionValue(
            name, intervention.value, ConditionOrigin.INTERVENTION,
            "hypothetical:do",
        )
    after, after_unknown, _ = _evaluate(mapping, after_map)

    if before == RelationState.UNKNOWN or after == RelationState.UNKNOWN:
        comparison = ComparisonKind.UNDETERMINED
    elif before == after:
        comparison = ComparisonKind.INVARIANT
    else:
        comparison = ComparisonKind.CHANGED

    return CounterfactualAssessment(
        mapping.mapping_id, before, after, comparison, changed,
        tuple(sorted(set(before_unknown) | set(after_unknown))),
        bool(interventions),
    )
