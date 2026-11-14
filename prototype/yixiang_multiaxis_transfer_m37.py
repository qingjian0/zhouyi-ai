"""M37 multi-axis analogy transfer audit; declarations only, no semantic inference."""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Axis(str, Enum):
    MORPHOLOGY = "morphology"
    ATTRIBUTE = "attribute"
    FUNCTION = "function"
    RELATION = "relation"
    PROCESS = "process"
    MECHANISM = "mechanism"
    SYSTEM_BEHAVIOR = "system_behavior"
    TIME = "time"
    POSITION = "position"
    POTENTIAL = "potential"
    ENVIRONMENT = "environment"
    PHASE = "phase"
    SCALE = "scale"


class EvidenceSide(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class EvidenceKind(str, Enum):
    CLASSICAL_TEXT = "classical_text"
    COMMENTARY = "commentary"
    MODERN_STUDY = "modern_study"
    OBSERVATION = "observation"
    INTERVENTION = "intervention"
    SIMULATION = "simulation"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    MODEL_ASSUMPTION = "model_assumption"


class ReviewState(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class MappingOutcome(str, Enum):
    PRESERVED = "preserved"
    PARTIAL = "partial"
    VIOLATED = "violated"
    CONFLICTED = "conflicted"
    UNASSESSED = "unassessed"


class ConstraintOutcome(str, Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    CONFLICTED = "conflicted"
    UNRESOLVED = "unresolved"


class AuditDisposition(str, Enum):
    BLOCKED = "blocked"
    REJECTED = "rejected"
    REVIEW_REQUIRED = "review_required"
    CONDITIONAL = "conditional"
    ELIGIBLE_FOR_EXTERNAL_VALIDATION = "eligible_for_external_validation"


@dataclass(frozen=True)
class SourceVersion:
    source_id: str
    version_id: str
    witness_id: str
    lineage_root_id: str
    layer: str
    locator: str


@dataclass(frozen=True)
class AxisEvidence:
    evidence_id: str
    axis: Axis
    side: EvidenceSide
    context_id: str
    source_version_ref: str
    kind: EvidenceKind
    review_state: ReviewState
    limitation_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AxisMapping:
    mapping_id: str
    axis: Axis
    source_value: str
    target_value: str
    mapping_rule_ref: str
    scope: str
    evidence_refs: Tuple[str, ...]
    outcome: MappingOutcome
    counterexample_refs: Tuple[str, ...] = ()
    reviewer_ids: Tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class CrossAxisConstraint:
    constraint_id: str
    mapping_refs: Tuple[str, ...]
    rule_ref: str
    evidence_refs: Tuple[str, ...]
    outcome: ConstraintOutcome
    scope: str
    counterexample_refs: Tuple[str, ...] = ()
    reviewer_ids: Tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class TransferCandidate:
    candidate_id: str
    source_context_id: str
    target_context_id: str
    required_axes: Tuple[Axis, ...]
    mappings: Tuple[AxisMapping, ...]
    constraints: Tuple[CrossAxisConstraint, ...]
    scope: str
    limitations: Tuple[str, ...]


@dataclass(frozen=True)
class AuditReport:
    disposition: AuditDisposition
    issues: Tuple[str, ...]
    warnings: Tuple[str, ...]
    axis_status: Tuple[Tuple[str, str], ...]
    eligible_axes: Tuple[str, ...]
    rejected_axes: Tuple[str, ...]
    unresolved_constraints: Tuple[str, ...]
    semantic_equivalence_established: bool = False
    causal_equivalence_established: bool = False


def audit_multiaxis_transfer(candidate, source_versions=(), evidence=()):
    """Audit a declared multi-axis mapping without deriving semantic truth."""
    if not isinstance(candidate, TransferCandidate):
        raise ValueError("candidate must be a TransferCandidate")
    source_versions, evidence = tuple(source_versions), tuple(evidence)
    issues, warnings = [], []

    if not all((candidate.candidate_id, candidate.source_context_id,
                candidate.target_context_id, candidate.scope, candidate.limitations)):
        issues.append("incomplete_candidate")
    if candidate.source_context_id == candidate.target_context_id:
        issues.append("source_and_target_context_must_differ")
    if len(candidate.required_axes) < 2:
        issues.append("multi_axis_candidate_requires_at_least_two_axes")
    if any(not isinstance(axis, Axis) for axis in candidate.required_axes):
        issues.append("invalid_required_axis")
    if len(candidate.required_axes) != len(set(candidate.required_axes)):
        issues.append("duplicate_required_axis")
    valid_required_axes = tuple(axis for axis in candidate.required_axes if isinstance(axis, Axis))

    if any(not isinstance(v, SourceVersion) for v in source_versions):
        raise ValueError("source_versions must contain SourceVersion items")
    version_map = {v.version_id: v for v in source_versions}
    if len(version_map) != len(source_versions):
        issues.append("duplicate_source_version_id")
    for v in source_versions:
        if not all((v.source_id, v.version_id, v.witness_id, v.lineage_root_id,
                    v.layer, v.locator)):
            issues.append("incomplete_source_version:" + (v.version_id or "<empty>"))

    if any(not isinstance(e, AxisEvidence) for e in evidence):
        raise ValueError("evidence must contain AxisEvidence items")
    evidence_map = {e.evidence_id: e for e in evidence}
    if len(evidence_map) != len(evidence):
        issues.append("duplicate_evidence_id")
    for e in evidence:
        if not all((e.evidence_id, e.context_id, e.source_version_ref)):
            issues.append("incomplete_evidence:" + (e.evidence_id or "<empty>"))
        if not isinstance(e.axis, Axis) or not isinstance(e.side, EvidenceSide):
            issues.append("invalid_evidence_axis_or_side:" + e.evidence_id)
        if not isinstance(e.kind, EvidenceKind) or not isinstance(e.review_state, ReviewState):
            issues.append("invalid_evidence_kind_or_review_state:" + e.evidence_id)
        if e.context_id not in (candidate.source_context_id, candidate.target_context_id):
            issues.append("evidence_context_outside_candidate:" + e.evidence_id)
        expected_context = (candidate.source_context_id if e.side == EvidenceSide.SOURCE
                            else candidate.target_context_id)
        if e.context_id != expected_context:
            issues.append("evidence_side_context_mismatch:" + e.evidence_id)
        if e.source_version_ref not in version_map:
            issues.append("unknown_source_version:" + e.evidence_id)

    if any(not isinstance(m, AxisMapping) for m in candidate.mappings):
        raise ValueError("mappings must contain AxisMapping items")
    mapping_map = {m.mapping_id: m for m in candidate.mappings}
    if len(mapping_map) != len(candidate.mappings):
        issues.append("duplicate_mapping_id")
    for m in candidate.mappings:
        if not isinstance(m.axis, Axis) or not isinstance(m.outcome, MappingOutcome):
            issues.append("invalid_mapping_axis_or_outcome:" + m.mapping_id)
        if not all((m.mapping_id, m.source_value, m.target_value,
                    m.mapping_rule_ref, m.scope, m.rationale)):
            issues.append("incomplete_mapping:" + (m.mapping_id or "<empty>"))
        if len(m.evidence_refs) != len(set(m.evidence_refs)):
            issues.append("duplicate_mapping_evidence:" + m.mapping_id)
        refs = [evidence_map[x] for x in m.evidence_refs if x in evidence_map]
        if len(refs) != len(m.evidence_refs):
            issues.append("unknown_mapping_evidence:" + m.mapping_id)
        if m.outcome != MappingOutcome.UNASSESSED:
            if not refs:
                issues.append("assessed_mapping_requires_evidence:" + m.mapping_id)
            if any(e.axis != m.axis for e in refs):
                issues.append("mapping_evidence_axis_mismatch:" + m.mapping_id)
            sides = {e.side for e in refs}
            if sides != {EvidenceSide.SOURCE, EvidenceSide.TARGET}:
                issues.append("mapping_evidence_must_cover_source_and_target:" + m.mapping_id)
            if not m.reviewer_ids and m.outcome in (
                MappingOutcome.PRESERVED, MappingOutcome.VIOLATED, MappingOutcome.CONFLICTED
            ):
                issues.append("adjudicated_mapping_requires_reviewer:" + m.mapping_id)
        if not set(m.counterexample_refs).issubset(set(m.evidence_refs)):
            issues.append("counterexamples_must_be_linked_evidence:" + m.mapping_id)
        if m.outcome == MappingOutcome.PRESERVED:
            if any(e.review_state != ReviewState.REVIEWED for e in refs):
                issues.append("preserved_mapping_requires_reviewed_evidence:" + m.mapping_id)
            if m.counterexample_refs:
                issues.append("preserved_mapping_has_counterexamples:" + m.mapping_id)
            target_kinds = {e.kind for e in refs if e.side == EvidenceSide.TARGET}
            if target_kinds and target_kinds.issubset({
                EvidenceKind.SIMULATION, EvidenceKind.SYNTHETIC_FIXTURE,
                EvidenceKind.MODEL_ASSUMPTION
            }):
                warnings.append("non_empirical_target_support:" + m.mapping_id)
        elif m.outcome == MappingOutcome.VIOLATED and not m.counterexample_refs:
            issues.append("violated_mapping_requires_counterexample:" + m.mapping_id)
        elif m.outcome == MappingOutcome.CONFLICTED and len(refs) < 2:
            issues.append("conflicted_mapping_requires_multiple_evidence_items:" + m.mapping_id)
        roots = [version_map[e.source_version_ref].lineage_root_id for e in refs
                 if e.source_version_ref in version_map]
        if len(roots) != len(set(roots)):
            warnings.append("shared_declared_lineage:" + m.mapping_id)

    axis_status = {}
    for axis in valid_required_axes:
        related = [m.outcome for m in candidate.mappings if m.axis == axis]
        if not related:
            issues.append("missing_required_axis:" + axis.value)
            continue
        outcomes = set(related)
        if MappingOutcome.VIOLATED in outcomes:
            status = MappingOutcome.VIOLATED.value
        elif MappingOutcome.CONFLICTED in outcomes:
            status = MappingOutcome.CONFLICTED.value
        elif outcomes == {MappingOutcome.PRESERVED}:
            status = MappingOutcome.PRESERVED.value
        elif outcomes == {MappingOutcome.UNASSESSED}:
            status = MappingOutcome.UNASSESSED.value
        else:
            status = MappingOutcome.PARTIAL.value
        axis_status[axis.value] = status

    if any(not isinstance(c, CrossAxisConstraint) for c in candidate.constraints):
        raise ValueError("constraints must contain CrossAxisConstraint items")
    constraint_map = {c.constraint_id: c for c in candidate.constraints}
    if len(constraint_map) != len(candidate.constraints):
        issues.append("duplicate_constraint_id")
    used_axes = set()
    unresolved_constraints = []
    for c in candidate.constraints:
        if not isinstance(c.outcome, ConstraintOutcome):
            issues.append("invalid_constraint_outcome:" + str(c.constraint_id))
        if not all((c.constraint_id, c.rule_ref, c.scope, c.rationale)):
            issues.append("incomplete_cross_axis_constraint:" + (c.constraint_id or "<empty>"))
        if len(c.mapping_refs) < 2 or len(c.mapping_refs) != len(set(c.mapping_refs)):
            issues.append("cross_axis_constraint_requires_distinct_mappings:" + c.constraint_id)
        refs = [mapping_map[x] for x in c.mapping_refs if x in mapping_map]
        if len(refs) != len(c.mapping_refs):
            issues.append("unknown_constraint_mapping:" + c.constraint_id)
        axes = {m.axis for m in refs}
        if len(axes) < 2:
            issues.append("constraint_must_span_multiple_axes:" + c.constraint_id)
        used_axes.update(axes)
        erefs = [evidence_map[x] for x in c.evidence_refs if x in evidence_map]
        if not c.evidence_refs or len(erefs) != len(c.evidence_refs):
            issues.append("missing_or_unknown_constraint_evidence:" + c.constraint_id)
        elif len({e.axis for e in erefs}) < 2:
            issues.append("constraint_evidence_must_cover_multiple_axes:" + c.constraint_id)
        if not set(c.counterexample_refs).issubset(set(c.evidence_refs)):
            issues.append("constraint_counterexamples_must_be_linked_evidence:" + c.constraint_id)
        if c.outcome == ConstraintOutcome.SATISFIED:
            if not c.reviewer_ids or any(e.review_state != ReviewState.REVIEWED for e in erefs):
                issues.append("satisfied_constraint_requires_reviewed_evidence_and_reviewer:" + c.constraint_id)
            if c.counterexample_refs:
                issues.append("satisfied_constraint_has_counterexamples:" + c.constraint_id)
        elif c.outcome == ConstraintOutcome.VIOLATED and not c.counterexample_refs:
            issues.append("violated_constraint_requires_counterexample:" + c.constraint_id)
        elif c.outcome == ConstraintOutcome.CONFLICTED and len(erefs) < 2:
            issues.append("conflicted_constraint_requires_multiple_evidence_items:" + c.constraint_id)
        if c.outcome in (ConstraintOutcome.UNRESOLVED, ConstraintOutcome.CONFLICTED):
            unresolved_constraints.append(c.constraint_id)

    for axis in valid_required_axes:
        if axis not in used_axes:
            warnings.append("required_axis_not_cross_checked:" + axis.value)
    if not candidate.constraints:
        warnings.append("no_cross_axis_constraints_registered")

    if issues:
        disposition = AuditDisposition.BLOCKED
    elif any(v == MappingOutcome.VIOLATED.value for v in axis_status.values()) or any(
        c.outcome == ConstraintOutcome.VIOLATED for c in candidate.constraints
    ):
        disposition = AuditDisposition.REJECTED
    elif any(v == MappingOutcome.CONFLICTED.value for v in axis_status.values()) or any(
        c.outcome == ConstraintOutcome.CONFLICTED for c in candidate.constraints
    ):
        disposition = AuditDisposition.REVIEW_REQUIRED
    elif any(v != MappingOutcome.PRESERVED.value for v in axis_status.values()) or any(
        c.outcome != ConstraintOutcome.SATISFIED for c in candidate.constraints
    ) or warnings:
        disposition = AuditDisposition.CONDITIONAL
    else:
        disposition = AuditDisposition.ELIGIBLE_FOR_EXTERNAL_VALIDATION

    eligible = tuple(sorted(k for k, v in axis_status.items()
                            if v == MappingOutcome.PRESERVED.value))
    rejected = tuple(sorted(k for k, v in axis_status.items()
                            if v == MappingOutcome.VIOLATED.value))
    return AuditReport(
        disposition=disposition,
        issues=tuple(sorted(set(issues))),
        warnings=tuple(sorted(set(warnings))),
        axis_status=tuple(sorted(axis_status.items())),
        eligible_axes=eligible,
        rejected_axes=rejected,
        unresolved_constraints=tuple(sorted(unresolved_constraints)),
    )
