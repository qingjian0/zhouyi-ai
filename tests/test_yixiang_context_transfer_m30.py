import unittest
from prototype.yixiang_context_transfer_m30 import *
def ctx(i): return ContextProfile(i,"v1","task","env","observer","bounded scope")
def pair(): return ContextPair("p","c1","c2",("environment",))
def ev(i,b=EvidenceBasis.MORPHOLOGY,reviewed=True,contexts=("c1","c2")): return EvidenceRecord(i,contexts,b,"controlled comparison","same scope",reviewed)
def perm(kind=TransferKind.FEATURE,decision=TransferDecision.ALLOW,refs=("e",),constraints=(),counterexamples=(),reviewers=("reviewer",)):
 return TransferPermission("t","p",kind,decision,refs,constraints,counterexamples,"human adjudication",reviewers)
def assessment(outcome=StabilityOutcome.STABLE,refs=("e",),counterexamples=(),reviewers=("reviewer",)):
 return StabilityAssessment("a","p",StabilityDimension.MORPHOLOGY,outcome,refs,counterexamples,"paired observation","bounded scope","reviewed comparison",reviewers)
class M30Tests(unittest.TestCase):
 def run_audit(self,evs=(ev("e"),),perms=(),assess=(),evaluation=None,shifts=(),pairs=(pair(),),contexts=(ctx("c1"),ctx("c2"))):
  return audit_context_transfer(contexts,pairs,evs,assess,perms,shifts,evaluation)
 def test_valid_feature_transfer(self): self.assertTrue(self.run_audit(perms=(perm(),)).valid)
 def test_same_context_rejected(self): self.assertIn("same_context_is_not_transfer:p",self.run_audit(pairs=(ContextPair("p","c1","c1",("none",)),)).issues)
 def test_unknown_context_endpoint(self): self.assertIn("invalid_context_pair:p",self.run_audit(pairs=(ContextPair("p","c1","x",("env",)),)).issues)
 def test_missing_shift_dimension(self): self.assertIn("missing_shift_dimensions:p",self.run_audit(pairs=(ContextPair("p","c1","c2",()),)).issues)
 def test_duplicate_context(self): self.assertIn("invalid_or_duplicate_context",self.run_audit(contexts=(ctx("c1"),ctx("c1"))).issues)
 def test_missing_assessment_evidence(self): self.assertIn("missing_or_unknown_assessment_evidence:a",self.run_audit(assess=(assessment(refs=()),)).issues)
 def test_assessment_wrong_pair(self):
  a=StabilityAssessment("a","x",StabilityDimension.MORPHOLOGY,StabilityOutcome.WEAKENED,("e",),(),"m","s","r")
  self.assertIn("unknown_assessment_pair:a",self.run_audit(assess=(a,)).issues)
 def test_assessment_evidence_context_mismatch(self): self.assertIn("assessment_evidence_context_mismatch:a",self.run_audit(evs=(ev("e",contexts=("c1x",)),),assess=(assessment(),)).issues)
 def test_stable_requires_reviewers(self): self.assertIn("stable_claim_requires_reviewers:a",self.run_audit(assess=(assessment(reviewers=()),)).issues)
 def test_stable_counterexample_rejected(self): self.assertIn("stable_claim_has_unresolved_counterexamples:a",self.run_audit(assess=(assessment(counterexamples=("ce",)),)).issues)
 def test_attribute_not_mechanism_evidence(self): self.assertIn("insufficient_basis_for_transfer_kind:t",self.run_audit(evs=(ev("e",EvidenceBasis.ATTRIBUTE),),perms=(perm(TransferKind.MECHANISM),)).issues)
 def test_mechanism_requires_mechanism_evidence(self): self.assertIn("mechanism_transfer_requires_mechanism_evidence:t",self.run_audit(evs=(ev("e",EvidenceBasis.STRUCTURAL_RELATION),),perms=(perm(TransferKind.MECHANISM),)).issues)
 def test_function_requires_function_evidence(self): self.assertIn("insufficient_basis_for_transfer_kind:t",self.run_audit(perms=(perm(TransferKind.FUNCTION),)).issues)
 def test_system_requires_system_evidence(self): self.assertIn("system_transfer_requires_system_evidence:t",self.run_audit(evs=(ev("e",EvidenceBasis.MECHANISM),),perms=(perm(TransferKind.SYSTEM),)).issues)
 def test_unreviewed_evidence_cannot_authorize(self): self.assertIn("transfer_requires_reviewed_evidence:t",self.run_audit(evs=(ev("e",reviewed=False),),perms=(perm(),)).issues)
 def test_permission_requires_reviewer(self): self.assertIn("transfer_permission_requires_adjudication:t",self.run_audit(perms=(perm(reviewers=()),)).issues)
 def test_conditional_requires_constraints(self): self.assertIn("conditional_transfer_requires_constraints:t",self.run_audit(perms=(perm(decision=TransferDecision.CONDITIONAL),)).issues)
 def test_counterexample_blocks_unconditional_allow(self): self.assertIn("counterexamples_require_conditional_or_blocked:t",self.run_audit(perms=(perm(counterexamples=("ce",)),)).issues)
 def test_blocked_not_allowed(self):
  r=self.run_audit(perms=(perm(decision=TransferDecision.BLOCK),)); self.assertEqual(r.blocked_permissions,("t",)); self.assertEqual(r.allowed_permissions,())
 def test_review_not_allowed(self): self.assertEqual(self.run_audit(perms=(perm(decision=TransferDecision.REVIEW),)).blocked_permissions,("t",))
 def test_shift_requires_evidence(self):
  s=ShiftProfile("s","p",("environment",),"large",(),"shift")
  self.assertIn("incomplete_shift_profile:s",self.run_audit(shifts=(s,)).issues)
 def test_shift_pair_must_exist(self):
  s=ShiftProfile("s","x",("environment",),"large",("e",),"shift")
  self.assertIn("unknown_shift_pair:s",self.run_audit(shifts=(s,)).issues)
 def test_object_leakage(self):
  e=TransferEvaluation("x","object",("o",),("o",),("a",),("b",),("feature_similarity","classification","structural_relation"),("accuracy",),False,(),("small sample",))
  self.assertIn("object_leakage_across_split",self.run_audit(evaluation=e).issues)
 def test_context_family_leakage(self):
  e=TransferEvaluation("x","context_family",("o1",),("o2",),("f",),("f",),("feature_similarity","classification","structural_relation"),("accuracy",),False,(),("limits",))
  self.assertIn("context_family_leakage_across_split",self.run_audit(evaluation=e).issues)
 def test_missing_baseline(self):
  e=TransferEvaluation("x","object",("o1",),("o2",),("a",),("b",),("feature_similarity",),("accuracy",),False,(),("limits",))
  self.assertIn("missing_required_baseline",self.run_audit(evaluation=e).issues)
 def test_missing_metrics(self):
  e=TransferEvaluation("x","object",("o1",),("o2",),("a",),("b",),("feature_similarity","classification","structural_relation"),(),False,(),("limits",))
  self.assertIn("missing_evaluation_metrics",self.run_audit(evaluation=e).issues)
 def test_no_results_no_empirical_stability_claim(self):
  e=TransferEvaluation("x","object",("o1",),("o2",),("a",),("b",),("feature_similarity","classification","structural_relation"),("accuracy",),False,(),("limits",))
  self.assertTrue(self.run_audit(evaluation=e).valid); self.assertEqual(self.run_audit(evaluation=e).stability_claims,())
 def test_results_require_refs(self):
  e=TransferEvaluation("x","object",("o1",),("o2",),("a",),("b",),("feature_similarity","classification","structural_relation"),("accuracy",),True,(),("limits",))
  self.assertIn("recorded_results_require_result_refs",self.run_audit(evaluation=e).issues)
 def test_refs_without_results(self):
  e=TransferEvaluation("x","object",("o1",),("o2",),("a",),("b",),("feature_similarity","classification","structural_relation"),("accuracy",),False,("r",),("limits",))
  self.assertIn("result_refs_without_results",self.run_audit(evaluation=e).issues)
 def test_semantic_truth_not_established(self): self.assertFalse(self.run_audit(perms=(perm(),)).semantic_validity_established)
 def test_duplicate_evidence_rejected(self): self.assertIn("duplicate_evidence_id",self.run_audit(evs=(ev("e"),ev("e"))).issues)
 def test_duplicate_reference_not_independent_support(self): self.assertTrue(self.run_audit(perms=(perm(refs=("e","e")),)).valid)
 def test_assessment_requires_both_contexts(self):
  a=StabilityAssessment("a","p",StabilityDimension.MORPHOLOGY,StabilityOutcome.WEAKENED,("e",),(),"m","s","r")
  self.assertIn("assessment_evidence_must_cover_both_contexts:a",self.run_audit(evs=(ev("e",contexts=("c1",)),),assess=(a,)).issues)
 def test_permission_requires_both_contexts(self):
  self.assertIn("permission_evidence_must_cover_both_contexts:t",self.run_audit(evs=(ev("e",contexts=("c1",)),),perms=(perm(),)).issues)
 def test_stable_requires_reviewed_evidence(self):
  self.assertIn("stable_claim_requires_reviewed_evidence:a",self.run_audit(evs=(ev("e",reviewed=False),),assess=(assessment(),)).issues)
 def test_duplicate_assessment_id_not_silently_accepted(self):
  a=assessment()
  r=self.run_audit(assess=(a,a))
  self.assertIn("duplicate_assessment_id",r.issues)
if __name__=="__main__": unittest.main()
