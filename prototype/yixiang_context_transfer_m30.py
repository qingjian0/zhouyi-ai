"""M30 context-transfer and yixiang stability audit; structural checks only."""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class StabilityDimension(str, Enum):
    MORPHOLOGY="morphology"; ATTRIBUTE="attribute"; STRUCTURAL_RELATION="structural_relation"
    FUNCTION="function"; MECHANISM="mechanism"; SYSTEM_BEHAVIOR="system_behavior"
class StabilityOutcome(str, Enum):
    STABLE="stable"; WEAKENED="weakened"; REVERSED="reversed"; FAILED="failed"; UNKNOWN="unknown"
class TransferKind(str, Enum):
    FEATURE="feature"; RELATION="relation"; FUNCTION="function"; MECHANISM="mechanism"; SYSTEM="system"
class TransferDecision(str, Enum):
    ALLOW="allow"; CONDITIONAL="conditional"; REVIEW="review"; BLOCK="block"
class EvidenceBasis(str, Enum):
    MORPHOLOGY="morphology"; ATTRIBUTE="attribute"; STRUCTURAL_RELATION="structural_relation"
    FUNCTION="function"; MECHANISM="mechanism"; SYSTEM_BEHAVIOR="system_behavior"

@dataclass(frozen=True)
class ContextProfile:
    context_id:str; version:str; task:str; environment:str; observer:str; scope:str
@dataclass(frozen=True)
class ContextPair:
    pair_id:str; source_context_id:str; target_context_id:str; shift_dimensions:Tuple[str,...]
@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id:str; context_ids:Tuple[str,...]; basis:EvidenceBasis; method:str; scope:str; reviewed:bool=False
@dataclass(frozen=True)
class StabilityAssessment:
    assessment_id:str; pair_id:str; dimension:StabilityDimension; outcome:StabilityOutcome
    evidence_refs:Tuple[str,...]; counterexample_refs:Tuple[str,...]; method:str; scope:str; rationale:str
    reviewer_ids:Tuple[str,...]=()
@dataclass(frozen=True)
class TransferPermission:
    permission_id:str; pair_id:str; transfer_kind:TransferKind; decision:TransferDecision
    evidence_refs:Tuple[str,...]; constraints:Tuple[str,...]; counterexample_refs:Tuple[str,...]
    rationale:str; reviewer_ids:Tuple[str,...]=()
@dataclass(frozen=True)
class ShiftProfile:
    shift_id:str; pair_id:str; changed_dimensions:Tuple[str,...]; magnitude_label:str
    evidence_refs:Tuple[str,...]; rationale:str
@dataclass(frozen=True)
class TransferEvaluation:
    evaluation_id:str; split_unit:str; train_object_ids:Tuple[str,...]; test_object_ids:Tuple[str,...]
    train_context_families:Tuple[str,...]; test_context_families:Tuple[str,...]
    baselines:Tuple[str,...]; metrics:Tuple[str,...]; results_recorded:bool
    result_refs:Tuple[str,...]; limitations:Tuple[str,...]
@dataclass(frozen=True)
class AuditReport:
    valid:bool; issues:Tuple[str,...]; allowed_permissions:Tuple[str,...]
    blocked_permissions:Tuple[str,...]; stability_claims:Tuple[str,...]
    semantic_validity_established:bool=False

_REQUIRED_BASIS={
 TransferKind.FEATURE:{EvidenceBasis.MORPHOLOGY,EvidenceBasis.ATTRIBUTE},
 TransferKind.RELATION:{EvidenceBasis.STRUCTURAL_RELATION},
 TransferKind.FUNCTION:{EvidenceBasis.FUNCTION},
 TransferKind.MECHANISM:{EvidenceBasis.MECHANISM},
 TransferKind.SYSTEM:{EvidenceBasis.SYSTEM_BEHAVIOR},
}

def audit_context_transfer(contexts,pairs,evidence,assessments,permissions,shifts=(),evaluation=None):
    issues=[]
    cmap={c.context_id:c for c in contexts}
    if len(cmap)!=len(contexts) or any(not all((c.context_id,c.version,c.task,c.environment,c.observer,c.scope)) for c in contexts):
        issues.append("invalid_or_duplicate_context")
    pmap={p.pair_id:p for p in pairs}
    if len(pmap)!=len(pairs): issues.append("duplicate_context_pair")
    for p in pairs:
        if not p.pair_id or p.source_context_id not in cmap or p.target_context_id not in cmap:
            issues.append("invalid_context_pair:"+p.pair_id)
        if p.source_context_id==p.target_context_id: issues.append("same_context_is_not_transfer:"+p.pair_id)
        if not p.shift_dimensions or any(not x.strip() for x in p.shift_dimensions):
            issues.append("missing_shift_dimensions:"+p.pair_id)
    emap={e.evidence_id:e for e in evidence}
    if len(emap)!=len(evidence): issues.append("duplicate_evidence_id")
    for e in evidence:
        if not e.evidence_id or not e.context_ids or any(x not in cmap for x in e.context_ids):
            issues.append("invalid_evidence_context:"+e.evidence_id)
        if not e.method.strip() or not e.scope.strip(): issues.append("incomplete_evidence:"+e.evidence_id)
    stability=[]
    assessment_ids=[a.assessment_id for a in assessments]
    if len(assessment_ids)!=len(set(assessment_ids)): issues.append("duplicate_assessment_id")
    for a in assessments:
        p=pmap.get(a.pair_id)
        if p is None: issues.append("unknown_assessment_pair:"+a.assessment_id); continue
        if not a.evidence_refs or any(x not in emap for x in a.evidence_refs):
            issues.append("missing_or_unknown_assessment_evidence:"+a.assessment_id)
        else:
            covered=set()
            for x in a.evidence_refs:
                if not set(emap[x].context_ids).intersection({p.source_context_id,p.target_context_id}):
                    issues.append("assessment_evidence_context_mismatch:"+a.assessment_id)
                covered.update(emap[x].context_ids)
            if not {p.source_context_id,p.target_context_id}.issubset(covered):
                issues.append("assessment_evidence_must_cover_both_contexts:"+a.assessment_id)
        if not a.method.strip() or not a.scope.strip() or not a.rationale.strip():
            issues.append("incomplete_stability_assessment:"+a.assessment_id)
        if a.outcome==StabilityOutcome.STABLE and not a.reviewer_ids:
            issues.append("stable_claim_requires_reviewers:"+a.assessment_id)
        if a.outcome==StabilityOutcome.STABLE and any(x in emap and not emap[x].reviewed for x in a.evidence_refs):
            issues.append("stable_claim_requires_reviewed_evidence:"+a.assessment_id)
        if a.outcome==StabilityOutcome.STABLE and a.counterexample_refs:
            issues.append("stable_claim_has_unresolved_counterexamples:"+a.assessment_id)
        if a.outcome==StabilityOutcome.STABLE: stability.append(a.assessment_id)
    allowed=[]; blocked=[]
    for t in permissions:
        p=pmap.get(t.pair_id)
        if p is None: issues.append("unknown_permission_pair:"+t.permission_id); continue
        refs=[emap[x] for x in t.evidence_refs if x in emap]
        if not t.evidence_refs or len(refs)!=len(t.evidence_refs):
            issues.append("missing_or_unknown_permission_evidence:"+t.permission_id)
        else:
            covered=set()
            for e in refs:
                if not set(e.context_ids).intersection({p.source_context_id,p.target_context_id}):
                    issues.append("permission_evidence_context_mismatch:"+t.permission_id)
                covered.update(e.context_ids)
            if not {p.source_context_id,p.target_context_id}.issubset(covered):
                issues.append("permission_evidence_must_cover_both_contexts:"+t.permission_id)
        bases={e.basis for e in refs}
        if t.decision in (TransferDecision.ALLOW,TransferDecision.CONDITIONAL):
            if not (bases&_REQUIRED_BASIS[t.transfer_kind]):
                issues.append("insufficient_basis_for_transfer_kind:"+t.permission_id)
            if t.transfer_kind==TransferKind.MECHANISM and EvidenceBasis.MECHANISM not in bases:
                issues.append("mechanism_transfer_requires_mechanism_evidence:"+t.permission_id)
            if t.transfer_kind==TransferKind.SYSTEM and EvidenceBasis.SYSTEM_BEHAVIOR not in bases:
                issues.append("system_transfer_requires_system_evidence:"+t.permission_id)
            if not all(e.reviewed for e in refs): issues.append("transfer_requires_reviewed_evidence:"+t.permission_id)
            if not t.reviewer_ids or not t.rationale.strip(): issues.append("transfer_permission_requires_adjudication:"+t.permission_id)
            if t.decision==TransferDecision.CONDITIONAL and not t.constraints:
                issues.append("conditional_transfer_requires_constraints:"+t.permission_id)
            if t.counterexample_refs and t.decision==TransferDecision.ALLOW:
                issues.append("counterexamples_require_conditional_or_blocked:"+t.permission_id)
        if t.transfer_kind in (TransferKind.MECHANISM,TransferKind.SYSTEM) and bases<={EvidenceBasis.MORPHOLOGY,EvidenceBasis.ATTRIBUTE,EvidenceBasis.STRUCTURAL_RELATION}:
            issues.append("surface_or_structure_cannot_authorize_high_level_transfer:"+t.permission_id)
        (blocked if t.decision in (TransferDecision.BLOCK,TransferDecision.REVIEW) else allowed).append(t.permission_id)
    for s in shifts:
        if s.pair_id not in pmap: issues.append("unknown_shift_pair:"+s.shift_id)
        if not s.changed_dimensions or not s.magnitude_label or not s.evidence_refs or any(x not in emap for x in s.evidence_refs):
            issues.append("incomplete_shift_profile:"+s.shift_id)
    if evaluation is not None:
        if evaluation.split_unit not in ("object","source_family","context_family"): issues.append("invalid_split_unit")
        if set(evaluation.train_object_ids)&set(evaluation.test_object_ids): issues.append("object_leakage_across_split")
        if set(evaluation.train_context_families)&set(evaluation.test_context_families): issues.append("context_family_leakage_across_split")
        required={"feature_similarity","classification","structural_relation"}
        if not required.issubset(set(evaluation.baselines)): issues.append("missing_required_baseline")
        if not evaluation.metrics: issues.append("missing_evaluation_metrics")
        if evaluation.results_recorded and not evaluation.result_refs: issues.append("recorded_results_require_result_refs")
        if not evaluation.results_recorded and evaluation.result_refs: issues.append("result_refs_without_results")
        if not evaluation.limitations: issues.append("evaluation_limitations_required")
    return AuditReport(not issues,tuple(sorted(set(issues))),tuple(sorted(allowed)),tuple(sorted(blocked)),tuple(sorted(stability)))
