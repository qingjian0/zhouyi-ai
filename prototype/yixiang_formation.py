"""Audit the provenance chain from observation to xiang and category.

This is a bookkeeping and evidence-provenance prototype. It does not infer
features from raw perception or decide whether a category is philosophically
or empirically correct.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class FormationStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    MISSING_OBSERVATION = "missing_observation"
    MISSING_FEATURE_PROVENANCE = "missing_feature_provenance"
    FEATURE_NOT_GROUNDED = "feature_not_grounded"
    MISSING_SELECTION_RATIONALE = "missing_selection_rationale"
    MISSING_CATEGORY_CRITERION = "missing_category_criterion"
    MISSING_MEMBERSHIP_EVIDENCE = "missing_membership_evidence"
    COUNTEREXAMPLE_UNRESOLVED = "counterexample_unresolved"
    DECLARATION_MISMATCH = "declaration_mismatch"
    PROVISIONAL_FORMATION = "provisional_formation"


@dataclass(frozen=True)
class Observation:
    observation_id: str
    subject_id: str
    context_id: str
    context_version: int
    description: str
    evidence_refs: Tuple[str, ...]
    observer_id: str


@dataclass(frozen=True)
class FeatureSelection:
    feature_id: str
    subject_id: str
    label: str
    operational_description: str
    observation_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    selection_rationale: str
    purpose: str
    excluded_alternatives: Tuple[str, ...]
    reviewed: bool


@dataclass(frozen=True)
class CategoryAssignment:
    assignment_id: str
    subject_id: str
    category_id: str
    criterion: str
    feature_refs: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    counterexample_refs: Tuple[str, ...]
    counterexamples_resolved: bool | None
    reviewed: bool


@dataclass(frozen=True)
class FormationTrace:
    trace_id: str
    observations: Tuple[Observation, ...]
    selected_features: Tuple[FeatureSelection, ...]
    category_assignments: Tuple[CategoryAssignment, ...]


@dataclass(frozen=True)
class FormationAssessment:
    trace_id: str
    status: FormationStatus
    missing_observation_ids: Tuple[str, ...]
    ungrounded_feature_ids: Tuple[str, ...]
    missing_rationale_feature_ids: Tuple[str, ...]
    missing_criterion_assignment_ids: Tuple[str, ...]
    missing_membership_evidence_ids: Tuple[str, ...]
    unresolved_counterexample_assignment_ids: Tuple[str, ...]
    declaration_mismatches: Tuple[str, ...]
    semantic_validity_established: bool = False
    category_truth_established: bool = False
    adjudication: str = "human_review_required"


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")


def _items(values: Tuple[str, ...], field: str, allow_empty: bool = True) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be tuple")
    for value in values:
        _text(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")
    if not allow_empty and not values:
        raise ValueError(f"{field} must not be empty")


def _version(value: int, field: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")


def assess_formation(trace: FormationTrace) -> FormationAssessment:
    """Audit trace completeness without certifying its interpretation."""
    if not isinstance(trace, FormationTrace):
        raise ValueError("trace must be FormationTrace")
    _text(trace.trace_id, "trace_id")
    for name in ("observations", "selected_features", "category_assignments"):
        if not isinstance(getattr(trace, name), tuple):
            raise ValueError(f"{name} must be tuple")

    observation_ids = set()
    observation_evidence = set()
    observations_by_id = {}
    for obs in trace.observations:
        if not isinstance(obs, Observation):
            raise ValueError("observations must contain Observation")
        for name in ("observation_id", "subject_id", "context_id", "description", "observer_id"):
            _text(getattr(obs, name), f"observation.{name}")
        _version(obs.context_version, "observation.context_version")
        _items(obs.evidence_refs, "observation.evidence_refs", allow_empty=False)
        if obs.observation_id in observation_ids:
            raise ValueError("observation_id values must be unique")
        observation_ids.add(obs.observation_id)
        observations_by_id[obs.observation_id] = obs
        observation_evidence.update(obs.evidence_refs)

    feature_ids = set()
    ungrounded, missing_rationale, missing_obs = [], [], []
    declaration_mismatches = []
    for feature in trace.selected_features:
        if not isinstance(feature, FeatureSelection):
            raise ValueError("selected_features must contain FeatureSelection")
        for name in ("feature_id", "subject_id", "label", "operational_description", "selection_rationale", "purpose"):
            if name == "selection_rationale" and isinstance(getattr(feature, name), str) and not getattr(feature, name).strip():
                continue
            _text(getattr(feature, name), f"feature.{name}")
        for name in ("observation_refs", "evidence_refs", "excluded_alternatives"):
            _items(getattr(feature, name), f"feature.{name}", allow_empty=name == "excluded_alternatives")
        if not isinstance(feature.reviewed, bool):
            raise ValueError("feature.reviewed must be bool")
        if feature.feature_id in feature_ids:
            raise ValueError("feature_id values must be unique")
        feature_ids.add(feature.feature_id)
        if not feature.observation_refs or not set(feature.observation_refs) <= observation_ids:
            missing_obs.append(feature.feature_id)
        else:
            linked_observations = [observations_by_id[ref] for ref in feature.observation_refs]
            linked_evidence = {ref for obs in linked_observations for ref in obs.evidence_refs}
            if not feature.evidence_refs or not set(feature.evidence_refs) <= linked_evidence:
                ungrounded.append(feature.feature_id)
            if any(obs.subject_id != feature.subject_id for obs in linked_observations):
                declaration_mismatches.append(f"{feature.feature_id}:subject_mismatch")
        if not isinstance(feature.selection_rationale, str) or not feature.selection_rationale.strip():
            missing_rationale.append(feature.feature_id)

    assignment_ids = set()
    missing_criterion, missing_membership, unresolved = [], [], []
    for assignment in trace.category_assignments:
        if not isinstance(assignment, CategoryAssignment):
            raise ValueError("category_assignments must contain CategoryAssignment")
        for name in ("assignment_id", "subject_id", "category_id", "criterion"):
            if name == "criterion" and isinstance(getattr(assignment, name), str) and not getattr(assignment, name).strip():
                continue
            _text(getattr(assignment, name), f"assignment.{name}")
        for name in ("feature_refs", "evidence_refs", "counterexample_refs"):
            _items(getattr(assignment, name), f"assignment.{name}", allow_empty=name == "counterexample_refs")
        if not isinstance(assignment.reviewed, bool):
            raise ValueError("assignment.reviewed must be bool")
        if assignment.counterexamples_resolved is not None and not isinstance(assignment.counterexamples_resolved, bool):
            raise ValueError("counterexamples_resolved must be bool or None")
        if assignment.assignment_id in assignment_ids:
            raise ValueError("assignment_id values must be unique")
        assignment_ids.add(assignment.assignment_id)
        if not isinstance(assignment.criterion, str) or not assignment.criterion.strip():
            missing_criterion.append(assignment.assignment_id)
        if not assignment.feature_refs or not set(assignment.feature_refs) <= feature_ids:
            declaration_mismatches.append(f"{assignment.assignment_id}:unknown_feature_ref")
        elif any(feature.subject_id != assignment.subject_id for feature in trace.selected_features if feature.feature_id in assignment.feature_refs):
            declaration_mismatches.append(f"{assignment.assignment_id}:subject_mismatch")
        if not assignment.evidence_refs:
            missing_membership.append(assignment.assignment_id)
        if assignment.counterexample_refs and assignment.counterexamples_resolved is not True:
            unresolved.append(assignment.assignment_id)

    unreviewed = (
        any(not feature.reviewed for feature in trace.selected_features)
        or any(not assignment.reviewed for assignment in trace.category_assignments)
    )
    if unreviewed:
        status = FormationStatus.UNREVIEWED
    elif not trace.observations:
        status = FormationStatus.MISSING_OBSERVATION
    elif missing_obs:
        status = FormationStatus.MISSING_FEATURE_PROVENANCE
    elif ungrounded:
        status = FormationStatus.FEATURE_NOT_GROUNDED
    elif missing_rationale:
        status = FormationStatus.MISSING_SELECTION_RATIONALE
    elif missing_criterion:
        status = FormationStatus.MISSING_CATEGORY_CRITERION
    elif declaration_mismatches:
        status = FormationStatus.DECLARATION_MISMATCH
    elif missing_membership:
        status = FormationStatus.MISSING_MEMBERSHIP_EVIDENCE
    elif unresolved:
        status = FormationStatus.COUNTEREXAMPLE_UNRESOLVED
    else:
        status = FormationStatus.PROVISIONAL_FORMATION

    return FormationAssessment(
        trace_id=trace.trace_id,
        status=status,
        missing_observation_ids=tuple(sorted(missing_obs)),
        ungrounded_feature_ids=tuple(sorted(ungrounded)),
        missing_rationale_feature_ids=tuple(sorted(missing_rationale)),
        missing_criterion_assignment_ids=tuple(sorted(missing_criterion)),
        missing_membership_evidence_ids=tuple(sorted(missing_membership)),
        unresolved_counterexample_assignment_ids=tuple(sorted(unresolved)),
        declaration_mismatches=tuple(sorted(declaration_mismatches)),
    )
