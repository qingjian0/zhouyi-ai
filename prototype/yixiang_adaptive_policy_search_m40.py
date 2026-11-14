"""M40 finite-horizon outcome-contingent experiment policy search.

Uses a shared observable-history policy and maximin expected terminal reward
across declared model scenarios. This is a small exact tree search with a hard
node budget, not a general POMDP solver.
"""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class Prior:
    hypothesis: str
    probability: float

@dataclass(frozen=True)
class Likelihood:
    action: str
    hypothesis: str
    outcome: str
    probability: float

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    priors: tuple
    likelihoods: tuple
    provenance: str
    calibrated: bool = True

@dataclass(frozen=True)
class Action:
    action_id: str
    cost: float
    risk: float
    risk_limit: float
    approved: bool
    feasible: bool
    design_ref: str
    measurement_ref: str

@dataclass(frozen=True)
class PolicyNode:
    action_id: str | None
    branches: tuple
    terminal_values: tuple
    depth: int

@dataclass(frozen=True)
class SearchResult:
    root: PolicyNode | None
    scenario_values: tuple
    robust_value: float
    expanded_nodes: int
    disposition: str
    issues: tuple
    warnings: tuple
    execution_authorized: bool = False
    causal_truth_established: bool = False

def _entropy_reward(belief):
    # Terminal utility: probability of the most likely mechanism.
    return max(belief.values()) if belief else 0.0

def _update(belief, action, outcome, likelihood):
    weighted={h:p*likelihood.get((action,h,outcome),0.0) for h,p in belief.items()}
    z=sum(weighted.values())
    if z<=0: return None,0.0
    return {h:v/z for h,v in weighted.items()},z

def search_policy(actions, scenarios, horizon=3, max_nodes=5000,
                  cost_weight=0.01, risk_weight=0.01, max_total_cost=float("inf"),
                  max_total_risk=float("inf")):
    actions=tuple(actions); scenarios=tuple(scenarios); issues=[]; warnings=[]
    if horizon<0 or max_nodes<1 or any(not isfinite(x) or x<0 for x in (cost_weight,risk_weight)) or max_total_cost<0 or max_total_risk<0 or max_total_cost!=max_total_cost or max_total_risk!=max_total_risk:
        issues.append("invalid_search_limits")
    if not actions: issues.append("no_actions")
    if not scenarios: issues.append("no_scenarios")
    ids=[a.action_id for a in actions]
    if len(ids)!=len(set(ids)): issues.append("duplicate_action_id")
    for a in actions:
        if (not a.action_id or not a.design_ref or not a.measurement_ref or
            not all(isfinite(x) and x>=0 for x in (a.cost,a.risk,a.risk_limit))):
            issues.append("invalid_action:"+a.action_id)
        if a.risk>a.risk_limit: issues.append("action_risk_limit:"+a.action_id)
    eligible=tuple(a for a in actions if a.approved and a.feasible)
    for s in scenarios:
        hs=[p.hypothesis for p in s.priors]
        if not s.provenance or not s.calibrated or len(hs)<2 or len(set(hs))!=len(hs):
            issues.append("invalid_scenario:"+s.scenario_id); continue
        if any(not isfinite(p.probability) or p.probability<0 for p in s.priors) or abs(sum(p.probability for p in s.priors)-1)>1e-8:
            issues.append("invalid_prior:"+s.scenario_id)
        for a in eligible:
            for h in hs:
                ls=[l for l in s.likelihoods if l.action==a.action_id and l.hypothesis==h]
                if not ls or any(not isfinite(l.probability) or not 0<=l.probability<=1 for l in ls) or abs(sum(l.probability for l in ls)-1)>1e-8:
                    issues.append("invalid_likelihood:"+s.scenario_id+":"+a.action_id+":"+h)
    if issues:
        return SearchResult(None,(),0.0,0,"blocked",tuple(sorted(set(issues))),())
    if len(eligible)!=len(actions): warnings.append("unapproved_or_infeasible_actions_excluded")
    if not eligible:
        return SearchResult(None,(),0.0,0,"no_feasible_actions",(),tuple(warnings))
    maps=tuple({(l.action,l.hypothesis,l.outcome):l.probability for l in s.likelihoods} for s in scenarios)
    beliefs=tuple({p.hypothesis:p.probability for p in s.priors} for s in scenarios)
    expanded=0; capped=False
    def solve(bs, depth, used, spent_cost, spent_risk):
        nonlocal expanded,capped
        stop_values=tuple(_entropy_reward(b or {}) for b in bs)
        stop_node=PolicyNode(None,(),stop_values,depth)
        active_indices=[i for i,b in enumerate(bs) if b is not None]
        best_node=stop_node; best_values=stop_values
        best_key=min(stop_values[i] for i in active_indices) if active_indices else 0.0
        if depth>=horizon: return best_node,best_values
        candidates=[]
        for a in eligible:
            if a.action_id in used or spent_cost+a.cost>max_total_cost+1e-9 or spent_risk+a.risk>max_total_risk+1e-9: continue
            expanded+=1
            if expanded>max_nodes:
                capped=True; break
            outcomes=sorted({l.outcome for s in scenarios for l in s.likelihoods if l.action==a.action_id})
            branch_nodes=[]; branch_values={i:[] for i in range(len(scenarios))}
            for outcome in outcomes:
                next_bs=[]; probs=[]
                for i,b in enumerate(bs):
                    if b is None: next_bs.append(None); probs.append(0.0)
                    else:
                        nb,p=_update(b,a.action_id,outcome,maps[i]); next_bs.append(nb); probs.append(p)
                child,child_vals=solve(tuple(next_bs),depth+1,used|{a.action_id},spent_cost+a.cost,spent_risk+a.risk)
                branch_nodes.append((outcome,child))
                for i,p in enumerate(probs): branch_values[i].append(p*child_vals[i])
            values=tuple(sum(branch_values[i])-cost_weight*a.cost-risk_weight*a.risk for i in range(len(scenarios)))
            active_key=min(values[i] for i in active_indices) if active_indices else 0.0
            candidates.append((active_key,PolicyNode(a.action_id,tuple(branch_nodes),values,depth),values))
            if capped: break
        if candidates:
            candidates.sort(key=lambda x:(-x[0],x[1].action_id or ""))
            if candidates[0][0]>best_key:
                _,best_node,best_values=candidates[0]
        return best_node,best_values
    root,values=solve(beliefs,0,frozenset(),0.0,0.0)
    if capped: warnings.append("node_budget_exhausted_search_is_incomplete")
    warnings.extend(("shared_policy_uses_observable_outcomes_not_hidden_scenario_identity",
                     "finite_horizon_tree_search_not_general_pomdp_solver",
                     "terminal_reward_is_maximum_mechanism_posterior_not_causal_truth",
                     "no_experiment_execution_authorized"))
    return SearchResult(root,tuple((s.scenario_id,v) for s,v in zip(scenarios,values)),min(values),expanded,
                        "candidate_policy" if root.action_id else "stop_policy",(),tuple(sorted(set(warnings))))
