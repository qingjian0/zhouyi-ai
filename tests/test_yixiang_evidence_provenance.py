import unittest
from prototype.yixiang_evidence_provenance import *
def w(i,parents=(),complete=True):
    return Witness(i,"work","edition-"+i,"printed","juan1/page1","checked",complete,("ref-"+i,),tuple(parents),tuple("copied_from" for _ in parents))
def ev(i,wid,stance=EvidenceStance.SUPPORTS,status=ReviewStatus.REVIEWED,reviewers=("r1",),rationale="Reviewed against the cited witness."):
    return ClaimEvidence(i,wid,"claim",stance,status,tuple(reviewers),rationale)
class M14Tests(unittest.TestCase):
    def test_root(self): self.assertEqual(audit_provenance((w("A"),)).root_witnesses,("A",))
    def test_chain(self): self.assertEqual(audit_provenance((w("A"),w("B",("A",)),w("C",("B",)))).derived_witnesses,("B","C"))
    def test_missing_parent(self):
        with self.assertRaises(ValueError): audit_provenance((w("B",("X",)),))
    def test_cycle(self):
        with self.assertRaises(ValueError): audit_provenance((w("A",("B",)),w("B",("A",))))
    def test_self_parent(self):
        with self.assertRaises(ValueError): audit_provenance((w("A",("A",)),))
    def test_duplicate_witness(self):
        with self.assertRaises(ValueError): audit_provenance((w("A"),w("A")))
    def test_edge_arity(self):
        x=w("B",("A",)); bad=Witness(x.witness_id,x.work_id,x.edition_id,x.witness_kind,x.location,x.content_status,x.lineage_complete,x.evidence_refs,x.parent_ids,())
        with self.assertRaises(ValueError): audit_provenance((w("A"),bad))
    def test_unknown_edge_kind(self):
        x=w("B",("A",)); bad=Witness(x.witness_id,x.work_id,x.edition_id,x.witness_kind,x.location,x.content_status,x.lineage_complete,x.evidence_refs,x.parent_ids,("bad",))
        with self.assertRaises(ValueError): audit_provenance((w("A"),bad))
    def test_shared_ancestor(self): self.assertIn(("B","C"),audit_provenance((w("A"),w("B",("A",)),w("C",("A",)))).lineage_groups)
    def test_ancestor_descendant_dependency_detected(self):\n        self.assertIn(("A","B"),audit_provenance((w("A"),w("B",("A",)))).lineage_groups)\n    def test_distinct_roots_not_authenticity(self):
        x=audit_provenance((w("A"),w("B"))); self.assertEqual(x.lineage_groups,()); self.assertFalse(x.authenticity_established)
    def test_incomplete_lineage(self): self.assertEqual(audit_provenance((w("A",complete=False),)).incomplete_lineage_witnesses,("A",))
    def test_independent_support_pair(self):
        x=assess_claim_evidence("claim",(w("A"),w("B")),(ev("e1","A"),ev("e2","B",reviewers=("r2",))))
        self.assertEqual(x.independent_support_groups,(("A","B"),))
    def test_shared_ancestor_not_independent(self):
        x=assess_claim_evidence("claim",(w("root"),w("A",("root",)),w("B",("root",))),(ev("e1","A"),ev("e2","B",reviewers=("r2",))))
        self.assertEqual(x.independent_support_groups,())
    def test_incomplete_lineage_not_independent(self):
        x=assess_claim_evidence("claim",(w("A",complete=False),w("B")),(ev("e1","A"),ev("e2","B",reviewers=("r2",))))
        self.assertEqual(x.independent_support_groups,()); self.assertEqual(x.lineage_uncertain_witnesses,("A",))
    def test_support_conflict(self):
        x=assess_claim_evidence("claim",(w("A"),w("B")),(ev("e1","A"),ev("e2","B",EvidenceStance.CONTRADICTS,reviewers=("r2",))))
        self.assertEqual(x.decision,ClaimEvidenceDecision.CONFLICTED)
    def test_qualification_only(self): self.assertEqual(assess_claim_evidence("claim",(w("A"),),(ev("e1","A",EvidenceStance.QUALIFIES),)).decision,ClaimEvidenceDecision.QUALIFICATION_ONLY)
    def test_contradiction_only(self): self.assertEqual(assess_claim_evidence("claim",(w("A"),),(ev("e1","A",EvidenceStance.CONTRADICTS),)).decision,ClaimEvidenceDecision.INSUFFICIENT)
    def test_unreviewed_only(self): self.assertEqual(assess_claim_evidence("claim",(w("A"),),(ev("e1","A",status=ReviewStatus.UNREVIEWED,reviewers=()),)).decision,ClaimEvidenceDecision.UNREVIEWED)
    def test_no_evidence(self): self.assertEqual(assess_claim_evidence("claim",(w("A"),),()).decision,ClaimEvidenceDecision.INSUFFICIENT)
    def test_unknown_witness(self):
        with self.assertRaises(ValueError): assess_claim_evidence("claim",(w("A"),),(ev("e1","X"),))
    def test_short_rationale(self):
        with self.assertRaises(ValueError): assess_claim_evidence("claim",(w("A"),),(ev("e1","A",rationale="short"),))
    def test_disputed_with_reviewer_rejected(self):
        with self.assertRaises(ValueError): assess_claim_evidence("claim",(w("A"),),(ev("e1","A",status=ReviewStatus.DISPUTED),))
    def test_duplicate_evidence(self):
        with self.assertRaises(ValueError): assess_claim_evidence("claim",(w("A"),),(ev("e1","A"),ev("e1","A")))
    def test_semantic_truth_never_established(self):
        self.assertFalse(assess_claim_evidence("claim",(w("A"),),(ev("e1","A"),)).semantic_truth_established)
    def test_claim_scope(self):
        x=ev("e1","A"); other=ClaimEvidence(x.evidence_id,x.witness_id,"other",x.stance,x.review_status,x.reviewer_ids,x.rationale)
        self.assertEqual(assess_claim_evidence("claim",(w("A"),),(other,)).decision,ClaimEvidenceDecision.INSUFFICIENT)
if __name__=="__main__": unittest.main()
