"""M47 common metrics and transparent baselines for SCM benchmark episodes."""
from dataclasses import dataclass
from math import sqrt, isfinite
import random

@dataclass(frozen=True)
class BaselineOutput:
    baseline_id: str
    predicted_parents: tuple
    selected_interventions: tuple
    samples_used: int
    total_cost: float
    committed: bool
    evidence_sufficient: bool
    trace_valid: bool = True
    tool_errors: int = 0

@dataclass(frozen=True)
class EpisodeScore:
    baseline_id: str
    precision: float
    recall: float
    f1: float
    structural_hamming_distance: int
    intervention_coverage: float
    budget_utilization: float
    premature_commit: bool
    budget_violation: bool
    trace_valid: bool
    tool_errors: int

def _safe_ratio(a,b):
    return a/b if b else 0.0

def evaluate_episode(truth_parents,candidate_parents,output,budget,min_interventions_for_commit=1):
    truth=set(truth_parents); pred=set(output.predicted_parents)
    if not truth and not pred: precision=recall=f1=1.0
    else:
        tp=len(truth&pred); precision=_safe_ratio(tp,len(pred)); recall=_safe_ratio(tp,len(truth))
        f1=_safe_ratio(2*precision*recall,precision+recall)
    shd=len(truth-pred)+len(pred-truth)
    selected=set(output.selected_interventions)
    coverage=_safe_ratio(len(truth&selected),len(truth))
    utilization=_safe_ratio(output.total_cost,budget) if budget>0 else (0.0 if output.total_cost==0 else 1.0)
    premature=bool(output.committed and (not output.evidence_sufficient or len(selected)<min_interventions_for_commit))
    return EpisodeScore(output.baseline_id,precision,recall,f1,shd,coverage,utilization,premature,
                        output.total_cost>budget or output.samples_used<0,output.trace_valid,output.tool_errors)

def random_intervention_baseline(candidates,k,seed=0):
    values=tuple(dict.fromkeys(candidates))
    rng=random.Random(seed); selected=tuple(rng.sample(values,min(max(k,0),len(values))))
    return selected

def _correlation(x,y):
    n=len(x)
    if n!=len(y) or n<2: return 0.0
    mx=sum(x)/n; my=sum(y)/n
    vx=sum((v-mx)**2 for v in x); vy=sum((v-my)**2 for v in y)
    if vx<=0 or vy<=0: return 0.0
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/sqrt(vx*vy)

def correlation_screen_baseline(rows,target,candidates,k):
    if len(rows)<2: return tuple()
    ranked=[]
    for name in dict.fromkeys(candidates):
        if name==target or any(name not in row or target not in row for row in rows): continue
        score=abs(_correlation([float(r[name]) for r in rows],[float(r[target]) for r in rows]))
        ranked.append((score,name))
    return tuple(name for score,name in sorted(ranked,key=lambda x:(-x[0],x[1]))[:max(0,k)])

def oracle_diagnostic_baseline(truth_parents):
    """Evaluator-only upper bound; never expose to a live agent."""
    return tuple(sorted(set(truth_parents)))

def aggregate_scores(scores):
    scores=tuple(scores)
    if not scores: raise ValueError("scores_required")
    fields=("precision","recall","f1","structural_hamming_distance","intervention_coverage",
            "budget_utilization","premature_commit","budget_violation","tool_errors")
    result={"episodes":len(scores)}
    for field in fields:
        values=[float(getattr(s,field)) for s in scores]
        result["mean_"+field]=sum(values)/len(values)
    result["trace_valid_rate"]=sum(bool(s.trace_valid) for s in scores)/len(scores)
    return result
