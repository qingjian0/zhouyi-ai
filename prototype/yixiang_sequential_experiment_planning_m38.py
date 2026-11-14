"""M38 sequential experiment policy audit.

Evaluates an explicitly supplied finite decision tree under declared, normalized
mechanism priors and calibrated outcome likelihoods. It does not discover models,
search policies, execute interventions, or certify causal truth.
"""
from dataclasses import dataclass
from enum import Enum
from math import isfinite, log

class Review(str, Enum):
    PENDING="pending"; APPROVED="approved"; REJECTED="rejected"

class Disposition(str, Enum):
    BLOCKED="blocked"; INSUFFICIENT_MODEL="insufficient_model"
    ROBUST_POLICY_REVIEW="robust_policy_review"; FRAGILE_POLICY="fragile_policy"
    NO_INFORMATION_GAIN="no_information_gain"

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
class ExperimentAction:
    action_id: str
    cost: float
    risk: float
    max_risk: float
    safety_review: Review
    feasible: bool
    design_ref: str
    measurement_ref: str
    selection_split: str
    validation_split: str

@dataclass(frozen=True)
class OutcomeBranch:
    outcome: str
    next_node_id: str = ""
    stop: bool = False

@dataclass(frozen=True)
class PlanNode:
    node_id: str
    action_id: str
    branches: tuple

@dataclass(frozen=True)
class SequentialPolicy:
    policy_id: str
    root_node_id: str
    nodes: tuple
    max_steps: int
    max_total_cost: float
    max_total_risk: float
    min_robust_eig: float = 0.0

@dataclass(frozen=True)
class ScenarioScore:
    scenario_id: str
    expected_information_gain: float
    expected_cost: float
    worst_path_risk: float
    terminal_paths: int

@dataclass(frozen=True)
class PolicyAudit:
    disposition: Disposition
    scenario_scores: tuple
    robust_min_eig: float
    issues: tuple
    warnings: tuple
    execution_authorized: bool = False
    causal_truth_established: bool = False

def _entropy(p):
    return -sum(x * log(x, 2) for x in p if x > 0)

def _unique(items, key):
    values=[getattr(x,key) for x in items]
    return len(values)==len(set(values))

def _scenario_valid(s, action_ids):
    if not s.scenario_id or not s.provenance_ref or not s.calibrated:
        return False
    hs=[p.hypothesis_id for p in s.priors]
    if len(hs)<2 or len(hs)!=len(set(hs)): return False
    if any(not h or not isfinite(p.probability) or p.probability<0 for p in s.priors): return False
    if abs(sum(p.probability for p in s.priors)-1.0)>1e-8: return False
    outcomes={}; seen=set()
    for l in s.likelihoods:
        if l.action_id not in action_ids or l.hypothesis_id not in hs or not l.outcome or not isfinite(l.probability) or not (0<=l.probability<=1): return False
        key=(l.action_id,l.hypothesis_id,l.outcome)
        if key in seen: return False
        seen.add(key); outcomes.setdefault((l.action_id,l.hypothesis_id),[]).append(l.probability)
    return all((a,h) in outcomes and abs(sum(outcomes[(a,h)])-1.0)<=1e-8
               for a in action_ids for h in hs)

def audit_policy(policy, actions, scenarios):
    issues=[]; warnings=[]; scores=[]
    actions=tuple(actions); scenarios=tuple(scenarios); nodes=tuple(policy.nodes)
    if not policy.policy_id or not policy.root_node_id: issues.append("missing_policy_identity")
    if policy.max_steps<1 or not all(isfinite(x) and x>=0 for x in (policy.max_total_cost,policy.max_total_risk,policy.min_robust_eig)):
        issues.append("invalid_policy_limits")
    if not _unique(actions,"action_id"): issues.append("duplicate_action_id")
    if not _unique(nodes,"node_id"): issues.append("duplicate_node_id")
    amap={a.action_id:a for a in actions}; nmap={n.node_id:n for n in nodes}
    if policy.root_node_id not in nmap: issues.append("missing_root_node")
    if not scenarios: issues.append("no_model_scenarios")
    used_action_ids={n.action_id for n in nodes}
    for s in scenarios:
        if not _scenario_valid(s,used_action_ids): issues.append("invalid_or_uncalibrated_scenario:"+s.scenario_id)
    for a in actions:
        if not all((a.action_id,a.design_ref,a.measurement_ref,a.selection_split,a.validation_split)):
            issues.append("incomplete_action:"+a.action_id)
        if a.selection_split==a.validation_split: issues.append("selection_validation_overlap:"+a.action_id)
        if not all(isfinite(x) and x>=0 for x in (a.cost,a.risk,a.max_risk)): issues.append("negative_cost_or_risk:"+a.action_id)
        if a.risk>a.max_risk: warnings.append("action_exceeds_own_risk_limit:"+a.action_id)
        if a.safety_review!=Review.APPROVED: warnings.append("action_not_approved:"+a.action_id)
        if not a.feasible: warnings.append("action_infeasible:"+a.action_id)
    for n in nodes:
        if n.action_id not in amap: issues.append("unknown_action:"+n.node_id)
        if not n.branches: issues.append("node_without_branches:"+n.node_id)
        outs=[b.outcome for b in n.branches]
        if len(outs)!=len(set(outs)): issues.append("duplicate_outcome_branch:"+n.node_id)
        for b in n.branches:
            if not b.outcome or (b.stop and b.next_node_id) or (not b.stop and b.next_node_id not in nmap):
                issues.append("invalid_branch:"+n.node_id+":"+b.outcome)
    if issues:
        return PolicyAudit(Disposition.BLOCKED,(),0.0,tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    # Detect cycles and depth before evaluating any scenario.
    def walk(node_id, path, depth):
        if node_id in path: issues.append("policy_cycle:"+node_id); return
        if depth>policy.max_steps: issues.append("policy_exceeds_max_steps:"+node_id); return
        n=nmap[node_id]
        for b in n.branches:
            if not b.stop: walk(b.next_node_id,path|{node_id},depth+1)
    walk(policy.root_node_id,set(),1)
    if issues:
        return PolicyAudit(Disposition.BLOCKED,(),0.0,tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    for a in actions:
        if a.action_id in {n.action_id for n in nodes} and (not a.feasible or a.safety_review!=Review.APPROVED or a.risk>a.max_risk):
            issues.append("policy_uses_unapproved_action:"+a.action_id)
    if issues:
        return PolicyAudit(Disposition.BLOCKED,(),0.0,tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    for s in scenarios:
        prior={p.hypothesis_id:p.probability for p in s.priors}
        likelihood={(l.action_id,l.hypothesis_id,l.outcome):l.probability for l in s.likelihoods}
        terminal_entropy=0.0; expected_cost=0.0; worst_risk=0.0; leaves=0
        def evaluate(node_id, belief, path_prob, cost, risk, depth):
            nonlocal terminal_entropy,expected_cost,worst_risk,leaves
            node=nmap[node_id]; action=amap[node.action_id]
            expected_cost += path_prob*action.cost
            next_cost=cost+action.cost; next_risk=risk+action.risk
            if next_cost>policy.max_total_cost+1e-9: issues.append("total_cost_exceeded:"+policy.policy_id)
            if next_risk>policy.max_total_risk+1e-9: issues.append("path_risk_exceeded:"+policy.policy_id)
            expected_outcomes={l.outcome for l in s.likelihoods if l.action_id==action.action_id}
            declared_outcomes={b.outcome for b in node.branches}
            if expected_outcomes!=declared_outcomes:
                issues.append("branch_outcome_coverage_mismatch:"+node_id)
            for branch in node.branches:
                if branch.outcome not in expected_outcomes:
                    issues.append("branch_has_no_likelihood:"+node_id+":"+branch.outcome)
                    continue
                probs=[belief[h]*likelihood[(action.action_id,h,branch.outcome)] for h in belief]
                marginal=sum(probs)
                if marginal<=0: issues.append("zero_probability_branch:"+node_id+":"+branch.outcome); continue
                posterior={h:v/marginal for h,v in zip(belief,probs)}
                branch_prob=path_prob*marginal
                if branch.stop:
                    terminal_entropy += branch_prob*_entropy(tuple(posterior.values()))
                    worst_risk=max(worst_risk,next_risk); leaves+=1
                else:
                    evaluate(branch.next_node_id,posterior,branch_prob,next_cost,next_risk,depth+1)
        evaluate(policy.root_node_id,prior,1.0,0.0,0.0,1)
        eig=_entropy(tuple(prior.values()))-terminal_entropy
        scores.append(ScenarioScore(s.scenario_id,eig,expected_cost,worst_risk,leaves))
    if issues:
        return PolicyAudit(Disposition.BLOCKED,tuple(scores),min((x.expected_information_gain for x in scores),default=0.0),tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    robust=min(x.expected_information_gain for x in scores)
    if robust<=1e-12: disposition=Disposition.NO_INFORMATION_GAIN
    elif robust+1e-12<policy.min_robust_eig: disposition=Disposition.FRAGILE_POLICY
    else: disposition=Disposition.ROBUST_POLICY_REVIEW
    warnings.extend(("expected_information_gain_depends_on_declared_calibrated_models","policy_tree_is_evaluated_not_automatically_searched","human_review_required_and_no_execution_authorized","validation_split_must_remain_unseen_until_final_evaluation"))
    return PolicyAudit(disposition,tuple(scores),robust,(),tuple(sorted(set(warnings))),False,False)
