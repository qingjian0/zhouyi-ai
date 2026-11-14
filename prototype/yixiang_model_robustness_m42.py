"""M42 stress audit for model misspecification and hidden-confounding sensitivity."""
from dataclasses import dataclass
from enum import Enum
from math import isfinite

class Confounding(str, Enum):
    ADDRESSED="addressed"
    SENSITIVITY_BOUNDED="sensitivity_bounded"
    UNMODELED="unmodeled"
    UNKNOWN="unknown"

class RobustnessStatus(str, Enum):
    ROBUST_WITHIN_DECLARED_SET="robust_within_declared_set"
    FRAGILE="fragile"
    REVIEW_REQUIRED="review_required"
    BLOCKED="blocked"

@dataclass(frozen=True)
class StressScenario:
    scenario_id: str
    policy_value: float
    prior_shift: float
    likelihood_shift: float
    measurement_shift: float
    confounding: Confounding
    assumptions_ref: str
    evidence_ref: str
    calibrated: bool

@dataclass(frozen=True)
class RobustnessAudit:
    status: RobustnessStatus
    nominal_value: float
    worst_case_value: float
    best_case_value: float
    value_range: float
    scenario_values: tuple
    issues: tuple
    warnings: tuple
    causal_claim_permitted: bool = False

def audit_model_robustness(nominal_value, scenarios, minimum_acceptable_value=0.0,
                           max_prior_shift=0.25, max_likelihood_shift=0.25,
                           max_measurement_shift=0.25, require_confounding_addressed=True):
    scenarios=tuple(scenarios); issues=[]; warnings=[]
    limits=(nominal_value,minimum_acceptable_value,max_prior_shift,max_likelihood_shift,max_measurement_shift)
    if any(not isfinite(x) for x in limits): issues.append("non_finite_limit_or_nominal")
    if any(x<0 for x in (max_prior_shift,max_likelihood_shift,max_measurement_shift)): issues.append("negative_shift_limit")
    if not scenarios: issues.append("no_stress_scenarios")
    ids=[s.scenario_id for s in scenarios]
    if len(ids)!=len(set(ids)): issues.append("duplicate_scenario_id")
    for s in scenarios:
        vals=(s.policy_value,s.prior_shift,s.likelihood_shift,s.measurement_shift)
        if any(not isfinite(x) for x in vals): issues.append("non_finite_scenario:"+s.scenario_id); continue
        if any(x<0 for x in vals[1:]): issues.append("negative_shift:"+s.scenario_id)
        if not s.assumptions_ref or not s.evidence_ref: issues.append("missing_provenance:"+s.scenario_id)
        if not s.calibrated: issues.append("uncalibrated_scenario:"+s.scenario_id)
        if s.prior_shift>max_prior_shift: warnings.append("prior_shift_exceeds_declared_bound:"+s.scenario_id)
        if s.likelihood_shift>max_likelihood_shift: warnings.append("likelihood_shift_exceeds_declared_bound:"+s.scenario_id)
        if s.measurement_shift>max_measurement_shift: warnings.append("measurement_shift_exceeds_declared_bound:"+s.scenario_id)
        if s.confounding in (Confounding.UNKNOWN,Confounding.UNMODELED):
            warnings.append("confounding_not_resolved:"+s.scenario_id)
    if issues:
        return RobustnessAudit(RobustnessStatus.BLOCKED,nominal_value,0.0,0.0,0.0,(),tuple(sorted(set(issues))),tuple(sorted(set(warnings))))
    values=[nominal_value]+[s.policy_value for s in scenarios]
    worst=min(values); best=max(values); spread=best-worst
    unresolved=any(s.confounding in (Confounding.UNKNOWN,Confounding.UNMODELED) for s in scenarios)
    out_of_bound=any(s.prior_shift>max_prior_shift or s.likelihood_shift>max_likelihood_shift or s.measurement_shift>max_measurement_shift for s in scenarios)
    if (require_confounding_addressed and unresolved) or out_of_bound:
        status=RobustnessStatus.REVIEW_REQUIRED
    elif worst<minimum_acceptable_value:
        status=RobustnessStatus.FRAGILE
    else:
        status=RobustnessStatus.ROBUST_WITHIN_DECLARED_SET
    warnings.extend(("robustness_is_only_over_explicitly_declared_stress_scenarios",
                     "stress_shifts_are_sensitivity_inputs_not_empirical_discovery",
                     "no_unmeasured_confounder_is_ruled_out_by_this_audit"))
    return RobustnessAudit(status,nominal_value,worst,best,spread,
        tuple((s.scenario_id,s.policy_value) for s in scenarios),(),tuple(sorted(set(warnings))),False)
