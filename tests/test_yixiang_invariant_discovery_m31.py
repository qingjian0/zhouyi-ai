import unittest
from prototype.yixiang_invariant_discovery_m31 import *
def cx(i,f=None): return Context(i,f or i,"v1","task","env","subject","scope")
def cand(): return InvariantCandidate("c",InvariantLevel.FEATURE,"operational definition","observable","relation","scope",("condition A",),(),"prereg-1",("reviewer",))
def ev(i,context="x"): return Evidence(i,"source-family",context,"measurement",True)
def obs(i,context="x",result=ObservationResult.PRESERVED,review=ReviewState.REVIEWED):
 return Observation(i,"c",context,"object-"+context,result,("e"+i,),"measurement",review)
def test(kind=TestKind.FALSIFICATION,context="y",reviewers=("reviewer",)):
 return FalsificationTest("t","c",kind,(context,),"controlled perturbation","failure expected if boundary crossed","observed outcome",("et",),reviewers)
def audit(contexts=(cx("x"),cx("y")),candidates=(cand(),),evidence=(ev("eo","x"),ev("et","y")),observations=(),tests=(),cex=(),evaluations=()):
 return audit_invariant_discovery(contexts,candidates,evidence,observations,tests,cex,evaluations)
class M31Tests(unittest.TestCase):
 def test_candidate_is_not_proven(self): self.assertEqual(audit().candidate_states,(("c","candidate"),))
 def test_candidate_requires_preregistration(self):
  c=InvariantCandidate("c",InvariantLevel.FEATURE,"d","o","r","s",("b",),(),"")
  self.assertIn("incomplete_candidate:c",audit(candidates=(c,)).issues)
 def test_candidate_requires_boundary(self):
  c=InvariantCandidate("c",InvariantLevel.FEATURE,"d","o","r","s",(),(),"p")
  self.assertIn("candidate_requires_explicit_boundary_conditions:c",audit(candidates=(c,)).issues)
 def test_duplicate_context_rejected(self): self.assertIn("duplicate_context_id",audit(contexts=(cx("x"),cx("x"))).issues)
 def test_unknown_observation_context(self):
  o=Observation("o","c","z","obj",ObservationResult.PRESERVED,("eo",),"m",ReviewState.REVIEWED)
  self.assertIn("unknown_observation_context:o",audit(observations=(o,)).issues)
 def test_observation_evidence_must_match_context(self):
  o=Observation("o","c","y","obj",ObservationResult.PRESERVED,("eo",),"m",ReviewState.REVIEWED)
  self.assertIn("observation_evidence_context_mismatch:o",audit(observations=(o,)).issues)
 def test_unknown_evidence_rejected(self):
  o=Observation("o","c","x","obj",ObservationResult.PRESERVED,("missing",),"m",ReviewState.REVIEWED)
  self.assertIn("unknown_observation_evidence:o",audit(observations=(o,)).issues)
 def test_duplicate_observation_id(self):
  o=obs("1")
  self.assertIn("duplicate_observation_id",audit(observations=(o,o)).issues)
 def test_only_one_context_remains_candidate(self): self.assertEqual(audit(observations=(obs("1"),)).candidate_states[0][1],"candidate")
 def test_two_contexts_without_falsification_inconclusive(self):
  self.assertEqual(audit(observations=(obs("1","x"),obs("2","y"))).candidate_states[0][1],"inconclusive")
 def test_falsification_coverage_required(self):
  self.assertEqual(audit(observations=(obs("1","x"),obs("2","y"))).candidate_states[0][1],"inconclusive")
 def test_adversarial_test_requires_reviewer(self):
  self.assertIn("adversarial_test_requires_reviewers:t",audit(tests=(test(reviewers=()),)).issues)
 def test_test_requires_evidence(self):
  t=FalsificationTest("t","c",TestKind.FALSIFICATION,("y",),"perturb","failure","outcome",(),("r",))
  self.assertIn("incomplete_falsification_test:t",audit(tests=(t,)).issues)
 def test_test_evidence_context_mismatch(self):
  t=FalsificationTest("t","c",TestKind.FALSIFICATION,("y",),"perturb","failure","outcome",("eo",),("r",))
  self.assertIn("test_evidence_context_mismatch:t",audit(tests=(t,)).issues)
 def test_unknown_test_candidate(self):
  t=FalsificationTest("t","z",TestKind.FALSIFICATION,("y",),"p","f","o",("et",),("r",))
  self.assertIn("unknown_test_candidate:t",audit(tests=(t,)).issues)
 def test_duplicate_test_id(self):
  t=test()
  self.assertIn("duplicate_test_id",audit(tests=(t,t)).issues)
 def test_reviewed_failure_refutes_candidate(self):
  o1=obs("1","x"); o2=obs("2","y",ObservationResult.FAILED)
  self.assertEqual(audit(observations=(o1,o2),tests=(test(),)).candidate_states[0][1],"refuted")
 def test_reviewed_reversal_refutes_candidate(self):
  o1=obs("1","x"); o2=obs("2","y",ObservationResult.REVERSED)
  self.assertEqual(audit(observations=(o1,o2),tests=(test(),)).candidate_states[0][1],"refuted")
 def test_unreviewed_failure_does_not_auto_refute(self):
  o1=obs("1","x"); o2=obs("2","y",ObservationResult.FAILED,ReviewState.UNREVIEWED)
  self.assertEqual(audit(observations=(o1,o2),tests=(test(),)).candidate_states[0][1],"inconclusive")
 def test_reviewed_counterexample_refutes(self):
  c=Counterexample("ce","c","y","obj","counter observation",("et",),ReviewState.REVIEWED)
  self.assertEqual(audit(observations=(obs("1","x"),obs("2","y")),tests=(test(),),cex=(c,)).candidate_states[0][1],"refuted")
 def test_duplicate_counterexample_id(self):
  c=Counterexample("ce","c","y","obj","counter",("et",),ReviewState.REVIEWED)
  self.assertIn("duplicate_counterexample_id",audit(cex=(c,c)).issues)
 def test_unreviewed_counterexample_not_confirmed_refutation(self):
  c=Counterexample("ce","c","y","obj","counter",("et",),ReviewState.UNREVIEWED)
  self.assertNotEqual(audit(observations=(obs("1","x"),obs("2","y")),tests=(test(),),cex=(c,)).candidate_states[0][1],"refuted")
 def test_counterexample_requires_evidence(self):
  c=Counterexample("ce","c","y","obj","counter",(),ReviewState.REVIEWED)
  self.assertIn("incomplete_counterexample:ce",audit(cex=(c,)).issues)
 def test_falsification_test_unknown_context(self):
  t=FalsificationTest("t","c",TestKind.FALSIFICATION,("z",),"p","f","o",("et",),("r",))
  self.assertIn("invalid_test_contexts:t",audit(tests=(t,)).issues)
 def test_evaluation_object_leakage(self):
  e=Evaluation("ev",("o",),("o",),("train",),("test",),("hold",),("feature_similarity","classification","structural_relation"),("accuracy",),"r",10,"bootstrap",("small",))
  self.assertIn("object_leakage:ev",audit(evaluations=(e,)).issues)
 def test_evaluation_context_family_leakage(self):
  e=Evaluation("ev",("o1",),("o2",),("fam",),("fam",),("hold",),("feature_similarity","classification","structural_relation"),("acc",),"r",10,"bootstrap",("small",))
  self.assertIn("context_family_leakage:ev",audit(evaluations=(e,)).issues)
 def test_evaluation_requires_three_baselines(self):
  e=Evaluation("ev",("o1",),("o2",),("train",),("test",),("hold",),("feature_similarity",),("acc",),"r",10,"bootstrap",("small",))
  self.assertIn("missing_baselines:ev",audit(evaluations=(e,)).issues)
 def test_evaluation_requires_results_and_metrics(self):
  e=Evaluation("ev",("o1",),("o2",),("train",),("test",),("hold",),("feature_similarity","classification","structural_relation"),(),"",0,"",())
  self.assertIn("incomplete_evaluation_record:ev",audit(evaluations=(e,)).issues)
 def test_evaluation_requires_limitations(self):
  e=Evaluation("ev",("o1",),("o2",),("train",),("test",),("hold",),("feature_similarity","classification","structural_relation"),("acc",),"r",10,"bootstrap",())
  self.assertIn("evaluation_limitations_required:ev",audit(evaluations=(e,)).issues)
 def test_semantic_truth_never_established(self): self.assertFalse(audit().semantic_truth_established)
 def test_unknown_candidate_counterexample_endpoint(self):
  c=Counterexample("ce","z","y","obj","counter",("et",),ReviewState.REVIEWED)
  self.assertIn("invalid_counterexample_endpoint:ce",audit(cex=(c,)).issues)
 def test_replication_is_not_falsification_coverage(self):
  t=test(kind=TestKind.REPLICATION)
  self.assertEqual(audit(tests=(t,)).falsification_coverage,(("c",0),))
if __name__=="__main__": unittest.main()
