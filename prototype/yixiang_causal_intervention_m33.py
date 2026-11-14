"""M33 causal intervention and counterfactual audit for invariant compositions.

This module audits study design and evidence provenance. It never infers causality
from association and never certifies a causal claim as true.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class InterventionKind(str, Enum):
    REMOVE_MEMBER = "remove_member"
    SUBSTITUTE_MEMBER = "substitute_member"
    REMOVE_EDGE = "remove_edge"
    SWAP_ORDER = "swap_order"
    CHANGE_CONTEXT = "change_context"
    SET_MEMBER_VALUE = "set_member_value"


class AssignmentKind(str, Enum):
    RANDOMIZED = "randomized"
    QUASI_EXPERIMENTAL = "quasi_experimental"
    OBSERVATIONAL = "observational"
    SIMULATED = "simulated"


class EvidenceReview(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"


class CausalDisposition(str, Enum):
    BLOCKED = "blocked"
    ASSOCIATIONAL_ONLY = "associational_only"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class Intervention:
    intervention_id: str
    composition_id: str
    kind: InterventionKind
    target_id: str
    control_condition: str
    treatment_condition: str
    controlled_factors: Tuple[str, ...]
    changed_factors: Tuple[str, ...]
    predicted_direction: str
    preregistration_ref: str


@dataclass(frozen=True)
class StudyUnit:
    unit_id: str
    unit_family: str
    context_family: str
    source_family: str
    intervention_id: str
    condition: str
    outcome: float
    outcome_measure: str
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class CausalEvidence:
    evidence_id: str
    source_family: str
    method: str
    review: EvidenceReview
    context_family: str


@dataclass(frozen=True)
class CounterfactualPair:
    pair_id: str
    intervention_id: str
    unit_family: str
    control_unit_id: str
    treatment_unit_id: str
    matching_basis: str
    exchangeability_argument: str
    consistency_argument: str
    positivity_argument: str
    interference_assessment: str


@dataclass(frozen=True)
class CausalClaim:
    claim_id: str
    intervention_id: str
    estimand: str
    target_population: str
    identification_strategy: str
    assumptions: Tuple[str, ...]
    alternative_explanations: Tuple[str, ...]
    effect_estimate: str
    uncertainty_method: str
    evidence_refs: Tuple[str, ...]
    reviewer_ids: Tuple[str, ...]


@dataclass(frozen=True)
class CausalAudit:
    valid: bool
    disposition: CausalDisposition
    issues: Tuple[str, ...]
    claim_dispositions: Tuple[Tuple[str, str], ...]
    causal_truth_established: bool = False


def audit_causal_interventions_m33(interventions, units, evidence, pairs=(), claims=()):
    interventions = tuple(interventions)
    units = tuple(units)
    evidence = tuple(evidence)
    pairs = tuple(pairs)
    claims = tuple(claims)
    issues = []
    needs_review = False

    imap = {x.intervention_id: x for x in interventions}
    umap = {x.unit_id: x for x in units}
    emap = {x.evidence_id: x for x in evidence}
    if len(imap) != len(interventions): issues.append("duplicate_intervention_id")
    if len(umap) != len(units): issues.append("duplicate_unit_id")
    if len(emap) != len(evidence): issues.append("duplicate_evidence_id")

    for item in interventions:
        if not all((item.intervention_id, item.composition_id, item.target_id,
                    item.control_condition, item.treatment_condition,
                    item.predicted_direction, item.preregistration_ref)):
            issues.append("incomplete_intervention:" + item.intervention_id)
        if item.control_condition == item.treatment_condition:
            issues.append("intervention_conditions_must_differ:" + item.intervention_id)
        if not item.changed_factors:
            issues.append("intervention_requires_changed_factor:" + item.intervention_id)
        if set(item.changed_factors) & set(item.controlled_factors):
            issues.append("factor_both_changed_and_controlled:" + item.intervention_id)
        if item.kind == InterventionKind.CHANGE_CONTEXT and not any(
            "context" in x.lower() for x in item.changed_factors
        ):
            issues.append("context_intervention_must_change_context:" + item.intervention_id)
        if item.kind == InterventionKind.SWAP_ORDER and not any(
            "order" in x.lower() for x in item.changed_factors
        ):
            issues.append("order_intervention_must_change_order:" + item.intervention_id)

    for ev in evidence:
        if not all((ev.evidence_id, ev.source_family, ev.method, ev.context_family)):
            issues.append("incomplete_evidence:" + ev.evidence_id)
        if ev.review != EvidenceReview.REVIEWED:
            needs_review = True

    for unit in units:
        if unit.intervention_id not in imap:
            issues.append("unknown_unit_intervention:" + unit.unit_id)
        if not all((unit.unit_id, unit.unit_family, unit.context_family,
                    unit.source_family, unit.condition, unit.outcome_measure)):
            issues.append("incomplete_study_unit:" + unit.unit_id)
        if not unit.evidence_refs:
            issues.append("unit_requires_evidence:" + unit.unit_id)
        for ref in unit.evidence_refs:
            if ref not in emap:
                issues.append("unknown_unit_evidence:" + unit.unit_id + ":" + ref)
            elif emap[ref].context_family != unit.context_family:
                issues.append("unit_evidence_context_mismatch:" + unit.unit_id + ":" + ref)

    pair_ids = [p.pair_id for p in pairs]
    if len(pair_ids) != len(set(pair_ids)): issues.append("duplicate_pair_id")
    paired_units = set()
    for pair in pairs:
        intervention = imap.get(pair.intervention_id)
        control = umap.get(pair.control_unit_id)
        treatment = umap.get(pair.treatment_unit_id)
        if intervention is None:
            issues.append("unknown_pair_intervention:" + pair.pair_id)
        if control is None or treatment is None:
            issues.append("unknown_pair_unit:" + pair.pair_id)
            continue
        if control.unit_id == treatment.unit_id:
            issues.append("counterfactual_pair_requires_distinct_units:" + pair.pair_id)
        if control.unit_id in paired_units or treatment.unit_id in paired_units:
            issues.append("unit_reused_across_pairs:" + pair.pair_id)
        paired_units.update((control.unit_id, treatment.unit_id))
        if control.intervention_id != pair.intervention_id or treatment.intervention_id != pair.intervention_id:
            issues.append("pair_intervention_mismatch:" + pair.pair_id)
        if control.condition != intervention.control_condition or treatment.condition != intervention.treatment_condition:
            issues.append("pair_condition_mismatch:" + pair.pair_id)
        if control.unit_family != pair.unit_family or treatment.unit_family != pair.unit_family:
            issues.append("pair_unit_family_mismatch:" + pair.pair_id)
        if control.outcome_measure != treatment.outcome_measure:
            issues.append("pair_outcome_measure_mismatch:" + pair.pair_id)
        if not all((pair.matching_basis.strip(), pair.exchangeability_argument.strip(),
                    pair.consistency_argument.strip(), pair.positivity_argument.strip(),
                    pair.interference_assessment.strip())):
            issues.append("incomplete_counterfactual_assumptions:" + pair.pair_id)
        # A pair of distinct units is not an observed individual-level counterfactual.
        # It is a matched comparison and requires exchangeability assumptions.
        if control.unit_id != treatment.unit_id:
            needs_review = True

    claim_ids = [c.claim_id for c in claims]
    if len(claim_ids) != len(set(claim_ids)): issues.append("duplicate_claim_id")
    claim_states = []
    for claim in claims:
        intervention = imap.get(claim.intervention_id)
        if intervention is None:
            issues.append("unknown_claim_intervention:" + claim.claim_id)
            claim_states.append((claim.claim_id, "blocked"))
            continue
        if not all((claim.claim_id, claim.estimand.strip(), claim.target_population.strip(),
                    claim.identification_strategy.strip(), claim.effect_estimate.strip(),
                    claim.uncertainty_method.strip())):
            issues.append("incomplete_causal_claim:" + claim.claim_id)
        if not claim.assumptions or not claim.alternative_explanations or not claim.reviewer_ids:
            issues.append("causal_claim_requires_assumptions_alternatives_reviewers:" + claim.claim_id)
        if not claim.evidence_refs:
            issues.append("causal_claim_requires_evidence:" + claim.claim_id)
        refs = [emap[r] for r in claim.evidence_refs if r in emap]
        if len(refs) != len(claim.evidence_refs):
            issues.append("unknown_claim_evidence:" + claim.claim_id)
        if any(x.review != EvidenceReview.REVIEWED for x in refs):
            needs_review = True
        assignment_types = {
            getattr(u, "assignment_kind", AssignmentKind.OBSERVATIONAL.value)
            for u in units if u.intervention_id == claim.intervention_id
        }
        # StudyUnit intentionally does not encode assignment; design strength is declared
        # by the identification strategy and audited conservatively.
        if "random" not in claim.identification_strategy.lower() and "quasi" not in claim.identification_strategy.lower():
            claim_states.append((claim.claim_id, "associational_only"))
            needs_review = True
        elif not claim.assumptions or not claim.alternative_explanations:
            claim_states.append((claim.claim_id, "blocked"))
        else:
            claim_states.append((claim.claim_id, "review_required"))
            needs_review = True
        if not any(p.intervention_id == claim.intervention_id for p in pairs):
            issues.append("causal_claim_requires_counterfactual_design:" + claim.claim_id)

    valid = not issues
    if not valid:
        disposition = CausalDisposition.BLOCKED
    elif any(state == "associational_only" for _, state in claim_states):
        disposition = CausalDisposition.ASSOCIATIONAL_ONLY
    else:
        disposition = CausalDisposition.REVIEW_REQUIRED if needs_review or claims else CausalDisposition.ASSOCIATIONAL_ONLY
    return CausalAudit(valid, disposition, tuple(sorted(set(issues))),
                       tuple(sorted(claim_states)), False)
