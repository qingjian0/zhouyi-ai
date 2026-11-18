"""M41 value-based stopping and continuation audit for adaptive experiments."""
from dataclasses import dataclass
from enum import Enum
from math import isfinite

class Decision(str, Enum):
    STOP="stop"
    CONTINUE="continue"
    REVIEW="review"

@dataclass(frozen=True)
class TerminalOption:
    expected_reward: float
    expected_decision_loss: float
    confidence: float
    evidence_ref: str
    validation_locked: bool

@dataclass(frozen=True)
class ContinuationOption:
    expected_future_reward: float
    experiment_cost: float
    experiment_risk: float
    uncertainty_penalty: float
    evidence_ref: str
    safety_approved: bool
    feasible: bool

@dataclass(frozen=True)
class StopAudit:
    decision: Decision
    stop_value: float
    continue_value: float
    margin: float
    issues: tuple
    warnings: tuple
    terminal_truth_certified: bool = False
    execution_authorized: bool = False

def audit_stopping(terminal, continuation, min_confidence=0.8,
                   continue_margin=0.0, max_risk=1.0, max_experiments_reached=False):
    issues=[]; warnings=[]
    vals=(terminal.expected_reward,terminal.expected_decision_loss,terminal.confidence,
          continuation.expected_future_reward,continuation.experiment_cost,
          continuation.experiment_risk,continuation.uncertainty_penalty,
          min_confidence,continue_margin,max_risk)
    if any(not isfinite(x) for x in vals): issues.append("non_finite_value")
    if any(x<0 for x in (terminal.expected_decision_loss,continuation.experiment_cost,
                         continuation.experiment_risk,continuation.uncertainty_penalty,
                         continue_margin,max_risk)): issues.append("negative_cost_risk_or_margin")
    if not 0<=terminal.confidence<=1 or not 0<=min_confidence<=1: issues.append("invalid_confidence")
    if not terminal.evidence_ref or not continuation.evidence_ref: issues.append("missing_evidence_reference")
    if not terminal.validation_locked: issues.append("validation_not_locked")
    if issues:
        return StopAudit(Decision.REVIEW,0.0,0.0,0.0,tuple(sorted(set(issues))),())
    stop_value=terminal.expected_reward-terminal.expected_decision_loss
    continue_value=(continuation.expected_future_reward-continuation.experiment_cost-
                    continuation.experiment_risk-continuation.uncertainty_penalty)
    margin=continue_value-stop_value
    if max_experiments_reached:
        warnings.append("maximum_experiment_horizon_reached")
        decision=Decision.STOP
    elif not continuation.safety_approved or not continuation.feasible or continuation.experiment_risk>max_risk:
        warnings.append("continuation_not_eligible")
        decision=Decision.STOP if terminal.confidence>=min_confidence else Decision.REVIEW
    elif margin>continue_margin:
        decision=Decision.CONTINUE
    elif terminal.confidence>=min_confidence:
        decision=Decision.STOP
    else:
        decision=Decision.REVIEW
        warnings.append("neither_continuation_value_nor_terminal_confidence_is_sufficient")
    warnings.extend(("stopping_is_a_decision_under_declared_utility_not_proof_of_truth",
                     "adaptive_stopping_rule_must_be_recorded_for_final_inference"))
    return StopAudit(decision,stop_value,continue_value,margin,(),tuple(sorted(set(warnings))))
