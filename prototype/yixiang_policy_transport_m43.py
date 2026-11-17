"""M43 audit of transporting adaptive experiment policies across contexts."""
from dataclasses import dataclass
from enum import Enum
from math import isfinite

class Invariance(str, Enum):
    SUPPORTED="supported"
    CONDITIONAL="conditional"
    UNKNOWN="unknown"
    REFUTED="refuted"

class Difference(str, Enum):
    POPULATION="population"
    MEASUREMENT="measurement"
    ACTION_VERSION="action_version"
    OUTCOME_DEFINITION="outcome_definition"
    MECHANISM="mechanism"
    SELECTION="selection"

class TransportStatus(str, Enum):
    CONDITIONALLY_TRANSPORTABLE="conditionally_transportable"
    REVIEW_REQUIRED="review_required"
    BLOCKED="blocked"

@dataclass(frozen=True)
class Domain:
    domain_id: str
    population_ref: str
    context_ref: str
    measurement_ref: str
    action_version: str
    outcome_definition: str

@dataclass(frozen=True)
class DomainDifference:
    difference: Difference
    description: str
    evidence_ref: str
    adjusted: bool

@dataclass(frozen=True)
class MechanismInvariant:
    mechanism_id: str
    status: Invariance
    source_evidence_ref: str
    target_evidence_ref: str
    reviewer: str

@dataclass(frozen=True)
class PolicyTransportQuery:
    source: Domain
    target: Domain
    source_policy_ref: str
    target_support_ref: str
    target_overlap: float
    target_value_estimate: float
    differences: tuple
    invariants: tuple
    target_validation_ref: str
    target_population_defined: bool

@dataclass(frozen=True)
class TransportAudit:
    status: TransportStatus
    target_value_estimate: float
    issues: tuple
    warnings: tuple
    policy_execution_authorized: bool = False
    causal_effect_certified: bool = False

def audit_policy_transport(q, minimum_overlap=0.8):
    issues=[]; warnings=[]
    if q.source.domain_id==q.target.domain_id: issues.append("source_and_target_domain_identical")
    if not all((q.source.population_ref,q.source.context_ref,q.source.measurement_ref,
                q.source.action_version,q.source.outcome_definition,q.target.population_ref,
                q.target.context_ref,q.target.measurement_ref,q.target.action_version,
                q.target.outcome_definition,q.source_policy_ref,q.target_support_ref,
                q.target_validation_ref)): issues.append("missing_domain_or_policy_provenance")
    if not q.target_population_defined: issues.append("target_population_not_defined")
    if not isfinite(q.target_overlap) or not 0<=q.target_overlap<=1: issues.append("invalid_target_overlap")
    if not isfinite(q.target_value_estimate): issues.append("invalid_target_value")
    if q.target_overlap<minimum_overlap: warnings.append("insufficient_target_support_overlap")
    known={d.difference for d in q.differences}
    required=set()
    if q.source.population_ref!=q.target.population_ref: required.add(Difference.POPULATION)
    if q.source.measurement_ref!=q.target.measurement_ref: required.add(Difference.MEASUREMENT)
    if q.source.action_version!=q.target.action_version: required.add(Difference.ACTION_VERSION)
    if q.source.outcome_definition!=q.target.outcome_definition: required.add(Difference.OUTCOME_DEFINITION)
    if q.source.context_ref!=q.target.context_ref: required.add(Difference.MECHANISM)
    if q.source.context_ref!=q.target.context_ref: required.add(Difference.SELECTION)
    if required-known: issues.extend("unrecorded_domain_difference:"+x.value for x in sorted(required-known,key=lambda x:x.value))
    if q.source.context_ref!=q.target.context_ref and not q.invariants:
        issues.append("missing_mechanism_invariance_evidence")
    for d in q.differences:
        if not d.description or not d.evidence_ref: issues.append("difference_missing_evidence:"+d.difference.value)
        if not d.adjusted: warnings.append("difference_not_adjusted:"+d.difference.value)
    for inv in q.invariants:
        if not inv.mechanism_id or not inv.source_evidence_ref or not inv.target_evidence_ref or not inv.reviewer:
            issues.append("invariant_missing_review_evidence:"+inv.mechanism_id)
        if inv.status==Invariance.REFUTED: issues.append("mechanism_invariance_refuted:"+inv.mechanism_id)
        if inv.status in (Invariance.UNKNOWN,Invariance.CONDITIONAL):
            warnings.append("mechanism_invariance_not_fully_supported:"+inv.mechanism_id)
    if issues:
        return TransportAudit(TransportStatus.BLOCKED,q.target_value_estimate,tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    if q.target_overlap<minimum_overlap or any(not d.adjusted for d in q.differences) or any(i.status!=Invariance.SUPPORTED for i in q.invariants):
        status=TransportStatus.REVIEW_REQUIRED
    else:
        status=TransportStatus.CONDITIONALLY_TRANSPORTABLE
    warnings.extend(("transportability_is_conditional_on_recorded_selection_and_mechanism_assumptions",
                     "target_value_is_caller_supplied_not_estimated_here",
                     "policy_transport_does_not_imply_effect_transport_or_policy_optimality"))
    return TransportAudit(status,q.target_value_estimate,(),tuple(sorted(set(warnings))),False,False)
