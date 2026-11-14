"""M29 epistemic-state ledger and dependency uncertainty propagation."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class EpistemicState(str, Enum):
    UNKNOWN="unknown"; INSUFFICIENT="insufficient"; REVIEW_REQUIRED="review_required"
    PROVISIONAL="provisional"; CONDITIONAL="conditional"; WEAKENED="weakened"
    CONFLICTED="conflicted"; STALE="stale"; REVALIDATED="revalidated"
class EvidencePolarity(str, Enum):
    SUPPORT="support"; COUNTER="counter"; QUALIFIER="qualifier"
class EvidenceReview(str, Enum):
    UNREVIEWED="unreviewed"; REVIEWED="reviewed"; DISPUTED="disputed"
class DependencyStrength(str, Enum):
    HARD="hard"; SOFT="soft"
class ConditionState(str, Enum):
    SATISFIED="satisfied"; UNSATISFIED="unsatisfied"; UNKNOWN="unknown"

@dataclass(frozen=True)
class EvidenceItem:
    evidence_id:str; claim_id:str; polarity:EvidencePolarity; review:EvidenceReview
    reviewer_ids:Tuple[str,...]; rationale:str
@dataclass(frozen=True)
class ClaimJudgement:
    claim_id:str; state:EpistemicState; reason:str
    reviewer_ids:Tuple[str,...]=(); condition_refs:Tuple[str,...]=(); revalidation_of:str=""
@dataclass(frozen=True)
class Condition:
    condition_id:str; claim_id:str; state:ConditionState; description:str
@dataclass(frozen=True)
class ClaimDependency:
    dependency_id:str; prerequisite_claim_id:str; dependent_claim_id:str
    strength:DependencyStrength; relation:str
@dataclass(frozen=True)
class StateRecord:
    claim_id:str; local_state:EpistemicState; effective_state:EpistemicState
    reasons:Tuple[str,...]; inherited_from:Tuple[str,...]; semantic_truth_established:bool=False
@dataclass(frozen=True)
class UncertaintyReport:
    valid_graph:bool; records:Tuple[StateRecord,...]; issues:Tuple[str,...]
    propagation_trace:Tuple[Tuple[str,str,str],...]

def _rank(state):
    return {EpistemicState.UNKNOWN:0,EpistemicState.PROVISIONAL:1,
    EpistemicState.REVALIDATED:1,EpistemicState.CONDITIONAL:2,
    EpistemicState.REVIEW_REQUIRED:3,EpistemicState.INSUFFICIENT:4,
    EpistemicState.WEAKENED:5,EpistemicState.CONFLICTED:6,EpistemicState.STALE:7}[state]

def derive_local_state(claim_id,evidence,judgement,conditions=()):
    relevant=[e for e in evidence if e.claim_id==claim_id]
    reviewed=[e for e in relevant if e.review==EvidenceReview.REVIEWED]
    unreviewed=[e for e in relevant if e.review!=EvidenceReview.REVIEWED]
    support=[e for e in reviewed if e.polarity==EvidencePolarity.SUPPORT]
    counter=[e for e in reviewed if e.polarity==EvidencePolarity.COUNTER]
    if judgement is None:
        if not relevant:return EpistemicState.UNKNOWN
        return EpistemicState.REVIEW_REQUIRED if unreviewed else EpistemicState.INSUFFICIENT
    if judgement.claim_id!=claim_id or not isinstance(judgement.state,EpistemicState):
        raise ValueError("judgement mismatch or invalid state")
    if not judgement.reason.strip():raise ValueError("judgement reason is required")
    if judgement.state in (EpistemicState.PROVISIONAL,EpistemicState.CONDITIONAL,
      EpistemicState.WEAKENED,EpistemicState.CONFLICTED,EpistemicState.REVALIDATED) and not judgement.reviewer_ids:
        raise ValueError("adjudicated state requires reviewer_ids")
    if judgement.state==EpistemicState.REVALIDATED and not judgement.revalidation_of.strip():
        raise ValueError("revalidated state requires revalidation_of")
    if support and counter and judgement.state==EpistemicState.PROVISIONAL:
        raise ValueError("unresolved support/counter evidence cannot be PROVISIONAL")
    if unreviewed and judgement.state==EpistemicState.PROVISIONAL:
        raise ValueError("unreviewed evidence requires REVIEW_REQUIRED or explicit adjudication")
    if judgement.state==EpistemicState.CONDITIONAL:
        cmap={c.condition_id:c for c in conditions if c.claim_id==claim_id}
        if not judgement.condition_refs:raise ValueError("conditional judgement requires condition_refs")
        if any(x not in cmap for x in judgement.condition_refs):raise ValueError("unknown condition reference")
        if all(cmap[x].state==ConditionState.SATISFIED for x in judgement.condition_refs):
            raise ValueError("all conditions satisfied; conditional state is not justified")
    if judgement.state==EpistemicState.PROVISIONAL and not support:
        raise ValueError("provisional judgement requires reviewed support evidence")
    if judgement.state==EpistemicState.WEAKENED and not counter:
        raise ValueError("weakened judgement requires reviewed counter-evidence")
    if judgement.state==EpistemicState.CONFLICTED and not (support and counter):
        raise ValueError("conflicted judgement requires reviewed support and counter-evidence")
    return judgement.state

def audit_epistemic_graph(claim_ids,evidence,judgements,conditions,dependencies):
    issues=[]
    if not claim_ids or len(claim_ids)!=len(set(claim_ids)):issues.append("claim_ids_must_be_nonempty_and_unique")
    claim_set=set(claim_ids)
    for cid in claim_ids:
        if not isinstance(cid,str) or not cid.strip():issues.append("empty_claim_id")
    evidence_ids=set()
    for e in evidence:
        if not isinstance(e,EvidenceItem):issues.append("invalid_evidence_item");continue
        if not e.evidence_id.strip() or not e.claim_id.strip() or not e.rationale.strip():issues.append("empty_evidence_field")
        if e.evidence_id in evidence_ids:issues.append("duplicate_evidence_id")
        evidence_ids.add(e.evidence_id)
        if e.claim_id not in claim_set:issues.append("unknown_evidence_claim:"+e.evidence_id)
        if not isinstance(e.polarity,EvidencePolarity) or not isinstance(e.review,EvidenceReview):issues.append("invalid_evidence_state:"+e.evidence_id)
        if e.review==EvidenceReview.REVIEWED and (not e.reviewer_ids or len(e.rationale.strip())<12):issues.append("reviewed_evidence_incomplete:"+e.evidence_id)
        if e.review!=EvidenceReview.REVIEWED and e.reviewer_ids:issues.append("unreviewed_evidence_has_reviewers:"+e.evidence_id)
    jmap={}
    for j in judgements:
        if j.claim_id not in claim_set:issues.append("unknown_judgement_claim:"+j.claim_id)
        if j.claim_id in jmap:issues.append("duplicate_judgement:"+j.claim_id)
        jmap[j.claim_id]=j
    cmap={}
    for c in conditions:
        if c.condition_id in cmap:issues.append("duplicate_condition:"+c.condition_id)
        cmap[c.condition_id]=c
        if c.claim_id not in claim_set or not c.description.strip():issues.append("invalid_condition:"+c.condition_id)
    edge_ids=set(); adjacency={cid:[] for cid in claim_ids}
    for edge in dependencies:
        if edge.dependency_id in edge_ids:issues.append("duplicate_dependency:"+edge.dependency_id)
        edge_ids.add(edge.dependency_id)
        if edge.prerequisite_claim_id not in claim_set or edge.dependent_claim_id not in claim_set:
            issues.append("unknown_dependency_endpoint:"+edge.dependency_id);continue
        if edge.prerequisite_claim_id==edge.dependent_claim_id:issues.append("self_dependency:"+edge.dependency_id)
        if not isinstance(edge.strength,DependencyStrength) or not edge.relation.strip():issues.append("invalid_dependency:"+edge.dependency_id)
        adjacency[edge.prerequisite_claim_id].append(edge)
    visiting=set();visited=set()
    def visit(cid):
        if cid in visiting:return True
        if cid in visited:return False
        visiting.add(cid); cyclic=any(visit(e.dependent_claim_id) for e in adjacency[cid])
        visiting.remove(cid);visited.add(cid);return cyclic
    if any(visit(cid) for cid in claim_ids if cid not in visited):issues.append("dependency_cycle")
    if issues:return UncertaintyReport(False,(),tuple(sorted(set(issues))),())
    local={}
    for cid in claim_ids:
        try:local[cid]=derive_local_state(cid,evidence,jmap.get(cid),conditions)
        except ValueError as exc:issues.append(f"{cid}:{exc}")
    if issues:return UncertaintyReport(False,(),tuple(sorted(set(issues))),())
    effective=dict(local); reasons={cid:[] for cid in claim_ids}; inherited={cid:set() for cid in claim_ids};trace=[]
    indegree={cid:0 for cid in claim_ids}
    for edges in adjacency.values():
        for edge in edges:indegree[edge.dependent_claim_id]+=1
    ready=sorted(cid for cid,d in indegree.items() if d==0)
    while ready:
        source=ready.pop(0)
        for edge in adjacency[source]:
            target=edge.dependent_claim_id; source_state=effective[source]; tj=jmap.get(target)
            if tj and tj.state==EpistemicState.REVALIDATED:
                trace.append((target,"revalidation_barrier",edge.dependency_id))
            elif source_state not in (EpistemicState.PROVISIONAL,EpistemicState.REVALIDATED,EpistemicState.UNKNOWN):
                if edge.strength==DependencyStrength.SOFT:candidate=EpistemicState.REVIEW_REQUIRED
                elif source_state==EpistemicState.STALE:candidate=EpistemicState.STALE
                elif source_state in (EpistemicState.CONFLICTED,EpistemicState.WEAKENED,EpistemicState.CONDITIONAL,EpistemicState.INSUFFICIENT):candidate=source_state
                else:candidate=EpistemicState.INSUFFICIENT
                if _rank(candidate)>_rank(effective[target]):
                    effective[target]=candidate;reasons[target].append(f"dependency:{source}:{source_state.value}:{edge.strength.value}")
                    inherited[target].add(source);trace.append((target,candidate.value,edge.dependency_id))
            indegree[target]-=1
            if indegree[target]==0:ready.append(target);ready.sort()
    records=tuple(StateRecord(cid,local[cid],effective[cid],tuple(reasons[cid]),tuple(sorted(inherited[cid]))) for cid in sorted(claim_ids))
    return UncertaintyReport(True,records,(),tuple(trace))

def adapt_m27_invalidation(invalidation,m27_node_to_claim_id):
    """Explicit mapping: M27 node IDs are never guessed to be M29 claim IDs."""
    mapping=dict(m27_node_to_claim_id)
    if len(mapping)!=len(m27_node_to_claim_id):raise ValueError("duplicate M27 node mapping")
    output=[]
    for node in invalidation.stale_node_ids:
        if node not in mapping:raise ValueError(f"unmapped M27 stale node: {node}")
        output.append((mapping[node],EpistemicState.STALE,f"m27:{node}:stale"))
    for node in invalidation.review_node_ids:
        if node not in mapping:raise ValueError(f"unmapped M27 review node: {node}")
        output.append((mapping[node],EpistemicState.REVIEW_REQUIRED,f"m27:{node}:review"))
    return tuple(sorted(output))
