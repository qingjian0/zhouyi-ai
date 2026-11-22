"""Unified orchestration API for the symbolic classiang cognition MVP.

This module composes existing evidence-grounded primitives. It does not infer
raw features, mappings, causal semantics, or calibrated probabilities. Every
upstream annotation and mapping remains explicit and auditable.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.analogy import AnalogyCandidate, AnalogyAssessment, assess_analogy
from prototype.classiang_discovery import (
    DiscoveryResult, ObjectView, discover_classes,
)
from prototype.classiang_engine import (
    AspectSelection, ClassExample, ClassHypothesis, ClassRevisionResult,
    InductionResult, MembershipAssessment, MembershipDecision, Observation,
    assess_membership, induce_class, revise_class_with_counterexample,
    select_aspects,
)
from prototype.dynamic_analogy import (
    DynamicAnalogyAssessment, DynamicAnalogyCandidate, assess_dynamic_analogy,
)


@dataclass(frozen=True)
class RevisionRequest:
    """Complete provenance required for a counterexample-driven revision."""

    hypothesis: ClassHypothesis
    positive_examples: tuple[ClassExample, ...]
    negative_examples: tuple[ClassExample, ...]
    counterexample: ClassExample


@dataclass(frozen=True)
class ClassiangCycleRequest:
    """Inputs for one bounded cognition cycle.

    The query observation is assessed against a class induced from supplied
    examples. Transfer candidates are optional and must carry explicit
    mappings, conditions, evidence, and validity scopes.
    """

    class_id: str
    purpose: str
    validity_scope: str
    query_observation: Observation
    positive_examples: tuple[ClassExample, ...]
    negative_examples: tuple[ClassExample, ...] = ()
    min_relevance: float = 0.5
    analogy_candidate: AnalogyCandidate | None = None
    dynamic_analogy_candidate: DynamicAnalogyCandidate | None = None
    discovery_objects: tuple[ObjectView, ...] | None = None
    revision: RevisionRequest | None = None


@dataclass(frozen=True)
class ClassiangCycleResult:
    aspect_selection: AspectSelection
    induction: InductionResult
    membership: MembershipAssessment | None
    discovery: DiscoveryResult | None
    analogy_assessment: AnalogyAssessment | None
    dynamic_analogy_assessment: DynamicAnalogyAssessment | None
    revision: ClassRevisionResult | None
    transfer_gate_passed: bool
    reason_codes: tuple[str, ...]


def run_classiang_cycle(request: ClassiangCycleRequest) -> ClassiangCycleResult:
    """Run the integrated symbolic cycle with fail-closed transfer gating.

    The cycle performs task-conditioned aspect selection, class induction,
    membership assessment, optional bounded class discovery, optional static
    and dynamic relation-preservation checks, and optional local revision.

    A transfer gate passes only when the induced class is discriminative,
    the query is provisionally accepted, at least one transfer candidate was
    evaluated, and every supplied transfer assessment passes. Passing these
    structural gates is not proof of semantic or causal equivalence.
    """
    if not isinstance(request, ClassiangCycleRequest):
        raise ValueError("request must be ClassiangCycleRequest")
    if not isinstance(request.query_observation, Observation):
        raise ValueError("query_observation must be Observation")
    if not isinstance(request.positive_examples, tuple) or not request.positive_examples:
        raise ValueError("positive_examples must be a non-empty tuple")
    if not isinstance(request.negative_examples, tuple):
        raise ValueError("negative_examples must be a tuple")

    selection = select_aspects(
        request.query_observation,
        purpose=request.purpose,
        min_relevance=request.min_relevance,
    )
    induction = induce_class(
        class_id=request.class_id,
        purpose=request.purpose,
        positive_examples=request.positive_examples,
        negative_examples=request.negative_examples,
        validity_scope=request.validity_scope,
    )
    membership = (
        assess_membership(request.query_observation, induction.hypothesis)
        if induction.hypothesis is not None else None
    )

    discovery = (
        discover_classes(request.discovery_objects)
        if request.discovery_objects is not None else None
    )
    analogy_assessment = (
        assess_analogy(request.analogy_candidate)
        if request.analogy_candidate is not None else None
    )
    dynamic_assessment = (
        assess_dynamic_analogy(request.dynamic_analogy_candidate)
        if request.dynamic_analogy_candidate is not None else None
    )
    revision_result = None
    if request.revision is not None:
        revision = request.revision
        revision_result = revise_class_with_counterexample(
            hypothesis=revision.hypothesis,
            positive_examples=revision.positive_examples,
            negative_examples=revision.negative_examples,
            counterexample=revision.counterexample,
        )

    transfer_assessments = tuple(
        item for item in (analogy_assessment, dynamic_assessment)
        if item is not None
    )
    reasons: list[str] = []
    if induction.hypothesis is None:
        reasons.append("CLASS_INDUCTION_UNDERDETERMINED")
    elif induction.status.value != "discriminative":
        reasons.append("CLASS_BOUNDARY_NOT_DISCRIMINATIVE")
    if membership is None:
        reasons.append("MEMBERSHIP_NOT_ASSESSABLE")
    elif membership.decision != MembershipDecision.ACCEPT_PROVISIONAL:
        reasons.append("QUERY_NOT_ACCEPTED_BY_CLASS_RULE")
    if not transfer_assessments:
        reasons.append("NO_TRANSFER_CANDIDATE_EVALUATED")
    if any(not item.accepted for item in transfer_assessments):
        reasons.append("TRANSFER_STRUCTURE_OR_EVIDENCE_GATE_FAILED")

    transfer_gate_passed = (
        induction.hypothesis is not None
        and induction.status.value == "discriminative"
        and membership is not None
        and membership.decision == MembershipDecision.ACCEPT_PROVISIONAL
        and bool(transfer_assessments)
        and all(item.accepted for item in transfer_assessments)
    )
    if transfer_gate_passed:
        reasons.append("STRUCTURAL_TRANSFER_GATES_PASSED_NOT_SEMANTIC_PROOF")

    return ClassiangCycleResult(
        aspect_selection=selection,
        induction=induction,
        membership=membership,
        discovery=discovery,
        analogy_assessment=analogy_assessment,
        dynamic_analogy_assessment=dynamic_assessment,
        revision=revision_result,
        transfer_gate_passed=transfer_gate_passed,
        reason_codes=tuple(reasons),
    )
