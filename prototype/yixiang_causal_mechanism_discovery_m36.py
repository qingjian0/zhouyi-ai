"""M36 causal mechanism discovery evidence and claim auditor.

This is a transparent declaration auditor, not a causal discovery algorithm.
It never estimates effects, identifies a DAG, or certifies causal truth.
"""
from dataclasses import dataclass
from enum import Enum

class EvidenceKind(str, Enum):
    OBSERVATIONAL = "observational"
    INTERVENTIONAL = "interventional"
    COUNTERFACTUAL = "counterfactual"

class ReviewState(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"

class ConfoundingState(str, Enum):
    ADDRESSED = "addressed"
    SUSPECTED = "suspected"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"

class HypothesisState(str, Enum):
    PROPOSED = "proposed"
    WEAKENED = "weakened"
    REFUTED = "refuted"
    BOUNDED = "bounded"
    VALIDATION_PENDING = "validation_pending"

class DiscoveryDisposition(str, Enum):
    BLOCKED = "blocked"
    ASSOCIATIONAL_ONLY = "associational_only"
    CONDITIONAL = "conditional"
    REVIEW_REQUIRED = "review_required"

@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: EvidenceKind
    source_family: str
    dataset_split: str
    review_state: ReviewState
    observed_variables: tuple
    intervention_target: str = ""
    design_ref: str = ""
    limitation_refs: tuple = ()

@dataclass(frozen=True)
class MechanismHypothesis:
    hypothesis_id: str
    variable_ids: tuple
    directed_edges: tuple
    functional_form_ref: str
    scope: str
    evidence_refs: tuple
    alternative_hypothesis_ids: tuple
    confounding_state: ConfoundingState
    latent_variable_refs: tuple
    discovery_split: str
    validation_split: str
    assumptions: tuple
    reviewer_ids: tuple = ()
    state: HypothesisState = HypothesisState.PROPOSED

@dataclass(frozen=True)
class FalsificationRecord:
    record_id: str
    hypothesis_id: str
    evidence_ref: str
    expected_result: str
    observed_result: str
    outcome: str
    unresolved: bool = False

@dataclass(frozen=True)
class DiscoveryAudit:
    disposition: DiscoveryDisposition
    issues: tuple
    warnings: tuple
    causal_truth_established: bool = False

def audit_mechanism_discovery(evidence=(), hypotheses=(), falsifications=()):
    evidence, hypotheses, falsifications = tuple(evidence), tuple(hypotheses), tuple(falsifications)
    issues, warnings = [], []
    em = {e.evidence_id: e for e in evidence}
    hm = {h.hypothesis_id: h for h in hypotheses}
    if len(em) != len(evidence):
        issues.append("duplicate_evidence_id")
    if len(hm) != len(hypotheses):
        issues.append("duplicate_hypothesis_id")
    for e in evidence:
        if not all((e.evidence_id, e.source_family, e.dataset_split, e.observed_variables)):
            issues.append("incomplete_evidence:" + e.evidence_id)
        if e.kind == EvidenceKind.INTERVENTIONAL and (not e.intervention_target or not e.design_ref):
            issues.append("intervention_requires_target_and_design:" + e.evidence_id)
        if e.kind == EvidenceKind.COUNTERFACTUAL and not e.design_ref:
            issues.append("counterfactual_requires_generation_or_identification_design:" + e.evidence_id)
        if e.review_state == ReviewState.DISPUTED:
            warnings.append("disputed_evidence:" + e.evidence_id)
    for h in hypotheses:
        if not all((h.hypothesis_id, h.variable_ids, h.functional_form_ref, h.scope,
                    h.discovery_split, h.validation_split)):
            issues.append("incomplete_hypothesis:" + h.hypothesis_id)
        if len(h.variable_ids) != len(set(h.variable_ids)):
            issues.append("duplicate_variable:" + h.hypothesis_id)
        if h.discovery_split == h.validation_split:
            issues.append("discovery_validation_split_overlap:" + h.hypothesis_id)
        if not h.evidence_refs:
            issues.append("hypothesis_requires_evidence:" + h.hypothesis_id)
        if not h.assumptions:
            issues.append("hypothesis_requires_assumptions:" + h.hypothesis_id)
        if not h.reviewer_ids:
            warnings.append("hypothesis_requires_human_review:" + h.hypothesis_id)
        if h.confounding_state in (ConfoundingState.UNKNOWN, ConfoundingState.SUSPECTED):
            warnings.append("confounding_unresolved:" + h.hypothesis_id)
        if h.confounding_state == ConfoundingState.UNKNOWN and not h.latent_variable_refs:
            warnings.append("latent_variable_inventory_unknown:" + h.hypothesis_id)
        if not h.alternative_hypothesis_ids:
            warnings.append("no_competing_explanation_registered:" + h.hypothesis_id)
        for ref in h.evidence_refs:
            if ref not in em:
                issues.append("unknown_evidence:" + h.hypothesis_id + ":" + ref)
        if h.state == HypothesisState.REFUTED and not any(
            f.hypothesis_id == h.hypothesis_id and f.outcome in ("failed", "reversed")
            for f in falsifications
        ):
            issues.append("refuted_hypothesis_requires_failed_or_reversed_test:" + h.hypothesis_id)
    for f in falsifications:
        if f.hypothesis_id not in hm:
            issues.append("falsification_unknown_hypothesis:" + f.record_id)
        if f.evidence_ref not in em:
            issues.append("falsification_unknown_evidence:" + f.record_id)
        if not all((f.record_id, f.expected_result, f.observed_result, f.outcome)):
            issues.append("incomplete_falsification:" + f.record_id)
        if f.unresolved:
            warnings.append("unresolved_counterexample:" + f.record_id)
    # Counterfactual/simulated evidence is not treated as independent empirical intervention.
    for h in hypotheses:
        linked = [em[r] for r in h.evidence_refs if r in em]
        if linked and all(e.kind == EvidenceKind.OBSERVATIONAL for e in linked):
            warnings.append("observational_only:" + h.hypothesis_id)
        if any(e.kind == EvidenceKind.COUNTERFACTUAL for e in linked) and not any(
            e.kind == EvidenceKind.INTERVENTIONAL for e in linked
        ):
            warnings.append("counterfactual_without_empirical_intervention:" + h.hypothesis_id)
        families = [e.source_family for e in linked]
        if len(families) != len(set(families)):
            warnings.append("shared_source_family:" + h.hypothesis_id)
        if any(e.dataset_split == h.validation_split for e in linked):
            issues.append("validation_data_used_as_discovery_evidence:" + h.hypothesis_id)
    if issues:
        disposition = DiscoveryDisposition.BLOCKED
    elif not hypotheses or all(
        all(em[r].kind == EvidenceKind.OBSERVATIONAL for r in h.evidence_refs if r in em)
        for h in hypotheses
    ):
        disposition = DiscoveryDisposition.ASSOCIATIONAL_ONLY
    elif warnings:
        disposition = DiscoveryDisposition.CONDITIONAL
    else:
        disposition = DiscoveryDisposition.REVIEW_REQUIRED
    return DiscoveryAudit(disposition, tuple(sorted(set(issues))),
                          tuple(sorted(set(warnings))), False)
