"""M35 causal transportability and mechanism invariance declaration auditor.

This prototype audits explicit cross-domain assumptions. It does not run do-calculus,
estimate transport formulas, or certify causal truth.
"""
from dataclasses import dataclass
from enum import Enum

class DifferenceKind(str, Enum):
    POPULATION_DISTRIBUTION="population_distribution"
    MECHANISM_FUNCTION="mechanism_function"
    MEASUREMENT="measurement"
    TREATMENT_VERSION="treatment_version"
    SELECTION_PROCESS="selection_process"
    OUTCOME_DEFINITION="outcome_definition"
    UNKNOWN="unknown"

class InvarianceState(str, Enum):
    CLAIMED="claimed"
    EVIDENCE_SUPPORTED="evidence_supported"
    REFUTED="refuted"
    UNKNOWN="unknown"
    NOT_APPLICABLE="not_applicable"

class TransportDisposition(str, Enum):
    BLOCKED="blocked"
    NOT_IDENTIFIED="not_identified"
    CONDITIONAL="conditional"
    REVIEW_REQUIRED="review_required"

@dataclass(frozen=True)
class DomainSpec:
    domain_id:str
    population_definition:str
    context_family:str
    measurement_protocol:str
    treatment_version:str
    outcome_definition:str
    data_profile_ref:str

@dataclass(frozen=True)
class MechanismSpec:
    mechanism_id:str
    variable_id:str
    parent_ids:tuple
    functional_form_ref:str
    context_scope:tuple
    evidence_refs:tuple

@dataclass(frozen=True)
class DomainDifference:
    difference_id:str
    source_domain_id:str
    target_domain_id:str
    variable_id:str
    kind:DifferenceKind
    description:str
    evidence_refs:tuple

@dataclass(frozen=True)
class InvarianceClaim:
    claim_id:str
    mechanism_id:str
    source_domain_id:str
    target_domain_id:str
    state:InvarianceState
    evidence_refs:tuple
    counterexample_refs:tuple
    reviewer_ids:tuple
    scope:str

@dataclass(frozen=True)
class TransportQuery:
    query_id:str
    source_domain_id:str
    target_domain_id:str
    treatment_id:str
    outcome_id:str
    estimand:str
    target_population:str
    selection_diagram_ref:str
    identification_argument_ref:str
    required_data_refs:tuple

@dataclass(frozen=True)
class TransportAudit:
    disposition:TransportDisposition
    issues:tuple
    unsupported_invariances:tuple
    causal_truth_established:bool=False

def audit_transportability(domains=(), mechanisms=(), differences=(),
                           invariance_claims=(), queries=()):
    domains,mechanisms,differences=tuple(domains),tuple(mechanisms),tuple(differences)
    invariance_claims,queries=tuple(invariance_claims),tuple(queries)
    issues=[]; unsupported=[]
    dm={d.domain_id:d for d in domains}
    mm={m.mechanism_id:m for m in mechanisms}
    if len(dm)!=len(domains): issues.append("duplicate_domain_id")
    if len(mm)!=len(mechanisms): issues.append("duplicate_mechanism_id")
    for d in domains:
        if not all((d.domain_id,d.population_definition,d.context_family,
                    d.measurement_protocol,d.treatment_version,d.outcome_definition,
                    d.data_profile_ref)):
            issues.append("incomplete_domain_spec:"+d.domain_id)
    for m in mechanisms:
        if not all((m.mechanism_id,m.variable_id,m.functional_form_ref,m.context_scope)) or not m.evidence_refs:
            issues.append("incomplete_mechanism_spec:"+m.mechanism_id)
        if len(m.parent_ids)!=len(set(m.parent_ids)):
            issues.append("duplicate_mechanism_parent:"+m.mechanism_id)
        if m.mechanism_id in m.parent_ids or m.variable_id in m.parent_ids:
            issues.append("self_referential_mechanism:"+m.mechanism_id)
    diffids=[x.difference_id for x in differences]
    if len(diffids)!=len(set(diffids)): issues.append("duplicate_domain_difference_id")
    for x in differences:
        if x.source_domain_id not in dm or x.target_domain_id not in dm:
            issues.append("difference_unknown_domain:"+x.difference_id)
        if x.source_domain_id==x.target_domain_id:
            issues.append("difference_domains_must_differ:"+x.difference_id)
        if not x.variable_id or not x.description or not x.evidence_refs:
            issues.append("incomplete_domain_difference:"+x.difference_id)
    claimids=[c.claim_id for c in invariance_claims]
    if len(claimids)!=len(set(claimids)): issues.append("duplicate_invariance_claim_id")
    for c in invariance_claims:
        if c.mechanism_id not in mm: issues.append("claim_unknown_mechanism:"+c.claim_id)
        if c.source_domain_id not in dm or c.target_domain_id not in dm:
            issues.append("claim_unknown_domain:"+c.claim_id)
        if c.source_domain_id==c.target_domain_id: issues.append("claim_domains_must_differ:"+c.claim_id)
        if not c.scope.strip() or not c.reviewer_ids:
            issues.append("invariance_claim_requires_scope_and_review:"+c.claim_id)
        if c.state==InvarianceState.EVIDENCE_SUPPORTED and not c.evidence_refs:
            issues.append("supported_invariance_requires_evidence:"+c.claim_id)
        if c.state==InvarianceState.REFUTED and not c.counterexample_refs:
            issues.append("refuted_invariance_requires_counterexample:"+c.claim_id)
        if c.state in (InvarianceState.CLAIMED,InvarianceState.UNKNOWN):
            unsupported.append(c.claim_id)
    for q in queries:
        if q.source_domain_id not in dm or q.target_domain_id not in dm:
            issues.append("query_unknown_domain:"+q.query_id)
        if q.source_domain_id==q.target_domain_id:
            issues.append("transport_query_requires_distinct_domains:"+q.query_id)
        if not all((q.query_id,q.treatment_id,q.outcome_id,q.estimand,
                    q.target_population,q.selection_diagram_ref,
                    q.identification_argument_ref)):
            issues.append("incomplete_transport_query:"+q.query_id)
        if not q.required_data_refs:
            issues.append("transport_query_requires_data_inventory:"+q.query_id)
        if q.source_domain_id in dm and q.target_domain_id in dm:
            sd,td=dm[q.source_domain_id],dm[q.target_domain_id]
            if sd.measurement_protocol!=td.measurement_protocol and not any(
                x.kind==DifferenceKind.MEASUREMENT and
                x.source_domain_id==q.source_domain_id and
                x.target_domain_id==q.target_domain_id for x in differences):
                issues.append("unrecorded_measurement_difference:"+q.query_id)
            if sd.treatment_version!=td.treatment_version and not any(
                x.kind==DifferenceKind.TREATMENT_VERSION and
                x.source_domain_id==q.source_domain_id and
                x.target_domain_id==q.target_domain_id for x in differences):
                issues.append("unrecorded_treatment_version_difference:"+q.query_id)
            if sd.outcome_definition!=td.outcome_definition and not any(
                x.kind==DifferenceKind.OUTCOME_DEFINITION and
                x.source_domain_id==q.source_domain_id and
                x.target_domain_id==q.target_domain_id for x in differences):
                issues.append("unrecorded_outcome_definition_difference:"+q.query_id)
    # A declared difference in a mechanism variable defeats an unqualified
    # invariance claim for that mechanism unless explicitly scoped elsewhere.
    for c in invariance_claims:
        m=mm.get(c.mechanism_id)
        if m and any(x.variable_id==m.variable_id and
            x.source_domain_id==c.source_domain_id and
            x.target_domain_id==c.target_domain_id and
            x.kind==DifferenceKind.MECHANISM_FUNCTION for x in differences):
            if c.state==InvarianceState.EVIDENCE_SUPPORTED:
                issues.append("mechanism_difference_conflicts_with_invariance:"+c.claim_id)
    if issues:
        disposition=TransportDisposition.BLOCKED
    elif unsupported:
        disposition=TransportDisposition.CONDITIONAL
    elif not queries:
        disposition=TransportDisposition.NOT_IDENTIFIED
    else:
        # Even fully documented declarations need an actual identification proof.
        disposition=TransportDisposition.REVIEW_REQUIRED
    return TransportAudit(disposition,tuple(sorted(set(issues))),
                          tuple(sorted(set(unsupported))),False)
