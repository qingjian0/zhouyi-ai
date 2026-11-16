"""M37 active experiment design for competing yixiang mechanism hypotheses.
Ranks declared candidate experiments by conservative pairwise prediction separation.
Not Bayesian expected information gain, causal identification, or an executor.
"""
from dataclasses import dataclass
from enum import Enum
from math import sqrt, isfinite
class CandidateStatus(str, Enum):
    PROPOSED="proposed"; FEASIBLE="feasible"; BLOCKED="blocked"
class SafetyReview(str, Enum):
    PENDING="pending"; APPROVED="approved"; REJECTED="rejected"
class DesignDisposition(str, Enum):
    BLOCKED="blocked"; NO_DISCRIMINATING_DESIGN="no_discriminating_design"
    CONDITIONAL_RANKING="conditional_ranking"; REVIEW_REQUIRED="review_required"
@dataclass(frozen=True)
class MechanismPrediction:
    hypothesis_id:str; outcome_mean:float; outcome_sd:float; prediction_ref:str
@dataclass(frozen=True)
class ExperimentCandidate:
    experiment_id:str; intervention_target:str; intervention_value:str; context:str
    predictions:tuple; cost:float; risk_level:float; max_acceptable_risk:float
    feasibility:CandidateStatus; safety_review:SafetyReview; design_ref:str
    measurement_ref:str; source_family:str; selection_split:str; validation_split:str
    limitation_refs:tuple=()
@dataclass(frozen=True)
class RankedExperiment:
    experiment_id:str; discrimination_score:float; pairwise_separation:float
    cost_adjusted_score:float; covered_hypotheses:tuple
@dataclass(frozen=True)
class ExperimentDesignAudit:
    disposition:DesignDisposition; ranked:tuple; issues:tuple; warnings:tuple
    selected_experiment_id:str=""; causal_truth_established:bool=False
def _separation(a,b):
    return abs(a.outcome_mean-b.outcome_mean)/sqrt(a.outcome_sd**2+b.outcome_sd**2+1e-12)
def rank_experiments(hypothesis_ids,candidates,*,max_cost,max_risk):
    hs=tuple(sorted(set(hypothesis_ids))); candidates=tuple(candidates)
    issues=[]; warnings=[]; ranked=[]
    if len(hs)<2: issues.append("at_least_two_competing_hypotheses_required")
    if max_cost<0 or max_risk<0: issues.append("invalid_global_budget_or_risk_limit")
    ids=[c.experiment_id for c in candidates]
    if len(ids)!=len(set(ids)): issues.append("duplicate_experiment_id")
    for c in candidates:
        if not all((c.experiment_id,c.intervention_target,c.context,c.design_ref,c.measurement_ref,c.source_family,c.selection_split,c.validation_split)):
            issues.append("incomplete_candidate:"+c.experiment_id); continue
        if c.selection_split==c.validation_split: issues.append("selection_validation_split_overlap:"+c.experiment_id)
        if any(not isfinite(v) or v<0 for v in (c.cost,c.risk_level,c.max_acceptable_risk)):
            issues.append("negative_cost_or_risk:"+c.experiment_id)
            continue
        pm={p.hypothesis_id:p for p in c.predictions}
        if len(pm)!=len(c.predictions): issues.append("duplicate_prediction:"+c.experiment_id)
        missing=sorted(set(hs)-set(pm)); extra=sorted(set(pm)-set(hs))
        if missing: issues.append("missing_hypothesis_predictions:"+c.experiment_id+":"+",".join(missing))
        if extra: issues.append("unknown_hypothesis_predictions:"+c.experiment_id+":"+",".join(extra))
        invalid=[p for p in c.predictions if p.outcome_sd<0 or not p.prediction_ref]
        for p in invalid: issues.append("invalid_prediction:"+c.experiment_id+":"+p.hypothesis_id)
        if c.feasibility==CandidateStatus.BLOCKED: warnings.append("candidate_declared_blocked:"+c.experiment_id)
        if c.safety_review==SafetyReview.REJECTED: warnings.append("safety_rejected:"+c.experiment_id)
        elif c.safety_review!=SafetyReview.APPROVED: warnings.append("safety_review_pending:"+c.experiment_id)
        if c.risk_level>c.max_acceptable_risk: warnings.append("candidate_exceeds_own_risk_limit:"+c.experiment_id)
        if c.cost>max_cost: warnings.append("candidate_exceeds_budget:"+c.experiment_id)
        if c.risk_level>max_risk: warnings.append("candidate_exceeds_global_risk_limit:"+c.experiment_id)
        if missing or extra or invalid: continue
        if c.feasibility!=CandidateStatus.FEASIBLE or c.safety_review!=SafetyReview.APPROVED: continue
        if c.risk_level>c.max_acceptable_risk or c.risk_level>max_risk or c.cost>max_cost: continue
        pairs=[_separation(pm[a],pm[b]) for i,a in enumerate(hs) for b in hs[i+1:]]
        worst=min(pairs) if pairs else 0.0; mean=sum(pairs)/len(pairs) if pairs else 0.0
        ranked.append(RankedExperiment(c.experiment_id,worst,mean,worst/(1.0+c.cost),hs))
    ranked.sort(key=lambda x:(-x.discrimination_score,-x.cost_adjusted_score,x.experiment_id))
    if issues: disposition=DesignDisposition.BLOCKED
    elif not ranked or ranked[0].discrimination_score<=0: disposition=DesignDisposition.NO_DISCRIMINATING_DESIGN
    elif warnings: disposition=DesignDisposition.CONDITIONAL_RANKING
    else: disposition=DesignDisposition.REVIEW_REQUIRED
    selected=ranked[0].experiment_id if ranked and not issues else ""
    if selected:
        warnings.extend(("ranking_is_not_expected_information_gain_or_causal_identification","human_review_required_before_experiment_execution"))
    return ExperimentDesignAudit(disposition,tuple(ranked),tuple(sorted(set(issues))),tuple(sorted(set(warnings))),selected,False)
