"""M44 orchestration gate for adaptive experiment policy research stages M37-M43."""
from dataclasses import dataclass
from enum import Enum
from prototype.yixiang_adaptive_policy_search_m40 import SearchResult as M40SearchResult
from prototype.yixiang_adaptive_stopping_m41 import StopAudit, Decision
from prototype.yixiang_model_robustness_m42 import RobustnessAudit, RobustnessStatus
from prototype.yixiang_policy_transport_m43 import TransportAudit, TransportStatus

class PipelineStatus(str, Enum):
    BLOCKED="blocked"
    REVIEW_REQUIRED="review_required"
    READY_FOR_HUMAN_REVIEW="ready_for_human_review"
    STOPPED_FOR_HUMAN_REVIEW="stopped_for_human_review"

@dataclass(frozen=True)
class StageReference:
    stage: str
    artifact_ref: str
    evidence_ref: str

@dataclass(frozen=True)
class PipelineInput:
    policy_search: M40SearchResult
    stopping: StopAudit
    robustness: RobustnessAudit
    transport: TransportAudit
    stage_references: tuple

@dataclass(frozen=True)
class PipelineAudit:
    status: PipelineStatus
    completed_stages: tuple
    missing_stages: tuple
    blocking_reasons: tuple
    review_reasons: tuple
    next_step: str
    execution_authorized: bool = False
    causal_truth_established: bool = False

REQUIRED_STAGES=("M37","M38","M39","M40","M41","M42","M43")

def audit_pipeline(bundle):
    blockers=[]; reviews=[]
    refs={r.stage:r for r in bundle.stage_references}
    missing=tuple(x for x in REQUIRED_STAGES if x not in refs)
    for r in bundle.stage_references:
        if not r.artifact_ref or not r.evidence_ref: blockers.append("invalid_stage_reference:"+r.stage)
    if len(refs)!=len(bundle.stage_references): blockers.append("duplicate_stage_reference")
    if missing: reviews.append("missing_stage_references:"+",".join(missing))
    if bundle.policy_search.root is None or bundle.policy_search.disposition=="blocked":
        blockers.append("M40_policy_search_blocked")
    if bundle.stopping.decision==Decision.REVIEW: reviews.append("M41_stopping_review_required")
    if bundle.robustness.status==RobustnessStatus.BLOCKED: blockers.append("M42_robustness_blocked")
    elif bundle.robustness.status!=RobustnessStatus.ROBUST_WITHIN_DECLARED_SET:
        reviews.append("M42_robustness_not_cleared")
    if bundle.transport.status==TransportStatus.BLOCKED: blockers.append("M43_transport_blocked")
    elif bundle.transport.status!=TransportStatus.CONDITIONALLY_TRANSPORTABLE:
        reviews.append("M43_transport_not_cleared")
    if blockers:
        status=PipelineStatus.BLOCKED; next_step="resolve_blocking_contracts_and_rebuild_audit"
    elif reviews:
        status=PipelineStatus.REVIEW_REQUIRED; next_step="complete_missing_evidence_or_human_review"
    elif bundle.stopping.decision==Decision.STOP:
        status=PipelineStatus.STOPPED_FOR_HUMAN_REVIEW; next_step="human_review_terminal_decision_and_adaptive_inference"
    else:
        status=PipelineStatus.READY_FOR_HUMAN_REVIEW; next_step="human_review_next_experiment_before_any_execution"
    return PipelineAudit(status,tuple(x for x in REQUIRED_STAGES if x in refs),missing,
                         tuple(sorted(set(blockers))),tuple(sorted(set(reviews))),next_step,False,False)
