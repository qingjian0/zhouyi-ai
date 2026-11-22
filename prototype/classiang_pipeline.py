"""Unified orchestration API for the symbolic classiang cognition MVP.

This module composes existing evidence-grounded primitives. It does not infer
raw features, mappings, causal semantics, or calibrated probabilities. Every
upstream annotation and mapping remains explicit and auditable.
"""
from __future__ import annotations

from dataclasses import dataclass

from prototype.analogy import (
    AnalogyCandidate, AnalogyAssessment, AnalogyDiscoveryResult, Evidence, Relation,
    assess_analogy, discover_analogy_mappings,
)
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
class AnalogyDiscoveryRequest:
    """Bounded graph-mapping search inputs; no semantic labels are inferred."""

    source_domain: str
    target_domain: str
    source_entities: tuple[str, ...]
    target_entities: tuple[str, ...]
    source_relations: tuple[Relation, ...]
    target_relations: tuple[Relation, ...]
    dimensions: tuple[str, ...] = ("relation",)
    conditions: tuple[str, ...] = ("mapping evaluated against supplied graph snapshots",)
    evidence: tuple[Evidence, ...] = ()
    validity_scope: str = "the supplied finite entity and relation graphs only"
    min_relation_f1: float = 0.8
    max_evaluations: int = 10000
    max_results: int = 20


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
    analogy_discovery: AnalogyDiscoveryRequest | None = None
    dynamic_analogy_candidate: DynamicAnalogyCandidate | None = None
    discovery_objects: tuple[ObjectView, ...] | None = None
    revision: RevisionRequest | None = None
    comparison_observations: tuple[Observation, ...] = ()


@dataclass(frozen=True)
class ClassiangCycleResult:
    aspect_selection: AspectSelection
    induction: InductionResult
    membership: MembershipAssessment | None
    discovery: DiscoveryResult | None
    analogy_assessment: AnalogyAssessment | None
    analogy_discovery: AnalogyDiscoveryResult | None
    dynamic_analogy_assessment: DynamicAnalogyAssessment | None
    revision: ClassRevisionResult | None
    comparisons: tuple[ObservationComparison, ...]
    transfer_gate_passed: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ObservationComparison:
    """Evidence-grounded aspect comparison; overlap is not semantic equivalence."""

    left_observation_id: str
    right_observation_id: str
    purpose: str
    left_aspects: tuple
    right_aspects: tuple
    shared_aspects: tuple
    left_only_aspects: tuple
    right_only_aspects: tuple
    shared_evidence_refs: tuple[str, ...]
    shared_context: tuple[str, ...]
    same_domain: bool


def compare_observations(
    left: Observation,
    right: Observation,
    *,
    purpose: str,
    min_relevance: float = 0.5,
) -> ObservationComparison:
    """Compare two observations under the same task-conditioned aspect policy.

    The result reports explicit intersections and differences only. Shared
    features, evidence references, or context do not establish class identity,
    causal equivalence, or a valid cross-domain transfer.
    """
    if not isinstance(left, Observation) or not isinstance(right, Observation):
        raise ValueError("left and right must be Observation")
    if left.observation_id == right.observation_id:
        raise ValueError("observations must have distinct IDs")
    left_selection = select_aspects(
        left, purpose=purpose, min_relevance=min_relevance,
    )
    right_selection = select_aspects(
        right, purpose=purpose, min_relevance=min_relevance,
    )
    left_set, right_set = set(left_selection.selected), set(right_selection.selected)
    return ObservationComparison(
        left_observation_id=left.observation_id,
        right_observation_id=right.observation_id,
        purpose=purpose,
        left_aspects=left_selection.selected,
        right_aspects=right_selection.selected,
        shared_aspects=tuple(sorted(left_set & right_set)),
        left_only_aspects=tuple(sorted(left_set - right_set)),
        right_only_aspects=tuple(sorted(right_set - left_set)),
        shared_evidence_refs=tuple(sorted(set(left.evidence_refs) & set(right.evidence_refs))),
        shared_context=tuple(sorted(set(left.context) & set(right.context))),
        same_domain=left.domain == right.domain,
    )


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

    if not isinstance(request.comparison_observations, tuple):
        raise ValueError("comparison_observations must be a tuple")
    comparisons = tuple(
        compare_observations(
            request.query_observation, other,
            purpose=request.purpose, min_relevance=request.min_relevance,
        )
        for other in request.comparison_observations
    )

    discovery = (
        discover_classes(request.discovery_objects)
        if request.discovery_objects is not None else None
    )
    analogy_assessment = (
        assess_analogy(request.analogy_candidate)
        if request.analogy_candidate is not None else None
    )
    analogy_discovery = None
    if request.analogy_discovery is not None:
        search = request.analogy_discovery
        analogy_discovery = discover_analogy_mappings(
            source_domain=search.source_domain,
            target_domain=search.target_domain,
            source_entities=search.source_entities,
            target_entities=search.target_entities,
            source_relations=search.source_relations,
            target_relations=search.target_relations,
            dimensions=search.dimensions,
            conditions=search.conditions,
            evidence=search.evidence,
            validity_scope=search.validity_scope,
            min_relation_f1=search.min_relation_f1,
            max_evaluations=search.max_evaluations,
            max_results=search.max_results,
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

    transfer_assessments = [
        item for item in (analogy_assessment, dynamic_assessment)
        if item is not None
    ]
    if analogy_discovery is not None:
        accepted_discoveries = [
            item.assessment for item in analogy_discovery.candidates
            if item.assessment.accepted
        ]
        if accepted_discoveries:
            transfer_assessments.append(accepted_discoveries[0])
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
        analogy_discovery=analogy_discovery,
        dynamic_analogy_assessment=dynamic_assessment,
        revision=revision_result,
        comparisons=comparisons,
        transfer_gate_passed=transfer_gate_passed,
        reason_codes=tuple(reasons),
    )
