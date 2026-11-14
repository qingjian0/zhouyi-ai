"""M39 bounded search for non-myopic experiment sequences.

This version searches fixed, open-loop action sequences. It does not yet search
outcome-contingent policy trees; M38 remains the evaluator for supplied trees.
"""
from dataclasses import dataclass
from enum import Enum
from math import isfinite, log

class SearchDisposition(str, Enum):
    BLOCKED="blocked"
    CANDIDATES_FOUND="candidates_found"
    NO_FEASIBLE_SEQUENCE="no_feasible_sequence"

@dataclass(frozen=True)
class Prior:
    hypothesis_id: str
    probability: float

@dataclass(frozen=True)
class Likelihood:
    action_id: str
    hypothesis_id: str
    outcome: str
    probability: float

@dataclass(frozen=True)
class ModelScenario:
    scenario_id: str
    priors: tuple
    likelihoods: tuple
    provenance_ref: str
    calibrated: bool

@dataclass(frozen=True)
class Action:
    action_id: str
    cost: float
    risk: float
    max_risk: float
    safety_approved: bool
    feasible: bool
    design_ref: str
    measurement_ref: str
    selection_split: str
    validation_split: str

@dataclass(frozen=True)
class SequenceScore:
    action_ids: tuple
    robust_eig: float
    scenario_eigs: tuple
    total_cost: float
    total_risk: float
    utility: float

@dataclass(frozen=True)
class SearchResult:
    disposition: SearchDisposition
    ranked_sequences: tuple
    greedy_sequence: tuple
    greedy_utility: float
    expanded_states: int
    issues: tuple
    warnings: tuple
    execution_authorized: bool = False
    causal_truth_established: bool = False

def _entropy(p):
    return -sum(x*log(x,2) for x in p if x>0)

def _valid_scenario(s, action_ids):
    if not s.scenario_id or not s.provenance_ref or not s.calibrated: return False
    hs=[p.hypothesis_id for p in s.priors]
    if len(hs)<2 or len(set(hs))!=len(hs): return False
    if any(not h or not isfinite(p.probability) or p.probability<0 for h,p in ((p.hypothesis_id,p) for p in s.priors)): return False
    if abs(sum(p.probability for p in s.priors)-1)>1e-8: return False
    grouped={}; seen=set()
    for l in s.likelihoods:
        if l.action_id not in action_ids or l.hypothesis_id not in hs or not l.outcome or not isfinite(l.probability) or not 0<=l.probability<=1: return False
        key=(l.action_id,l.hypothesis_id,l.outcome)
        if key in seen: return False
        seen.add(key); grouped.setdefault((l.action_id,l.hypothesis_id),[]).append(l.probability)
    return all((a,h) in grouped and abs(sum(grouped[(a,h)])-1)<=1e-8 for a in action_ids for h in hs)

def _sequence_eig(sequence, scenario, max_outcome_paths):
    prior={p.hypothesis_id:p.probability for p in scenario.priors}
    likelihood={(l.action_id,l.hypothesis_id,l.outcome):l.probability for l in scenario.likelihoods}
    initial=_entropy(tuple(prior.values()))
    states=[(prior,1.0)]
    path_count=1
    for aid in sequence:
        outcomes=sorted({l.outcome for l in scenario.likelihoods if l.action_id==aid})
        path_count*=len(outcomes)
        if path_count>max_outcome_paths: return None
        next_states=[]
        for belief,path_prob in states:
            for outcome in outcomes:
                weighted={h:belief[h]*likelihood[(aid,h,outcome)] for h in belief}
                marginal=sum(weighted.values())
                if marginal>0:
                    posterior={h:v/marginal for h,v in weighted.items()}
                    next_states.append((posterior,path_prob*marginal))
        states=next_states
    terminal=sum(prob*_entropy(tuple(belief.values())) for belief,prob in states)
    return initial-terminal

def _score(sequence, actions, scenarios, cost_weight, risk_weight, max_outcome_paths):
    amap={a.action_id:a for a in actions}
    cost=sum(amap[x].cost for x in sequence)
    risk=sum(amap[x].risk for x in sequence)
    eigs=tuple((s.scenario_id,_sequence_eig(sequence,s,max_outcome_paths)) for s in scenarios)
    if any(v is None for _,v in eigs): return None
    robust=min(v for _,v in eigs)
    return SequenceScore(tuple(sequence),robust,eigs,cost,risk,robust-cost_weight*cost-risk_weight*risk)

def search_sequences(actions, scenarios, horizon, beam_width, max_total_cost,
                     max_total_risk, cost_weight=0.0, risk_weight=0.0, max_outcome_paths=4096):
    actions=tuple(actions); scenarios=tuple(scenarios); issues=[]; warnings=[]
    if horizon<1 or beam_width<1 or max_outcome_paths<1 or not all(isfinite(x) and x>=0 for x in (max_total_cost,max_total_risk,cost_weight,risk_weight)):
        issues.append("invalid_search_limits")
    ids=[a.action_id for a in actions]
    if len(ids)!=len(set(ids)): issues.append("duplicate_action_id")
    if not actions: issues.append("no_actions")
    if not scenarios: issues.append("no_model_scenarios")
    for a in actions:
        if not a.action_id or not a.design_ref or not a.measurement_ref or not a.selection_split or not a.validation_split:
            issues.append("incomplete_action:"+a.action_id)
        if a.selection_split==a.validation_split: issues.append("selection_validation_overlap:"+a.action_id)
        if not all(isfinite(x) and x>=0 for x in (a.cost,a.risk,a.max_risk)): issues.append("invalid_action_cost_or_risk:"+a.action_id)
        if a.risk>a.max_risk: issues.append("action_risk_limit_exceeded:"+a.action_id)
        if not a.safety_approved or not a.feasible: warnings.append("action_not_eligible:"+a.action_id)
    eligible=[a for a in actions if a.safety_approved and a.feasible and a.risk<=a.max_risk]
    for s in scenarios:
        if not _valid_scenario(s,set(ids)):
            issues.append("invalid_or_uncalibrated_scenario:"+s.scenario_id)
    if issues:
        return SearchResult(SearchDisposition.BLOCKED,(),(),0.0,0,tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    if not eligible:
        return SearchResult(SearchDisposition.NO_FEASIBLE_SEQUENCE,(),(),0.0,0,(),tuple(sorted(set(warnings))))
    beam=[tuple()]; seen=set(); ranked={}; expanded=0; capped=False;
    for depth in range(1,min(horizon,len(eligible))+1):
        candidates=[]
        for prefix in beam:
            for a in eligible:
                if a.action_id in prefix: continue
                seq=prefix+(a.action_id,)
                if seq in seen: continue
                seen.add(seq); expanded+=1
                cost=sum(next(x.cost for x in eligible if x.action_id==aid) for aid in seq)
                risk=sum(next(x.risk for x in eligible if x.action_id==aid) for aid in seq)
                if cost>max_total_cost+1e-9 or risk>max_total_risk+1e-9: continue
                score=_score(seq,eligible,scenarios,cost_weight,risk_weight,max_outcome_paths)
                if score is None:
                    capped=True
                    continue
                ranked[seq]=score; candidates.append(score)
        if not candidates: break
        candidates.sort(key=lambda x:(-x.utility,x.total_cost,x.total_risk,x.action_ids))
        beam=[x.action_ids for x in candidates[:beam_width]]
    best=tuple(sorted(ranked.values(),key=lambda x:(-x.utility,x.total_cost,x.total_risk,x.action_ids)))
    # True one-step greedy baseline: maximize incremental robust-EIG utility at each step.
    greedy=tuple(); greedy_utility=0.0; current_eig=0.0
    for _ in range(min(horizon,len(eligible))):
        extensions=[]
        for a in eligible:
            if a.action_id in greedy: continue
            seq=greedy+(a.action_id,)
            score=_score(seq,eligible,scenarios,cost_weight,risk_weight,max_outcome_paths)
            if score is not None and score.total_cost<=max_total_cost+1e-9 and score.total_risk<=max_total_risk+1e-9:
                marginal=(score.robust_eig-current_eig)-cost_weight*a.cost-risk_weight*a.risk
                extensions.append((marginal,score))
        if not extensions: break
        extensions.sort(key=lambda x:(-x[0],x[1].action_ids))
        marginal,chosen=extensions[0]
        if marginal<=0: break
        greedy=chosen.action_ids; current_eig=chosen.robust_eig; greedy_utility=chosen.utility
    if capped: warnings.append("some_sequences_skipped_by_outcome_path_cap")
    warnings.extend(("open_loop_sequences_only_no_outcome_contingent_branching","bounded_beam_search_is_not_global_optimality_proof","robustness_only_over_declared_model_scenarios","validation_data_must_remain_unseen_until_search_and_policy_freeze","search_ranking_is_not_execution_authorization"))
    return SearchResult(SearchDisposition.CANDIDATES_FOUND if best else SearchDisposition.NO_FEASIBLE_SEQUENCE,
                        best,greedy,greedy_utility,expanded,(),tuple(sorted(set(warnings))),False,False)
