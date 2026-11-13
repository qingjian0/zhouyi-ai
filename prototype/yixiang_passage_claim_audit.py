"""M15 passage-to-claim semantic-scope audit; human-reviewed, non-truth-establishing."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple
from prototype.yixiang_evidence_provenance import ReviewStatus, Witness, audit_provenance

class EvidenceRelation(str, Enum):
    SUPPORTS="supports"; CONTRADICTS="contradicts"; QUALIFIES="qualifies"; IRRELEVANT="irrelevant"; AMBIGUOUS="ambiguous"
class Coverage(str, Enum):
    WHOLE_ATOM="whole_atom"; PARTIAL_ATOM="partial_atom"; NO_COVERAGE="no_coverage"; UNCLEAR="unclear"
class ContextFit(str, Enum):
    COMPATIBLE="compatible"; INCOMPATIBLE="incompatible"; UNCERTAIN="uncertain"
class TextLayer(str, Enum):
    BASE_TEXT="base_text"; COMMENTARY="commentary"; QUOTATION="quotation"; EDITORIAL="editorial"; RECONSTRUCTION="reconstruction"; UNKNOWN="unknown"
class AtomDecision(str, Enum):
    SUPPORT_ONLY="support_only"; SUPPORTED_WITH_QUALIFICATION="supported_with_qualification"; CONFLICTED="conflicted"; QUALIFICATION_ONLY="qualification_only"; PARTIAL_ONLY="partial_only"; CONTEXT_MISMATCH="context_mismatch"; LAYER_MISMATCH="layer_mismatch"; AMBIGUOUS="ambiguous"; UNRESOLVED_EVIDENCE="unresolved_evidence"; INSUFFICIENT="insufficient"; UNREVIEWED="unreviewed"
class ClaimCoverageDecision(str, Enum):
    FULL_ATOM_COVERAGE="full_atom_coverage"; QUALIFIED_COVERAGE="qualified_coverage"; PARTIAL_ATOM_COVERAGE="partial_atom_coverage"; CONFLICTED="conflicted"; QUALIFICATION_ONLY="qualification_only"; UNRESOLVED_EVIDENCE="unresolved_evidence"; INSUFFICIENT="insufficient"; UNREVIEWED="unreviewed"

@dataclass(frozen=True)
class ClaimAtom:
    atom_id:str; claim_id:str; text:str; allowed_text_layers:Tuple[TextLayer,...]=(TextLayer.BASE_TEXT,)
@dataclass(frozen=True)
class InterpretationContext:
    context_id:str; period_or_layer:str; genre:str; speaker_or_voice:str; discourse_function:str; conditions:Tuple[str,...]=()
@dataclass(frozen=True)
class PassageSpan:
    span_id:str; witness_id:str; excerpt:str; location:str; text_layer:TextLayer; context_id:str
    context_before:str=""; context_after:str=""; variant_group_id:str=""; char_start:int=-1; char_end:int=-1
@dataclass(frozen=True)
class EvidenceLink:
    evidence_id:str; atom_id:str; span_id:str; relation:EvidenceRelation; coverage:Coverage; context_fit:ContextFit
    review_status:ReviewStatus; reviewer_ids:Tuple[str,...]; rationale:str
@dataclass(frozen=True)
class AtomAssessment:
    atom_id:str; decision:AtomDecision; whole_support_ids:Tuple[str,...]; partial_support_ids:Tuple[str,...]
    contradiction_ids:Tuple[str,...]; qualification_ids:Tuple[str,...]; ambiguous_ids:Tuple[str,...]
    context_mismatch_ids:Tuple[str,...]; layer_mismatch_ids:Tuple[str,...]; unresolved_ids:Tuple[str,...]
@dataclass(frozen=True)
class ClaimAssessment:
    claim_id:str; decision:ClaimCoverageDecision; atom_assessments:Tuple[AtomAssessment,...]
    uncovered_atom_ids:Tuple[str,...]; semantic_truth_established:bool=False
    interpretation_ceiling:str="reviewed_passage_scope_and_context_only"

def _nonempty(v,f):
    if not isinstance(v,str) or not v.strip(): raise ValueError(f"{f} must be non-empty")
def _unique(v,f):
    if not isinstance(v,tuple): raise ValueError(f"{f} must be tuple")
    for x in v: _nonempty(x,f)
    if len(v)!=len(set(v)): raise ValueError(f"{f} entries must be unique")
def _validate_context(x):
    if not isinstance(x,InterpretationContext): raise ValueError("contexts must contain InterpretationContext")
    for f in ("context_id","period_or_layer","genre","speaker_or_voice","discourse_function"): _nonempty(getattr(x,f),f)
    _unique(x.conditions,"conditions")
def _validate_span(x,witnesses,contexts):
    if not isinstance(x,PassageSpan): raise ValueError("passages must contain PassageSpan")
    for f in ("span_id","witness_id","excerpt","location","context_id"): _nonempty(getattr(x,f),f)
    if x.witness_id not in witnesses: raise ValueError(f"unknown witness: {x.witness_id}")
    if x.context_id not in contexts: raise ValueError(f"unknown context: {x.context_id}")
    if not isinstance(x.text_layer,TextLayer): raise ValueError("invalid text layer")
    if not isinstance(x.char_start,int) or not isinstance(x.char_end,int): raise ValueError("character offsets must be integers")
    if (x.char_start==-1)!=(x.char_end==-1): raise ValueError("both character offsets must be supplied together")
    if x.char_start!=-1 and (x.char_start<0 or x.char_end<=x.char_start): raise ValueError("invalid character span")
def _validate_link(x,atoms,spans):
    if not isinstance(x,EvidenceLink): raise ValueError("links must contain EvidenceLink")
    for f in ("evidence_id","atom_id","span_id","rationale"): _nonempty(getattr(x,f),f)
    if x.atom_id not in atoms: raise ValueError(f"unknown claim atom: {x.atom_id}")
    if x.span_id not in spans: raise ValueError(f"unknown passage span: {x.span_id}")
    if not isinstance(x.relation,EvidenceRelation): raise ValueError("invalid evidence relation")
    if not isinstance(x.coverage,Coverage) or not isinstance(x.context_fit,ContextFit): raise ValueError("invalid coverage or context fit")
    if not isinstance(x.review_status,ReviewStatus): raise ValueError("invalid review status")
    _unique(x.reviewer_ids,"reviewer_ids")
    if x.review_status==ReviewStatus.REVIEWED:
        if not x.reviewer_ids or len(x.rationale.strip())<12: raise ValueError("reviewed link requires reviewer IDs and substantive rationale")
    elif x.reviewer_ids: raise ValueError("unreviewed/disputed link cannot claim completed reviewers")
def _assess_atom(atom_id,links,spans,allowed_layers):
    layer_mismatch=tuple(sorted(x.evidence_id for x in links if spans[x.span_id].text_layer not in allowed_layers))
    eligible=[x for x in links if spans[x.span_id].text_layer in allowed_layers]
    reviewed=[x for x in eligible if x.review_status==ReviewStatus.REVIEWED]
    unresolved=tuple(sorted(x.evidence_id for x in eligible if x.review_status!=ReviewStatus.REVIEWED))
    compatible=[x for x in reviewed if x.context_fit==ContextFit.COMPATIBLE]
    mismatch=tuple(sorted(x.evidence_id for x in reviewed if x.context_fit==ContextFit.INCOMPATIBLE))
    ambiguous=[x for x in reviewed if x.context_fit==ContextFit.UNCERTAIN or x.relation==EvidenceRelation.AMBIGUOUS or x.coverage==Coverage.UNCLEAR]
    support=[x for x in compatible if x.relation==EvidenceRelation.SUPPORTS]
    whole=tuple(sorted(x.evidence_id for x in support if x.coverage==Coverage.WHOLE_ATOM))
    partial=tuple(sorted(x.evidence_id for x in support if x.coverage==Coverage.PARTIAL_ATOM))
    contra=tuple(sorted(x.evidence_id for x in compatible if x.relation==EvidenceRelation.CONTRADICTS and x.coverage in (Coverage.WHOLE_ATOM,Coverage.PARTIAL_ATOM)))
    qual=tuple(sorted(x.evidence_id for x in compatible if x.relation==EvidenceRelation.QUALIFIES and x.coverage in (Coverage.WHOLE_ATOM,Coverage.PARTIAL_ATOM)))
    amb=tuple(sorted(x.evidence_id for x in ambiguous))
    if whole and contra: decision=AtomDecision.CONFLICTED
    elif not reviewed and links: decision=AtomDecision.UNREVIEWED
    elif unresolved: decision=AtomDecision.UNRESOLVED_EVIDENCE
    elif whole and qual: decision=AtomDecision.SUPPORTED_WITH_QUALIFICATION
    elif whole and amb: decision=AtomDecision.AMBIGUOUS
    elif whole: decision=AtomDecision.SUPPORT_ONLY
    elif contra: decision=AtomDecision.CONFLICTED
    elif qual: decision=AtomDecision.QUALIFICATION_ONLY
    elif partial: decision=AtomDecision.PARTIAL_ONLY
    elif mismatch: decision=AtomDecision.CONTEXT_MISMATCH
    elif layer_mismatch: decision=AtomDecision.LAYER_MISMATCH
    elif amb: decision=AtomDecision.AMBIGUOUS
    elif not reviewed and links: decision=AtomDecision.UNREVIEWED
    else: decision=AtomDecision.INSUFFICIENT
    return AtomAssessment(atom_id,decision,whole,partial,contra,qual,amb,mismatch,layer_mismatch,unresolved)

def assess_claim_coverage(claim_id,atoms,contexts,passages,witnesses,links):
    _nonempty(claim_id,"claim_id")
    if not isinstance(atoms,tuple) or not atoms: raise ValueError("atoms must be a non-empty tuple")
    if not isinstance(contexts,tuple) or not contexts: raise ValueError("contexts must be a non-empty tuple")
    if not isinstance(passages,tuple) or not passages: raise ValueError("passages must be a non-empty tuple")
    if not isinstance(witnesses,tuple) or not witnesses: raise ValueError("witnesses must be a non-empty tuple")
    if not isinstance(links,tuple): raise ValueError("links must be tuple")
    audit_provenance(witnesses)
    witness_ids={x.witness_id for x in witnesses}; context_by={}; span_by={}; atom_by={}
    for x in contexts:
        _validate_context(x)
        if x.context_id in context_by: raise ValueError("duplicate context_id")
        context_by[x.context_id]=x
    for x in passages:
        _validate_span(x,witness_ids,context_by)
        if x.span_id in span_by: raise ValueError("duplicate span_id")
        span_by[x.span_id]=x
    for x in atoms:
        if not isinstance(x,ClaimAtom): raise ValueError("atoms must contain ClaimAtom")
        for f in ("atom_id","claim_id","text"): _nonempty(getattr(x,f),f)
        if not isinstance(x.allowed_text_layers,tuple) or not x.allowed_text_layers or any(not isinstance(v,TextLayer) for v in x.allowed_text_layers): raise ValueError("allowed_text_layers must be a non-empty tuple of TextLayer")
        if len(x.allowed_text_layers)!=len(set(x.allowed_text_layers)): raise ValueError("allowed_text_layers must be unique")
        if x.claim_id!=claim_id: raise ValueError("all atoms must belong to requested claim")
        if x.atom_id in atom_by: raise ValueError("duplicate atom_id")
        atom_by[x.atom_id]=x
    if not atom_by: raise ValueError("at least one claim atom is required")
    ids=set(); grouped={k:[] for k in atom_by}
    for x in links:
        _validate_link(x,atom_by,span_by)
        if x.evidence_id in ids: raise ValueError("duplicate evidence_id")
        ids.add(x.evidence_id); grouped[x.atom_id].append(x)
    assessments=tuple(_assess_atom(k,grouped[k],span_by,atom_by[k].allowed_text_layers) for k in atom_by)
    decisions={x.decision for x in assessments}
    uncovered=tuple(sorted(x.atom_id for x in assessments if not x.whole_support_ids))
    if AtomDecision.CONFLICTED in decisions: result=ClaimCoverageDecision.CONFLICTED
    elif AtomDecision.UNRESOLVED_EVIDENCE in decisions: result=ClaimCoverageDecision.UNRESOLVED_EVIDENCE
    elif all(x.whole_support_ids and x.decision==AtomDecision.SUPPORT_ONLY for x in assessments): result=ClaimCoverageDecision.FULL_ATOM_COVERAGE
    elif any(x.decision==AtomDecision.SUPPORTED_WITH_QUALIFICATION for x in assessments): result=ClaimCoverageDecision.QUALIFIED_COVERAGE
    elif decisions=={AtomDecision.QUALIFICATION_ONLY}: result=ClaimCoverageDecision.QUALIFICATION_ONLY
    elif any(x.whole_support_ids or x.partial_support_ids for x in assessments): result=ClaimCoverageDecision.PARTIAL_ATOM_COVERAGE
    elif decisions=={AtomDecision.UNREVIEWED}: result=ClaimCoverageDecision.UNREVIEWED
    else: result=ClaimCoverageDecision.INSUFFICIENT
    return ClaimAssessment(claim_id,result,assessments,uncovered)
