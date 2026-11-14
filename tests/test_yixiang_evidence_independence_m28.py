import unittest
from prototype.yixiang_evidence_independence_m28 import *

def src(i, group=None, work=None):
    return SourceIdentity(i, work or ("work-"+i), "edition", group or i, "declared source")
def wit(i, source, complete=True):
    return Witness(i, source, "ed-"+i, "digital_text", "juan1/page1", "base_text",
                   "transcription_unverified", complete)
def edge(i, parent, child, kind=DerivationKind.COPY):
    return Derivation(i, parent, child, kind, "declared", "documented derivation")
def ev(i, witness, stance=EvidenceStance.SUPPORTS, state=ReviewState.REVIEWED, reviewers=("r1",)):
    return EvidenceAssertion(i, witness, "claim", stance, state, tuple(reviewers),
                             "Compared with the cited witness carefully.")

class M28Tests(unittest.TestCase):
    def test_distinct_roots_distinct_source_groups_can_pair(self):
        x=assess_evidence_independence("claim",(src("s1"),src("s2")),(wit("a","s1"),wit("b","s2")),(),(ev("e1","a"),ev("e2","b",reviewers=("r2",))))
        self.assertEqual(x.independent_support_pairs,(("a","b"),))
    def test_same_source_different_digital_witnesses_not_independent(self):
        x=assess_evidence_independence("claim",(src("s"),),(wit("a","s"),wit("b","s")),(),(ev("e1","a"),ev("e2","b")))
        self.assertEqual(x.independent_support_pairs,())
    def test_same_independence_group_not_independent(self):
        x=assess_evidence_independence("claim",(src("s1","family"),src("s2","family")),(wit("a","s1"),wit("b","s2")),(),(ev("e1","a"),ev("e2","b")))
        self.assertEqual(x.independent_support_pairs,())
    def test_shared_ancestor_not_independent(self):
        x=assess_evidence_independence("claim",(src("root"),src("s1"),src("s2")),(wit("r","root"),wit("a","s1"),wit("b","s2")),(edge("d1","r","a"),edge("d2","r","b")),(ev("e1","a"),ev("e2","b")))
        self.assertEqual(x.independent_support_pairs,())
    def test_ancestor_descendant_not_independent(self):
        x=assess_evidence_independence("claim",(src("s1"),src("s2")),(wit("a","s1"),wit("b","s2")),(edge("d","a","b",DerivationKind.OCR),),(ev("e1","a"),ev("e2","b")))
        self.assertEqual(x.independent_support_pairs,())
    def test_ocr_is_explicit_derivation(self):
        a=audit_evidence_provenance((src("s"),),(wit("a","s"),wit("b","s")),(edge("ocr","a","b",DerivationKind.OCR),))
        self.assertEqual(a.derived_witness_ids,("b",))
    def test_translation_is_explicit_derivation(self):
        a=audit_evidence_provenance((src("s"),),(wit("a","s"),wit("b","s")),(edge("tr","a","b",DerivationKind.TRANSLATION),))
        self.assertEqual(a.derivation_edges,1)
    def test_incomplete_lineage_blocks_pair(self):
        x=assess_evidence_independence("claim",(src("s1"),src("s2")),(wit("a","s1",False),wit("b","s2")),(),(ev("e1","a"),ev("e2","b")))
        self.assertEqual(x.independent_support_pairs,())
        self.assertEqual(x.unresolved_lineage_witnesses,("a",))
    def test_conflict_is_preserved(self):
        x=assess_evidence_independence("claim",(src("s1"),src("s2")),(wit("a","s1"),wit("b","s2")),(),(ev("e1","a"),ev("e2","b",EvidenceStance.CONTRADICTS)))
        self.assertEqual(x.contradiction_evidence_ids,("e2",))
    def test_qualification_is_preserved(self):
        x=assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(ev("e1","a",EvidenceStance.QUALIFIES),))
        self.assertEqual(x.qualification_evidence_ids,("e1",))
    def test_unreviewed_is_not_counted_as_support(self):
        x=assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(ev("e1","a",state=ReviewState.UNREVIEWED,reviewers=()),))
        self.assertEqual(x.reviewed_support_records,0)
        self.assertEqual(x.unreviewed_evidence_ids,("e1",))
    def test_conflict_does_not_delete_support(self):
        x=assess_evidence_independence("claim",(src("s1"),src("s2")),(wit("a","s1"),wit("b","s2")),(),(ev("e1","a"),ev("e2","b",EvidenceStance.CONTRADICTS)))
        self.assertEqual(x.reviewed_support_records,1)
        self.assertEqual(x.contradiction_evidence_ids,("e2",))
    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","s"),wit("b","s")),(edge("1","a","b"),edge("2","b","a")))
    def test_missing_parent_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","s"),),(edge("1","missing","a"),))
    def test_self_edge_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","s"),),(edge("1","a","a"),))
    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","missing"),),())
    def test_duplicate_source_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),src("s")),(wit("a","s"),),())
    def test_duplicate_witness_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","s"),wit("a","s")),())
    def test_duplicate_edge_rejected(self):
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","s"),wit("b","s")),(edge("d","a","b"),edge("d","a","b")))
    def test_unknown_edge_kind_rejected(self):
        bad=Derivation("d","a","b","not-kind","declared","note")
        with self.assertRaises(ValueError):
            audit_evidence_provenance((src("s"),),(wit("a","s"),wit("b","s")),(bad,))
    def test_duplicate_evidence_id_rejected(self):
        with self.assertRaises(ValueError):
            assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(ev("e","a"),ev("e","a")))
    def test_unknown_evidence_witness_rejected(self):
        with self.assertRaises(ValueError):
            assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(ev("e","x"),))
    def test_reviewed_requires_reviewer_and_rationale(self):
        bad=EvidenceAssertion("e","a","claim",EvidenceStance.SUPPORTS,ReviewState.REVIEWED,(),"short")
        with self.assertRaises(ValueError):
            assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(bad,))
    def test_disputed_retained_as_unreviewed(self):
        bad=EvidenceAssertion("e","a","claim",EvidenceStance.SUPPORTS,ReviewState.DISPUTED,(),"disputed")
        x=assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(bad,))
        self.assertEqual(x.unreviewed_evidence_ids,("e",))
    def test_semantic_entailment_never_established(self):
        x=assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(ev("e","a"),))
        self.assertFalse(x.semantic_entailment_established)
    def test_claims_are_scoped(self):
        other=EvidenceAssertion("e","a","other",EvidenceStance.SUPPORTS,ReviewState.REVIEWED,("r1",),"Compared with the cited witness carefully.")
        x=assess_evidence_independence("claim",(src("s"),),(wit("a","s"),),(),(other,))
        self.assertEqual(x.reviewed_support_records,0)

if __name__=="__main__":
    unittest.main()
