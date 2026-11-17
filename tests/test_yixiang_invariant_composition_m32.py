import unittest
from prototype.yixiang_invariant_composition_m32 import *

def inv(i="a", state="bounded", family="ctx"):
    return InvariantSnapshot(i,"relation",state,"scope",family,"obj-"+i,("m-"+i,))
def comp(**kw):
    d=dict(composition_id="cmp",member_ids=("a","b"),kind=CompositionKind.INTERACTION,
           scope="scope",context_family="ctx",boundary_conditions=("within-domain",))
    d.update(kw); return CompositionSpec(**d)
def ev(i, level, family=None):
    return EvidenceRecord(i,f"src-{family or i}","ctx",level,ReviewState.REVIEWED)
def claim(**kw):
    d=dict(claim_id="cl",composition_id="cmp",whole_level="system",
           operational_definition="joint response",predicted_observable="response-y",
           scope="scope",boundary_conditions=("within-domain",),
           member_evidence_refs=("ma","mb"),whole_evidence_refs=("w1","w2"),
           interaction_evidence_refs=("ix",),non_reducibility_argument="interaction changes output",
           counterexample_refs=(),competing_explanations=("additive model",),reviewer_ids=("r1",))
    d.update(kw); return EmergentInvariantClaim(**d)
def base(**kw):
    d=dict(invariants=(inv("a"),inv("b")),compositions=(comp(),),
           evidence=(ev("ma",EvidenceLevel.MEMBER),ev("mb",EvidenceLevel.MEMBER),
                     ev("w1",EvidenceLevel.WHOLE),ev("w2",EvidenceLevel.WHOLE),
                     ev("ix",EvidenceLevel.INTERACTION)))
    d.update(kw); return audit_invariant_composition_m32(**d)

class M32Tests(unittest.TestCase):
    def test_local_members_do_not_prove_whole(self):
        r=base()
        self.assertFalse(r.semantic_truth_established)
        self.assertEqual(r.disposition,CompositionDisposition.PROVISIONAL)
    def test_emergent_claim_requires_whole_and_member_evidence(self):
        r=base(claims=(claim(),))
        self.assertEqual(r.claim_dispositions,(("cl","review_required"),))
    def test_unknown_member_rejected(self):
        self.assertIn("unknown_composition_member:cmp:z",base(compositions=(comp(member_ids=("a","z")),)).issues)
    def test_duplicate_members_rejected(self):
        self.assertIn("duplicate_composition_member:cmp",base(compositions=(comp(member_ids=("a","a")),)).issues)
    def test_minimum_two_members(self):
        self.assertIn("composition_requires_two_members:cmp",base(compositions=(comp(member_ids=("a",)),)).issues)
    def test_member_context_family_must_match(self):
        self.assertIn("member_context_family_mismatch:cmp:b",base(invariants=(inv("a"),inv("b",family="other"))).issues)
    def test_unknown_state_rejected(self):
        self.assertIn("unknown_invariant_state:a",base(invariants=(inv("a",state="mystery"),inv("b"))).issues)
    def test_refuted_member_rejected(self):
        self.assertIn("refuted_member_in_composition_pool:a",base(invariants=(inv("a",state="refuted"),inv("b"))).issues)
    def test_unknown_dependency_endpoint(self):
        d=CompositionDependency("d","a","z","cmp",CompositionKind.INTERACTION,"why")
        self.assertIn("unknown_dependency_endpoint:d",base(dependencies=(d,)).issues)
    def test_dependency_endpoint_must_be_member(self):
        d=CompositionDependency("d","a","c","cmp",CompositionKind.INTERACTION,"why")
        self.assertIn("dependency_endpoint_outside_composition:d",base(invariants=(inv("a"),inv("b"),inv("c")),dependencies=(d,)).issues)
    def test_dependency_cycle_rejected(self):
        ds=(CompositionDependency("d1","a","b","cmp",CompositionKind.INTERACTION,"ab"),
            CompositionDependency("d2","b","a","cmp",CompositionKind.INTERACTION,"ba"))
        self.assertIn("composition_dependency_cycle",base(dependencies=ds).issues)
    def test_duplicate_dependency_id(self):
        d=CompositionDependency("d","a","b","cmp",CompositionKind.INTERACTION,"ab")
        self.assertIn("duplicate_dependency_id",base(dependencies=(d,d)).issues)
    def test_order_requires_permutation(self):
        self.assertIn("ordered_composition_requires_permutation:cmp",base(compositions=(comp(kind=CompositionKind.ORDERED,ordered_member_ids=("a",)),)).issues)
    def test_unordered_rejects_order(self):
        self.assertIn("order_declared_for_unordered_composition:cmp",base(compositions=(comp(ordered_member_ids=("a","b")),)).issues)
    def test_boundary_required(self):
        self.assertIn("incomplete_composition_scope_or_boundary:cmp",base(compositions=(comp(boundary_conditions=()),)).issues)
    def test_interaction_evidence_required_for_interaction(self):
        self.assertIn("interaction_evidence_required:cl",base(claims=(claim(interaction_evidence_refs=()),)).issues)
    def test_member_whole_evidence_overlap_rejected(self):
        self.assertIn("evidence_level_overlap:cl",base(claims=(claim(whole_evidence_refs=("ma",)),)).issues)
    def test_evidence_level_is_checked(self):
        self.assertIn("whole_evidence_level_mismatch:cl",base(claims=(claim(whole_evidence_refs=("ma",)),)).issues)
    def test_whole_evidence_shared_source_family_rejected(self):
        es=(ev("ma",EvidenceLevel.MEMBER),ev("mb",EvidenceLevel.MEMBER),
            ev("w1",EvidenceLevel.WHOLE,"same"),ev("w2",EvidenceLevel.WHOLE,"same"),
            ev("ix",EvidenceLevel.INTERACTION))
        self.assertIn("whole_evidence_shared_source_family:cl",base(evidence=es,claims=(claim(),)).issues)
    def test_claim_boundary_must_include_composition_boundary(self):
        self.assertIn("claim_scope_or_boundary_mismatch:cl",base(claims=(claim(boundary_conditions=()),)).issues)
    def test_competing_explanations_required(self):
        self.assertIn("claim_requires_competitors_and_reviewers:cl",base(claims=(claim(competing_explanations=()),)).issues)
    def test_reviewers_required(self):
        self.assertIn("claim_requires_competitors_and_reviewers:cl",base(claims=(claim(reviewer_ids=()),)).issues)
    def test_counterexample_must_be_evidenced(self):
        c=CompositionCounterexample("ce","cmp","whole failure",("missing",),ReviewState.REVIEWED)
        self.assertIn("unknown_counterexample_evidence:ce",base(counterexamples=(c,)).issues)
    def test_unresolved_reviewed_counterexample_blocks_claim(self):
        c=CompositionCounterexample("ce","cmp","whole failure",("w1",),ReviewState.REVIEWED)
        self.assertIn("unresolved_reviewed_counterexample:cl",base(claims=(claim(counterexample_refs=("ce",)),),counterexamples=(c,)).issues)
    def test_claim_must_account_for_recorded_counterexample(self):
        c=CompositionCounterexample("ce","cmp","whole failure",("w1",),ReviewState.UNREVIEWED)
        r=base(claims=(claim(),),counterexamples=(c,))
        self.assertEqual(r.disposition,CompositionDisposition.REVIEW_REQUIRED)
    def test_object_family_leakage(self):
        e=CompositionEvaluation("e",("x",),("x",),("a",),("b",),("c",),("d",),("s1",),("s2",),("member_prediction","local_composition","structural_relation","whole_level"),("acc",),"r",10,"cfg",("small",))
        self.assertIn("object_family_leakage:e",base(evaluations=(e,)).issues)
    def test_context_family_leakage(self):
        e=CompositionEvaluation("e",("x",),("y",),("a",),("a",),("c",),("d",),("s1",),("s2",),("member_prediction","local_composition","structural_relation","whole_level"),("acc",),"r",10,"cfg",("small",))
        self.assertIn("context_family_leakage:e",base(evaluations=(e,)).issues)
    def test_composition_leakage(self):
        e=CompositionEvaluation("e",("x",),("y",),("a",),("b",),("c",),("c",),("s1",),("s2",),("member_prediction","local_composition","structural_relation","whole_level"),("acc",),"r",10,"cfg",("small",))
        self.assertIn("composition_leakage:e",base(evaluations=(e,)).issues)
    def test_source_family_leakage(self):
        e=CompositionEvaluation("e",("x",),("y",),("a",),("b",),("c",),("d",),("s",),("s",),("member_prediction","local_composition","structural_relation","whole_level"),("acc",),"r",10,"cfg",("small",))
        self.assertIn("source_family_leakage:e",base(evaluations=(e,)).issues)
    def test_required_baselines(self):
        e=CompositionEvaluation("e",("x",),("y",),("a",),("b",),("c",),("d",),("s1",),("s2",),("member_prediction",),("acc",),"r",10,"cfg",("small",))
        self.assertIn("missing_composition_baselines:e",base(evaluations=(e,)).issues)
    def test_evaluation_configuration_required(self):
        e=CompositionEvaluation("e",("x",),("y",),("a",),("b",),("c",),("d",),("s1",),("s2",),("member_prediction","local_composition","structural_relation","whole_level"),("acc",),"r",10,"",("small",))
        self.assertIn("incomplete_composition_evaluation:e",base(evaluations=(e,)).issues)
    def test_non_claim_does_not_assert_emergence(self):
        self.assertFalse(base().semantic_truth_established)

if __name__ == "__main__": unittest.main()
