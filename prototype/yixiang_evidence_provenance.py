"""M14 textual witness provenance and claim-evidence audit."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class EvidenceStance(str, Enum):
    SUPPORTS="supports"
    CONTRADICTS="contradicts"
    QUALIFIES="qualifies"
class ReviewStatus(str, Enum):
    UNREVIEWED="unreviewed"
    REVIEWED="reviewed"
    DISPUTED="disputed"
class ClaimEvidenceDecision(str, Enum):
    SUPPORT_ONLY="support_only"
    CONFLICTED="conflicted"
    QUALIFICATION_ONLY="qualification_only"
    INSUFFICIENT="insufficient"
    UNREVIEWED="unreviewed"

@dataclass(frozen=True)
class Witness:
    witness_id:str
    work_id:str
    edition_id:str
    witness_kind:str
    location:str
    content_status:str
    lineage_complete:bool
    evidence_refs:Tuple[str,...]
    parent_ids:Tuple[str,...]=()
    derivation_kinds:Tuple[str,...]=()

@dataclass(frozen=True)
class ClaimEvidence:
    evidence_id:str
    witness_id:str
    claim_id:str
    stance:EvidenceStance
    review_status:ReviewStatus
    reviewer_ids:Tuple[str,...]
    rationale:str

@dataclass(frozen=True)
class EvidenceAssessment:
    claim_id:str
    decision:ClaimEvidenceDecision
    reviewed_support_count:int
    reviewed_contradiction_count:int
    reviewed_qualification_count:int
    independent_support_groups:Tuple[Tuple[str,...],...]
    lineage_uncertain_witnesses:Tuple[str,...]
    unresolved_evidence_ids:Tuple[str,...]
    semantic_truth_established:bool=False
    interpretation_ceiling:str="provenance_and_review_state_only"

@dataclass(frozen=True)
class ProvenanceAudit:
    witness_count:int
    root_witnesses:Tuple[str,...]
    derived_witnesses:Tuple[str,...]
    incomplete_lineage_witnesses:Tuple[str,...]
    lineage_groups:Tuple[Tuple[str,...],...]
    cycle_free:bool=True
    authenticity_established:bool=False

def _s(v,f):
    if not isinstance(v,str) or not v.strip(): raise ValueError(f"{f} must be non-empty")
def _strings(v,f,empty=True):
    if not isinstance(v,tuple) or (not empty and not v): raise ValueError(f"{f} must be tuple")
    for x in v: _s(x,f)
    if len(v)!=len(set(v)): raise ValueError(f"{f} entries must be unique")
def _validate_witness(w):
    if not isinstance(w,Witness): raise ValueError("witness entries must be Witness")
    for f in ("witness_id","work_id","edition_id","witness_kind","location","content_status"): _s(getattr(w,f),f)
    if not isinstance(w.lineage_complete,bool): raise ValueError("lineage_complete must be bool")
    _strings(w.evidence_refs,"evidence_refs",False); _strings(w.parent_ids,"parent_ids"); _strings(w.derivation_kinds,"derivation_kinds")
    if len(w.parent_ids)!=len(w.derivation_kinds): raise ValueError("each parent requires one derivation kind")
    allowed={"copied_from","quoted_from","revised_from","transcribed_from","ocr_from","collation_of","unknown_derivation"}
    if any(x not in allowed for x in w.derivation_kinds): raise ValueError("unknown derivation kind")

def _ancestors(wid,by,memo):
    if wid in memo: return memo[wid]
    result=set()
    for parent in by[wid].parent_ids:
        result.add(parent); result.update(_ancestors(parent,by,memo))
    memo[wid]=frozenset(result)
    return memo[wid]

def audit_provenance(witnesses):
    if not isinstance(witnesses,tuple) or not witnesses: raise ValueError("witnesses must be non-empty tuple")
    for w in witnesses: _validate_witness(w)
    ids=[w.witness_id for w in witnesses]
    if len(ids)!=len(set(ids)): raise ValueError("witness_id values must be unique")
    by={w.witness_id:w for w in witnesses}
    for w in witnesses:
        for p in w.parent_ids:
            if p not in by: raise ValueError(f"unknown parent witness: {p}")
            if p==w.witness_id: raise ValueError("witness cannot derive from itself")
    visiting=set(); visited=set()
    def visit(n):
        if n in visiting: raise ValueError("provenance graph contains a cycle")
        if n in visited: return
        visiting.add(n)
        for p in by[n].parent_ids: visit(p)
        visiting.remove(n); visited.add(n)
    for n in ids: visit(n)
    memo={}; groups=[]
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            aa, bb = _ancestors(a,by,memo), _ancestors(b,by,memo)\n            if a in bb or b in aa or (aa & bb): groups.append(tuple(sorted((a,b))))
    return ProvenanceAudit(len(ids),tuple(sorted(w.witness_id for w in witnesses if not w.parent_ids)),
        tuple(sorted(w.witness_id for w in witnesses if w.parent_ids)),
        tuple(sorted(w.witness_id for w in witnesses if not w.lineage_complete)),tuple(sorted(groups)))

def assess_claim_evidence(claim_id,witnesses,evidence):
    _s(claim_id,"claim_id"); audit_provenance(witnesses); by={w.witness_id:w for w in witnesses}
    if not isinstance(evidence,tuple): raise ValueError("evidence must be tuple")
    ids=[]; relevant=[]
    for x in evidence:
        if not isinstance(x,ClaimEvidence): raise ValueError("evidence entries must be ClaimEvidence")
        for f in ("evidence_id","witness_id","claim_id","rationale"): _s(getattr(x,f),f)
        _strings(x.reviewer_ids,"reviewer_ids")
        if x.evidence_id in ids: raise ValueError("evidence_id values must be unique")
        ids.append(x.evidence_id)
        if x.witness_id not in by: raise ValueError("evidence references unknown witness")
        if not isinstance(x.stance,EvidenceStance) or not isinstance(x.review_status,ReviewStatus): raise ValueError("invalid stance or review status")
        if x.review_status==ReviewStatus.REVIEWED and (not x.reviewer_ids or len(x.rationale.strip())<12): raise ValueError("reviewed evidence requires reviewer IDs and substantive rationale")
        if x.review_status!=ReviewStatus.REVIEWED and x.reviewer_ids: raise ValueError("unreviewed/disputed evidence cannot claim completed reviewers")
        if x.claim_id==claim_id: relevant.append(x)
    reviewed=[x for x in relevant if x.review_status==ReviewStatus.REVIEWED]
    sup=[x for x in reviewed if x.stance==EvidenceStance.SUPPORTS]
    con=[x for x in reviewed if x.stance==EvidenceStance.CONTRADICTS]
    qua=[x for x in reviewed if x.stance==EvidenceStance.QUALIFIES]
    unresolved=tuple(sorted(x.evidence_id for x in relevant if x.review_status!=ReviewStatus.REVIEWED))
    uncertain=tuple(sorted({x.witness_id for x in relevant if not by[x.witness_id].lineage_complete}))
    if not reviewed: decision=ClaimEvidenceDecision.UNREVIEWED if relevant else ClaimEvidenceDecision.INSUFFICIENT
    elif sup and con: decision=ClaimEvidenceDecision.CONFLICTED
    elif sup: decision=ClaimEvidenceDecision.SUPPORT_ONLY
    elif qua: decision=ClaimEvidenceDecision.QUALIFICATION_ONLY
    else: decision=ClaimEvidenceDecision.INSUFFICIENT
    groups=[]
    for i,left in enumerate(sup):
        for right in sup[i+1:]:
            a,b=by[left.witness_id],by[right.witness_id]
            if not (a.lineage_complete and b.lineage_complete): continue
            aa=_ancestors(a.witness_id,by,{}); bb=_ancestors(b.witness_id,by,{})
            if a.witness_id not in bb and b.witness_id not in aa and not (aa&bb):
                groups.append(tuple(sorted((a.witness_id,b.witness_id))))
    return EvidenceAssessment(claim_id,decision,len(sup),len(con),len(qua),tuple(sorted(set(groups))),uncertain,unresolved)
