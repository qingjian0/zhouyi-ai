import unittest
from prototype.yixiang_benchmark import validate_case,validate_dataset,evaluate_predictions,group_leakage
def make_case(cid,decision="accept",lineage=("work-a:edition-1",),split="train",scope=("context fixed",)):
 return {"case_id":cid,"source_lineage":list(lineage),"source_status":"synthetic_fixture","target_claim":"Test whether a proposed relation transfers to a target claim.","relation_families":["structural"],"shared_basis":["same relation topology"],"non_shared_basis":["different physical substrate"],"scope_conditions":list(scope),"required_invariants":["edge direction preserved"],"known_counterexamples":[],"causal_status":"unknown","evidence_refs":["fixture:"+cid],"independence_group":"fixture-group-"+cid,"gold_decision":decision,"gold_rationale":"Synthetic gold label; uncertainty is documented for abstention.","reviewers":["reviewer-a","reviewer-b"],"split_group":split}
class BenchmarkContractTests(unittest.TestCase):
 def test_valid_case_and_dataset(self): validate_case(make_case("a")); validate_dataset([make_case("a"),make_case("b")])
 def test_unknown_field_rejected(self):
  c=make_case("a"); c["similarity_score"]=0.9
  with self.assertRaisesRegex(ValueError,"unknown fields"): validate_case(c)
 def test_conditional_requires_scope(self):
  with self.assertRaisesRegex(ValueError,"scope_conditions"): validate_case(make_case("a","conditional",scope=()))
 def test_synthetic_requires_fixture_reference(self):
  c=make_case("a"); c["evidence_refs"]=["paper:123"]
  with self.assertRaisesRegex(ValueError,"fixture:"): validate_case(c)
 def test_duplicate_ids_rejected(self):
  with self.assertRaisesRegex(ValueError,"globally unique"): validate_dataset([make_case("a"),make_case("a")])
 def test_missing_prediction_counts_as_abstain(self):
  cases=[make_case("a","accept"),make_case("b","reject"),make_case("c","abstain")]
  r=evaluate_predictions(cases,[{"case_id":"a","decision":"accept"},{"case_id":"b","decision":"accept"}])
  self.assertEqual(r["n"],3); self.assertAlmostEqual(r["accuracy"],2/3); self.assertEqual(r["missing_predictions"],1); self.assertEqual(r["confusion_matrix"]["abstain"]["abstain"],1)
 def test_unknown_and_duplicate_predictions_rejected(self):
  with self.assertRaisesRegex(ValueError,"unknown case_id"): evaluate_predictions([make_case("a")],[{"case_id":"x","decision":"accept"}])
  with self.assertRaisesRegex(ValueError,"duplicate prediction"): evaluate_predictions([make_case("a")],[{"case_id":"a","decision":"accept"},{"case_id":"a","decision":"reject"}])
 def test_lineage_leakage_detected(self):
  cs=[make_case("a",lineage=("shared-work-edition",),split="train"),make_case("b",lineage=("shared-work-edition",),split="test")]
  self.assertEqual(group_leakage(cs)["leakage_groups"],["shared-work-edition"])
 def test_gold_requires_two_reviewers(self):
  c=make_case("a"); c["reviewers"]=["only-one"]
  with self.assertRaisesRegex(ValueError,"two independent reviewers"): validate_case(c)
 def test_abstention_is_valid_gold(self): validate_case(make_case("a","abstain"))
if __name__=="__main__": unittest.main()
