import unittest, json
from pathlib import Path
from prototype.yixiang_benchmark import validate_case,validate_dataset,evaluate_predictions,group_leakage
def make_case(cid,decision="accept",lineage=("work-a:edition-1",),split="train",scope=("context fixed",)):
 return {"case_id":cid,"source_lineage":list(lineage),"source_status":"synthetic_fixture","target_claim":"Test whether a proposed relation transfers to a target claim.","relation_families":["structural"],"shared_basis":["same relation topology"],"non_shared_basis":["different physical substrate"],"scope_conditions":list(scope),"required_invariants":["edge direction preserved"],"known_counterexamples":[],"causal_status":"unknown","evidence_refs":["fixture:"+cid],"independence_group":"fixture-group-"+cid,"gold_decision":decision,"gold_rationale":"Synthetic gold label; uncertainty is documented for abstention.","label_status":"fixture_expected","reviewers":[],"split_group":split}
class BenchmarkContractTests(unittest.TestCase):
 def test_valid_case_and_dataset(self): validate_case(make_case("a")); validate_dataset([make_case("a"),make_case("b")])
 def test_committed_synthetic_fixture_dataset(self):
  root=Path(__file__).resolve().parents[1]
  cases=json.loads((root/"data/yixiang_benchmark_synthetic.v0.1.json").read_text(encoding="utf-8"))
  validate_dataset(cases)
  self.assertEqual(len(cases),12)
  self.assertEqual({c["split_group"] for c in cases},{"train","dev","test"})
 def test_invalid_split_group_rejected(self):
  c=make_case("a",split="validation")
  with self.assertRaisesRegex(ValueError,"split_group"): validate_dataset([c])
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
 def test_fixture_scoring_requires_explicit_opt_in(self):
  with self.assertRaisesRegex(ValueError,"allow_fixture_expected"):
   evaluate_predictions([make_case("a")],[])
  result=evaluate_predictions([make_case("a")],[],allow_fixture_expected=True)
  self.assertEqual(result["evaluation_basis"],"fixture_expected")
 def test_pending_review_never_scored_as_gold(self):
  c=make_case("a"); c["source_status"]="critical_edition"; c["label_status"]="pending_review"; c["reviewers"]=[]
  with self.assertRaisesRegex(ValueError,"pending_review"): evaluate_predictions([c],[])
 def test_adjudicated_gold_is_scoreable(self):
  c=make_case("a"); c["source_status"]="critical_edition"; c["label_status"]="adjudicated"; c["reviewers"]=["r1","r2"]
  result=evaluate_predictions([c],[{"case_id":"a","decision":"accept"}])
  self.assertEqual(result["evaluation_basis"],"adjudicated")
 def test_mixed_label_status_populations_rejected(self):
  a=make_case("a"); b=make_case("b"); b["source_status"]="critical_edition"; b["label_status"]="pending_review"; b["reviewers"]=[]
  with self.assertRaisesRegex(ValueError,"pending_review"): evaluate_predictions([a,b],[])
 def test_accept_requires_shared_basis(self):
  c=make_case("a"); c["shared_basis"]=[]
  with self.assertRaisesRegex(ValueError,"shared_basis"): validate_case(c)
 def test_missing_prediction_counts_as_abstain(self):
  cases=[make_case("a","accept"),make_case("b","reject"),make_case("c","abstain")]
  r=evaluate_predictions(cases,[{"case_id":"a","decision":"accept"},{"case_id":"b","decision":"accept"}],allow_fixture_expected=True)
  self.assertEqual(r["n"],3); self.assertAlmostEqual(r["accuracy"],2/3); self.assertEqual(r["missing_predictions"],1); self.assertEqual(r["confusion_matrix"]["abstain"]["abstain"],1); self.assertAlmostEqual(r["abstention_coverage"],1/3); self.assertAlmostEqual(r["selective_coverage"],2/3); self.assertAlmostEqual(r["selective_risk"],0.5); self.assertIn("macro_f1",r["by_relation_family"]["structural"]); self.assertIn("confusion_matrix",r["by_relation_family"]["structural"])
 def test_unknown_and_duplicate_predictions_rejected(self):
  with self.assertRaisesRegex(ValueError,"unknown case_id"): evaluate_predictions([make_case("a")],[{"case_id":"x","decision":"accept"}],allow_fixture_expected=True)
  with self.assertRaisesRegex(ValueError,"duplicate prediction"): evaluate_predictions([make_case("a")],[{"case_id":"a","decision":"accept"},{"case_id":"a","decision":"reject"}],allow_fixture_expected=True)
 def test_lineage_leakage_detected(self):
  cs=[make_case("a",lineage=("shared-work-edition",),split="train"),make_case("b",lineage=("shared-work-edition",),split="test")]
  self.assertEqual(group_leakage(cs)["leakage_groups"],["shared-work-edition"])
 def test_malformed_enum_types_raise_value_error(self):
  for field in ("source_status","causal_status","gold_decision"):
   c=make_case("a"); c[field]=[]
   with self.subTest(field=field):
    with self.assertRaises(ValueError): validate_case(c)
  with self.assertRaises(ValueError):
   evaluate_predictions([make_case("a")],[{"case_id":"a","decision":[]}])
 def test_synthetic_fixture_cannot_claim_reviewers(self):
  c=make_case("a"); c["reviewers"]=["reviewer-a","reviewer-b"]
  with self.assertRaisesRegex(ValueError,"cannot claim human adjudication"): validate_case(c)
 def test_adjudicated_labels_require_two_reviewers(self):
  c=make_case("a"); c["source_status"]="critical_edition"; c["label_status"]="adjudicated"; c["reviewers"]=["reviewer-a"]
  with self.assertRaisesRegex(ValueError,"two distinct reviewer IDs"): validate_case(c)
  c["reviewers"]=["reviewer-a","reviewer-b"]; validate_case(c)
 def test_invalid_label_status_and_group_key_rejected(self):
  c=make_case("a"); c["label_status"]=[]
  with self.assertRaises(ValueError): validate_case(c)
  with self.assertRaisesRegex(ValueError,"unsupported grouping field"): group_leakage([make_case("a")],group_field="split_group")
 def test_independence_group_leakage_detected(self):
  a=make_case("a",split="train"); b=make_case("b",split="test")
  a["independence_group"]=b["independence_group"]="same-source-family"
  self.assertEqual(group_leakage([a,b],group_field="independence_group")["leakage_count"],1)
 def test_abstention_is_valid_gold(self):
  validate_case(make_case("a","abstain"))
  c=make_case("short","abstain"); c["gold_rationale"]="unclear"
  with self.assertRaisesRegex(ValueError,"abstain rationale"):
   validate_case(c)
 def test_schema_declares_python_fixture_and_abstention_constraints(self):
  root=Path(__file__).resolve().parents[1]
  schema=json.loads((root/"schemas/yixiang-benchmark-case.schema.json").read_text(encoding="utf-8"))
  rendered=json.dumps(schema)
  self.assertIn('"minContains": 1',rendered)
  self.assertIn('"minLength": 20',rendered)
if __name__=="__main__": unittest.main()
