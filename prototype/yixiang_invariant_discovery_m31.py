"""M31 invariant discovery and falsification audit; no semantic truth certification."""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class InvariantLevel(str, Enum):
    FEATURE="feature"
    RELATION="relation"
    MECHANISM="mechanism"
    SYSTEM="system"

class ObservationResult(str, Enum):
    PRESERVED="preserved"
    WEAKENED="weakened"
    REVERSED="reversed"
    FAILED="failed"
    UNKNOWN="unknown"

class TestKind(str, Enum):
    CONFIRMATORY="confirmatory"
    FALSIFICATION="falsification"
    BOUNDARY="boundary"
    REPLICATION="replication"

class ReviewState(str, Enum):
    UNREVIEWED="unreviewed"
    REVIEWED="reviewed"
    DISPUTED="disputed"

class ClaimState(str, Enum):
    CANDIDATE="candidate"
    BOUNDED="bounded"
    REFUTED="refuted"
    INCONCLUSIVE="inconclusive"
    REPLICATED="replicated"

@dataclass(frozen=True)
class Context:
    context_id:str
    family_id:str
    version:str
    task:str
    environment:str
    subject:str
    scope:str

@dataclass(frozen=True)
class InvariantCandidate:
    candidate_id:str
    level:InvariantLevel
    operational_definition:str
    predicted_observable:str
    expected_relation:str
    scope:str
    boundary_conditions:Tuple[str,...]
    excluded_conditions:Tuple[str,...]
    preregistration_ref:str
    reviewer_ids:Tuple[str,...]=()

@dataclass(frozen=True)
class Observation:
    observation_id:str
    candidate_id:str
    context_id:str
    object_id:str
    result:ObservationResult
    evidence_refs:Tuple[str,...]
    method:str
    reviewed:ReviewState

@dataclass(frozen=True)
class FalsificationTest:
    test_id:str
    candidate_id:str
    kind:TestKind
    target_context_ids:Tuple[str,...]
    perturbation:str
    predicted_failure_condition:str
    outcome:str
    evidence_refs:Tuple[str,...]
    reviewer_ids:Tuple[str,...]=()

@dataclass(frozen=True)
class Counterexample:
    counterexample_id:str
    candidate_id:str
    context_id:str
    object_id:str
    description:str
    evidence_refs:Tuple[str,...]
    review_state:ReviewState
    resolved_by:str=""

@dataclass(frozen=True)
class Evidence:
    evidence_id:str
    source_family_id:str
    context_id:str
    method:str
    reviewed:bool

@dataclass(frozen=True)
class Evaluation:
    evaluation_id:str
    train_object_ids:Tuple[str,...]
    test_object_ids:Tuple[str,...]
    train_context_families:Tuple[str,...]
    test_context_families:Tuple[str,...]
    holdout_context_ids:Tuple[str,...]
    baselines:Tuple[str,...]
    metrics:Tuple[str,...]
    results_ref:str
    sample_size:int
    confidence_interval_method:str
    limitations:Tuple[str,...]

@dataclass(frozen=True)
class AuditReport:
    valid:bool
    issues:Tuple[str,...]
    candidate_states:Tuple[Tuple[str,str],...]
    falsification_coverage:Tuple[Tuple[str,int],...]
    semantic_truth_established:bool=False

def audit_invariant_discovery(contexts,candidates,evidence,observations,tests,counterexamples,evaluations=()):
    issues=[]
    cmap={x.context_id:x for x in contexts}
    if len(cmap)!=len(contexts): issues.append("duplicate_context_id")
    if any(not all((x.context_id,x.family_id,x.version,x.task,x.environment,x.subject,x.scope)) for x in contexts):
        issues.append("incomplete_context")
    cand={x.candidate_id:x for x in candidates}
    if len(cand)!=len(candidates): issues.append("duplicate_candidate_id")
    for c in candidates:
        if not all((c.candidate_id,c.operational_definition.strip(),c.predicted_observable.strip(),
                    c.expected_relation.strip(),c.scope.strip(),c.preregistration_ref.strip())):
            issues.append("incomplete_candidate:"+c.candidate_id)
        if not c.boundary_conditions:
            issues.append("candidate_requires_explicit_boundary_conditions:"+c.candidate_id)
    emap={x.evidence_id:x for x in evidence}
    if len(emap)!=len(evidence): issues.append("duplicate_evidence_id")
    for e in evidence:
        if e.context_id not in cmap or not e.source_family_id or not e.method.strip():
            issues.append("invalid_evidence:"+e.evidence_id)
    obs_ids=[x.observation_id for x in observations]
    if len(obs_ids)!=len(set(obs_ids)): issues.append("duplicate_observation_id")
    valid_obs={}
    for o in observations:
        if o.candidate_id not in cand:
            issues.append("unknown_observation_candidate:"+o.observation_id); continue
        if o.context_id not in cmap:
            issues.append("unknown_observation_context:"+o.observation_id); continue
        if not o.object_id or not o.method.strip() or not o.evidence_refs:
            issues.append("incomplete_observation:"+o.observation_id)
        refs=[emap[r] for r in o.evidence_refs if r in emap]
        if len(refs)!=len(o.evidence_refs):
            issues.append("unknown_observation_evidence:"+o.observation_id)
        elif any(e.context_id!=o.context_id for e in refs):
            issues.append("observation_evidence_context_mismatch:"+o.observation_id)
        valid_obs.setdefault(o.candidate_id,[]).append(o)
    test_ids=[x.test_id for x in tests]
    if len(test_ids)!=len(set(test_ids)): issues.append("duplicate_test_id")
    coverage={cid:0 for cid in cand}
    for t in tests:
        if t.candidate_id not in cand:
            issues.append("unknown_test_candidate:"+t.test_id); continue
        if not t.target_context_ids or any(x not in cmap for x in t.target_context_ids):
            issues.append("invalid_test_contexts:"+t.test_id)
        if not t.perturbation.strip() or not t.predicted_failure_condition.strip() or not t.outcome.strip() or not t.evidence_refs:
            issues.append("incomplete_falsification_test:"+t.test_id)
        refs=[emap[r] for r in t.evidence_refs if r in emap]
        if len(refs)!=len(t.evidence_refs):
            issues.append("unknown_test_evidence:"+t.test_id)
        elif any(e.context_id not in t.target_context_ids for e in refs):
            issues.append("test_evidence_context_mismatch:"+t.test_id)
        if t.kind in (TestKind.FALSIFICATION,TestKind.BOUNDARY):
            coverage[t.candidate_id]+=1
        if t.kind in (TestKind.FALSIFICATION,TestKind.BOUNDARY) and not t.reviewer_ids:
            issues.append("adversarial_test_requires_reviewers:"+t.test_id)
    cex_ids=[x.counterexample_id for x in counterexamples]
    if len(cex_ids)!=len(set(cex_ids)): issues.append("duplicate_counterexample_id")
    cex_by={}
    for x in counterexamples:
        if x.candidate_id not in cand or x.context_id not in cmap:
            issues.append("invalid_counterexample_endpoint:"+x.counterexample_id)
        if not x.description.strip() or not x.evidence_refs:
            issues.append("incomplete_counterexample:"+x.counterexample_id)
        refs=[emap[r] for r in x.evidence_refs if r in emap]
        if len(refs)!=len(x.evidence_refs) or any(e.context_id!=x.context_id for e in refs):
            issues.append("counterexample_evidence_mismatch:"+x.counterexample_id)
        cex_by.setdefault(x.candidate_id,[]).append(x)
    states=[]
    for cid,c in cand.items():
        obs=valid_obs.get(cid,[])
        contexts_seen={o.context_id for o in obs}
        if len(contexts_seen)<2:
            state=ClaimState.CANDIDATE
        elif any(o.result in (ObservationResult.REVERSED,ObservationResult.FAILED) and o.reviewed==ReviewState.REVIEWED for o in obs):
            state=ClaimState.REFUTED
        elif any(x.review_state==ReviewState.REVIEWED and not x.resolved_by for x in cex_by.get(cid,[])):
            state=ClaimState.REFUTED
        elif coverage.get(cid,0)==0:
            state=ClaimState.INCONCLUSIVE
        elif any(o.reviewed!=ReviewState.REVIEWED for o in obs):
            state=ClaimState.INCONCLUSIVE
        elif c.reviewer_ids and all(x.review_state==ReviewState.REVIEWED for x in cex_by.get(cid,[])):
            state=ClaimState.BOUNDED
        else:
            state=ClaimState.INCONCLUSIVE
        if state in (ClaimState.BOUNDED,ClaimState.REPLICATED) and not c.reviewer_ids:
            issues.append("bounded_claim_requires_reviewers:"+cid)
        states.append((cid,state.value))
    for ev in evaluations:
        if set(ev.train_object_ids)&set(ev.test_object_ids): issues.append("object_leakage:"+ev.evaluation_id)
        if set(ev.train_context_families)&set(ev.test_context_families): issues.append("context_family_leakage:"+ev.evaluation_id)
        if not ev.holdout_context_ids or set(ev.holdout_context_ids)&{x for x in ev.train_context_families}:
            issues.append("invalid_holdout_contexts:"+ev.evaluation_id)
        required={"feature_similarity","classification","structural_relation"}
        if not required.issubset(set(ev.baselines)): issues.append("missing_baselines:"+ev.evaluation_id)
        if not ev.metrics or not ev.results_ref or ev.sample_size<=0 or not ev.confidence_interval_method:
            issues.append("incomplete_evaluation_record:"+ev.evaluation_id)
        if not ev.limitations: issues.append("evaluation_limitations_required:"+ev.evaluation_id)
    return AuditReport(not issues,tuple(sorted(set(issues))),tuple(sorted(states)),tuple(sorted(coverage.items())),False)
