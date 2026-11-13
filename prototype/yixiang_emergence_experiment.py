"""M10 preregistered, evidence-bounded tests for composition-level properties.

This module computes descriptive contrasts across explicit experimental arms.
It does not perform causal identification, significance testing, or certify
ontological emergence. A passing audit only enters HUMAN_REVIEW.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Tuple


class ExperimentDecision(str, Enum):
    BLOCKED = "blocked_incomplete_or_criterion_failed"
    HUMAN_REVIEW = "ready_for_human_review"


@dataclass(frozen=True)
class EmergenceProtocol:
    experiment_id: str
    claim_id: str
    metric_name: str
    expected_direction: str
    minimum_effect: float
    minimum_independent_units: int
    member_ids: Tuple[str, ...]
    necessary_member_ids: Tuple[str, ...]
    control_ids: Tuple[str, ...]
    in_scope_signature: str
    preregistration_ref: str
    registered_before_data: bool


@dataclass(frozen=True)
class ExperimentalMeasurement:
    measurement_id: str
    experiment_id: str
    arm: str
    outcome: float
    independent_unit_id: str
    evidence_ref: str
    scope_signature: str


@dataclass(frozen=True)
class ArmSummary:
    arm: str
    n_measurements: int
    n_independent_units: int
    mean_outcome: float


@dataclass(frozen=True)
class ExperimentContrast:
    name: str
    reference_arm: str
    comparison_arm: str
    oriented_effect: float
    required_minimum: float
    passed: bool


@dataclass(frozen=True)
class EmergenceExperimentAudit:
    experiment_id: str
    claim_id: str
    decision: ExperimentDecision
    reason_codes: Tuple[str, ...]
    arm_summaries: Tuple[ArmSummary, ...]
    contrasts: Tuple[ExperimentContrast, ...]
    scope_shift_mean: float | None
    interpretation_ceiling: str = "descriptive_preregistered_contrast_only"
    non_claims: Tuple[str, ...] = (
        "not_causal_identification",
        "not_statistical_significance",
        "not_proof_of_ontological_emergence",
        "not_universal_generalization",
        "not_independent_source_authentication",
    )


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _unique_strings(values: Tuple[str, ...], field: str, allow_empty: bool = False) -> None:
    if not isinstance(values, tuple) or (not values and not allow_empty):
        raise ValueError(f"{field} must be a non-empty tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field} entries must be non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} entries must be unique")


def validate_protocol(protocol: EmergenceProtocol) -> None:
    if not isinstance(protocol, EmergenceProtocol):
        raise ValueError("protocol must be EmergenceProtocol")
    for field in ("experiment_id", "claim_id", "metric_name", "in_scope_signature",
                  "preregistration_ref"):
        _nonempty(getattr(protocol, field), field)
    if protocol.expected_direction not in ("higher", "lower"):
        raise ValueError("expected_direction must be 'higher' or 'lower'")
    if (isinstance(protocol.minimum_effect, bool)
            or not isinstance(protocol.minimum_effect, (int, float))
            or not isfinite(protocol.minimum_effect)
            or protocol.minimum_effect <= 0):
        raise ValueError("minimum_effect must be finite and greater than zero")
    if (isinstance(protocol.minimum_independent_units, bool)
            or not isinstance(protocol.minimum_independent_units, int)
            or protocol.minimum_independent_units < 2):
        raise ValueError("minimum_independent_units must be an integer >= 2")
    _unique_strings(protocol.member_ids, "member_ids")
    _unique_strings(protocol.necessary_member_ids, "necessary_member_ids")
    _unique_strings(protocol.control_ids, "control_ids", allow_empty=True)
    if set(protocol.necessary_member_ids) - set(protocol.member_ids):
        raise ValueError("necessary_member_ids must be a subset of member_ids")
    if not isinstance(protocol.registered_before_data, bool):
        raise ValueError("registered_before_data must be boolean")


def _oriented_effect(direction: str, reference: float, comparison: float) -> float:
    return reference - comparison if direction == "higher" else comparison - reference


def audit_emergence_experiment(
    protocol: EmergenceProtocol,
    measurements: Tuple[ExperimentalMeasurement, ...],
) -> EmergenceExperimentAudit:
    """Check completeness and preregistered descriptive contrasts.

    Arms: member_only:<member_id>, intact_composite, bridge_removed,
    member_removed:<member_id>, control:<control_id>, and context_shift.
    Independent units may be paired across arms, but measurement/evidence IDs
    must be unique. No p-values or causal claims are computed.
    """
    validate_protocol(protocol)
    if not isinstance(measurements, tuple) or not measurements:
        raise ValueError("measurements must be a non-empty tuple")

    measurement_ids = []
    evidence_refs = []
    grouped: dict[str, list[ExperimentalMeasurement]] = {}
    for item in measurements:
        if not isinstance(item, ExperimentalMeasurement):
            raise ValueError("measurements must contain ExperimentalMeasurement values")
        for field in ("measurement_id", "experiment_id", "arm",
                      "independent_unit_id", "evidence_ref", "scope_signature"):
            _nonempty(getattr(item, field), field)
        if item.experiment_id != protocol.experiment_id:
            raise ValueError("measurement experiment_id does not match protocol")
        if isinstance(item.outcome, bool) or not isinstance(item.outcome, (int, float)) or not isfinite(item.outcome):
            raise ValueError("outcome must be a finite number")
        measurement_ids.append(item.measurement_id)
        evidence_refs.append(item.evidence_ref)
        grouped.setdefault(item.arm, []).append(item)
    if len(measurement_ids) != len(set(measurement_ids)):
        raise ValueError("measurement_id values must be unique")
    if len(evidence_refs) != len(set(evidence_refs)):
        raise ValueError("evidence_ref values must be unique across measurements")

    required_arms = {"intact_composite", "bridge_removed", "context_shift"}
    required_arms.update(f"member_only:{member_id}" for member_id in protocol.member_ids)
    required_arms.update(f"member_removed:{member_id}" for member_id in protocol.necessary_member_ids)
    required_arms.update(f"control:{control_id}" for control_id in protocol.control_ids)
    missing = sorted(required_arms - set(grouped))
    unexpected = sorted(set(grouped) - required_arms)
    reasons = []
    if missing:
        reasons.append("REQUIRED_EXPERIMENT_ARMS_MISSING")
    if unexpected:
        reasons.append("UNDECLARED_EXPERIMENT_ARMS_PRESENT")

    summaries = []
    means = {}
    for arm in sorted(grouped):
        rows = grouped[arm]
        units = {row.independent_unit_id for row in rows}
        mean = sum(float(row.outcome) for row in rows) / len(rows)
        means[arm] = mean
        summaries.append(ArmSummary(arm, len(rows), len(units), mean))
        if len(units) < protocol.minimum_independent_units:
            reasons.append(f"INSUFFICIENT_INDEPENDENT_UNITS:{arm}")
        expected_scope = (
            protocol.in_scope_signature if arm != "context_shift" else None
        )
        if expected_scope is not None and any(row.scope_signature != expected_scope for row in rows):
            reasons.append(f"IN_SCOPE_SIGNATURE_MISMATCH:{arm}")
        if arm == "context_shift" and all(
            row.scope_signature == protocol.in_scope_signature for row in rows
        ):
            reasons.append("CONTEXT_SHIFT_DID_NOT_CHANGE_SCOPE_SIGNATURE")

    contrasts = []
    if not missing:
        comparisons = [("composite_vs_bridge_removed", "bridge_removed")]
        comparisons.extend(
            (f"composite_vs_member_only:{member_id}", f"member_only:{member_id}")
            for member_id in protocol.member_ids
        )
        comparisons.extend(
            (f"composite_vs_member_removed:{member_id}", f"member_removed:{member_id}")
            for member_id in protocol.necessary_member_ids
        )
        comparisons.extend(
            (f"composite_vs_control:{control_id}", f"control:{control_id}")
            for control_id in protocol.control_ids
        )
        for name, comparison_arm in comparisons:
            effect = _oriented_effect(
                protocol.expected_direction,
                means["intact_composite"],
                means[comparison_arm],
            )
            passed = effect >= protocol.minimum_effect
            contrasts.append(ExperimentContrast(
                name, "intact_composite", comparison_arm,
                effect, protocol.minimum_effect, passed,
            ))
            if not passed:
                reasons.append(f"PREREGISTERED_CONTRAST_FAILED:{name}")

    if not protocol.registered_before_data:
        reasons.append("PREREGISTRATION_NOT_CONFIRMED_BEFORE_DATA")
    context_mean = means.get("context_shift")
    decision = ExperimentDecision.BLOCKED if reasons else ExperimentDecision.HUMAN_REVIEW
    return EmergenceExperimentAudit(
        protocol.experiment_id,
        protocol.claim_id,
        decision,
        tuple(sorted(set(reasons))),
        tuple(summaries),
        tuple(contrasts),
        context_mean,
    )
