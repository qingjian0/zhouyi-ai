import unittest
from prototype.yixiang_evidence_provenance import ReviewStatus, Witness
from prototype.yixiang_passage_claim_audit import *

def fixture():
    w=(Witness("W1","work","edition","transmitted","juan1","checked",True,("ref",)),)
    c=(InterpretationContext("C1","pre-qin textual layer","argumentative prose","speaker A","analogy",("debate setting",)),)
    p=(PassageSpan("P1","W1","以類取，以類予","《墨子·小取》",TextLayer.BASE_TEXT,"C1","以名舉實，以辭抒意","以說出故","V1",10,16),)
    a=(ClaimAtom("A1","CL1","The passage states a rule of reasoning by kinds."),)
    e=EvidenceLink("E1","A1","P1",EvidenceRelation.SUPPORTS,Coverage.WHOLE_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("reviewer-1",),"The wording directly expresses the stated rule.")
    return w,c,p,a,e

class M15Tests(unittest.TestCase):
    def test_whole_atom_support(self):
        w,c,p,a,e=fixture(); r=assess_claim_coverage("CL1",a,c,p,w,(e,))
        self.assertEqual(r.decision,ClaimCoverageDecision.FULL_ATOM_COVERAGE); self.assertFalse(r.semantic_truth_established)
    def test_partial_quote_not_whole(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",e.relation,Coverage.PARTIAL_ATOM,e.context_fit,e.review_status,e.reviewer_ids,e.rationale)
        r=assess_claim_coverage("CL1",a,c,p,w,(x,)); self.assertEqual(r.decision,ClaimCoverageDecision.PARTIAL_ATOM_COVERAGE); self.assertEqual(r.uncovered_atom_ids,("A1",))
    def test_no_coverage(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",e.relation,Coverage.NO_COVERAGE,e.context_fit,e.review_status,e.reviewer_ids,e.rationale)
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(x,)).decision,ClaimCoverageDecision.INSUFFICIENT)
    def test_context_mismatch(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",e.relation,e.coverage,ContextFit.INCOMPATIBLE,e.review_status,e.reviewer_ids,e.rationale)
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(x,)).atom_assessments[0].decision,AtomDecision.CONTEXT_MISMATCH)
    def test_uncertain_context(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",e.relation,e.coverage,ContextFit.UNCERTAIN,e.review_status,e.reviewer_ids,e.rationale)
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(x,)).atom_assessments[0].decision,AtomDecision.AMBIGUOUS)
    def test_contradiction_retained(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",EvidenceRelation.CONTRADICTS,Coverage.WHOLE_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"The surrounding passage contradicts this reading.")
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(e,x)).decision,ClaimCoverageDecision.CONFLICTED)
    def test_support_with_qualification_is_not_full_coverage(self):
        w,c,p,a,e=fixture(); q=EvidenceLink("E2","A1","P1",EvidenceRelation.QUALIFIES,Coverage.PARTIAL_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"This evidence narrows the valid scope of the claim.")
        r=assess_claim_coverage("CL1",a,c,p,w,(e,q)); self.assertEqual(r.decision,ClaimCoverageDecision.QUALIFIED_COVERAGE)
    def test_unclear_contradiction_is_not_counted_as_contradiction(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",EvidenceRelation.CONTRADICTS,Coverage.UNCLEAR,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"The possible contradiction has unclear scope.")
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(e,x)).decision,ClaimCoverageDecision.FULL_ATOM_COVERAGE)
    def test_qualification_not_support(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",EvidenceRelation.QUALIFIES,Coverage.WHOLE_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"This wording restricts the proposition scope.")
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(x,)).decision,ClaimCoverageDecision.QUALIFICATION_ONLY)
    def test_ambiguous_not_support(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",EvidenceRelation.AMBIGUOUS,Coverage.UNCLEAR,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"The syntax permits more than one interpretation.")
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(x,)).atom_assessments[0].decision,AtomDecision.AMBIGUOUS)
    def test_all_atoms_required(self):
        w,c,p,a,e=fixture(); atoms=a+(ClaimAtom("A2","CL1","A universal causal law."),)
        r=assess_claim_coverage("CL1",atoms,c,p,w,(e,))
        self.assertEqual(r.decision,ClaimCoverageDecision.PARTIAL_ATOM_COVERAGE); self.assertEqual(r.uncovered_atom_ids,("A2",))
    def test_each_atom_linked(self):
        w,c,p,a,e=fixture(); atoms=a+(ClaimAtom("A2","CL1","A second proposition."),)
        x=EvidenceLink("E2","A2","P1",EvidenceRelation.SUPPORTS,Coverage.WHOLE_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"The passage directly supports this second proposition.")
        self.assertEqual(assess_claim_coverage("CL1",atoms,c,p,w,(e,x)).decision,ClaimCoverageDecision.FULL_ATOM_COVERAGE)
    def test_unreviewed_not_promoted(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",e.relation,e.coverage,e.context_fit,ReviewStatus.UNREVIEWED,(),"Awaiting review.")
        self.assertEqual(assess_claim_coverage("CL1",a,c,p,w,(x,)).decision,ClaimCoverageDecision.UNREVIEWED)
    def test_unknown_witness(self):
        w,c,p,a,e=fixture(); bad=PassageSpan("P2","W-X","text","loc",TextLayer.BASE_TEXT,"C1")
        with self.assertRaises(ValueError): assess_claim_coverage("CL1",a,c,(bad,),w,(e,))
    def test_unknown_context(self):
        w,c,p,a,e=fixture(); bad=PassageSpan("P2","W1","text","loc",TextLayer.BASE_TEXT,"C-X")
        with self.assertRaises(ValueError): assess_claim_coverage("CL1",a,c,(bad,),w,(e,))
    def test_duplicate_evidence(self):
        w,c,p,a,e=fixture()
        with self.assertRaises(ValueError): assess_claim_coverage("CL1",a,c,p,w,(e,e))
    def test_reviewed_requires_reviewer_reason(self):
        w,c,p,a,e=fixture(); x=EvidenceLink("E2","A1","P1",e.relation,e.coverage,e.context_fit,ReviewStatus.REVIEWED,(),"short")
        with self.assertRaises(ValueError): assess_claim_coverage("CL1",a,c,p,w,(x,))
    def test_commentary_cannot_support_base_text_claim_by_default(self):
        w,c,p,a,e=fixture(); note=PassageSpan("P2","W1","注曰……","commentary",TextLayer.COMMENTARY,"C1")
        x=EvidenceLink("E2","A1","P2",EvidenceRelation.SUPPORTS,Coverage.WHOLE_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"This is a commentary interpretation, not base text.")
        r=assess_claim_coverage("CL1",a,c,p+(note,),w,(x,)); self.assertEqual(r.atom_assessments[0].decision,AtomDecision.LAYER_MISMATCH)
    def test_commentary_can_support_commentary_claim_when_declared(self):
        w,c,p,a,e=fixture(); note=PassageSpan("P2","W1","注曰……","commentary",TextLayer.COMMENTARY,"C1")
        atom=(ClaimAtom("A1","CL1","The commentary interprets the passage.",(TextLayer.COMMENTARY,)),)
        x=EvidenceLink("E2","A1","P2",EvidenceRelation.SUPPORTS,Coverage.WHOLE_ATOM,ContextFit.COMPATIBLE,ReviewStatus.REVIEWED,("r2",),"This commentary directly states the interpretation.")
        r=assess_claim_coverage("CL1",atom,c,p+(note,),w,(x,)); self.assertEqual(r.decision,ClaimCoverageDecision.FULL_ATOM_COVERAGE)
    def test_variant_group_preserved(self):
        w,c,p,a,e=fixture(); alt=PassageSpan("P2","W1","異文","loc2",TextLayer.BASE_TEXT,"C1",variant_group_id="V1")
        r=assess_claim_coverage("CL1",a,c,p+(alt,),w,(e,)); self.assertEqual(r.decision,ClaimCoverageDecision.FULL_ATOM_COVERAGE)
        self.assertEqual(alt.variant_group_id,"V1")
    def test_atom_claim_mismatch(self):
        w,c,p,a,e=fixture()
        with self.assertRaises(ValueError): assess_claim_coverage("CL1",(ClaimAtom("A2","OTHER","other"),),c,p,w,())
    def test_semantic_truth_never_established(self):
        w,c,p,a,e=fixture(); self.assertFalse(assess_claim_coverage("CL1",a,c,p,w,(e,)).semantic_truth_established)

if __name__=="__main__": unittest.main()
