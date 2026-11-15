import json, unittest
from pathlib import Path
from prototype.classical_xiang_corpus import validate_record
ROOT=Path(__file__).resolve().parents[1]
class CorpusTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.records=json.loads((ROOT/"data/classical_xiang_corpus.v0.1.json").read_text(encoding="utf-8"))
 def test_seed_records_validate(self):
  self.assertGreaterEqual(len(self.records),3)
  for r in self.records: validate_record(r)
 def test_record_and_claim_ids_unique(self):
  self.assertEqual(len({r["record_id"] for r in self.records}),len(self.records))
  ids=[c["claim_id"] for r in self.records for c in r["claims"]]
  self.assertEqual(len(ids),len(set(ids)))
 def test_duplicate_xunzi_digital_witness_is_consolidated_without_losing_claims(self):
  matches=[r for r in self.records if r["work"]["title"]=="荀子·正名篇" and r["text"]=="正名而期，质请而喻，辨异而不过，推类而不悖。"]
  self.assertEqual(len(matches),1)
  self.assertEqual(len(matches[0]["claims"]),3)
  self.assertTrue(any("不作为第二个独立版本" in note for note in matches[0].get("variant_notes",[])))
 def test_concept_tags_are_required_and_controlled(self):
  r=dict(self.records[0]); r["concept_tags"]=["invented_universal_category"]
  with self.assertRaisesRegex(ValueError,"concept_tags"): validate_record(r)
 def test_method_families_are_required_and_controlled(self):
  r=dict(self.records[0]); r["method_families"]=["ancient_universal_logic"]
  with self.assertRaisesRegex(ValueError,"method_families"): validate_record(r)
 def test_exact_locator_required(self):
  r=dict(self.records[0]); r["locator"]={"chapter":"系辞上传"}
  with self.assertRaisesRegex(ValueError,"exact chapter"): validate_record(r)
 def test_invalid_witness_url_rejected(self):
  r=dict(self.records[0]); r["witness"]=dict(r["witness"]); r["witness"]["url"]="not-a-url"
  with self.assertRaisesRegex(ValueError,"HTTP"):
   validate_record(r)
 def test_invalid_access_date_rejected(self):
  r=dict(self.records[0]); r["witness"]=dict(r["witness"]); r["witness"]["access_date"]="2026-13-40"
  with self.assertRaisesRegex(ValueError,"ISO date"):
   validate_record(r)
 def test_unknown_witness_kind_rejected(self):
  r=dict(self.records[0]); r["witness"]=dict(r["witness"]); r["witness"]["witness_kind"]="invented"
  with self.assertRaisesRegex(ValueError,"witness_kind"):
   validate_record(r)
 def test_model_cannot_self_review(self):
  r=dict(self.records[0]); r["source_type"]="model_generated"; r["review_status"]="reviewed"
  with self.assertRaisesRegex(ValueError,"self-certify"): validate_record(r)
 def test_duplicate_claim_id_rejected(self):
  r=dict(self.records[0]); r["claims"]=[dict(r["claims"][0]),dict(r["claims"][0])]
  with self.assertRaisesRegex(ValueError,"duplicate"): validate_record(r)
 def test_optional_analogy_boundary_fields_are_validated(self):
  r=dict(self.records[0]); r["claims"]=[dict(r["claims"][0])]
  r["claims"][0].update({"relation_family":"functional","causal_status":"not_claimed","shared_basis":["shared role"],"non_shared_basis":["different mechanism"],"scope_conditions":["textual context"]})
  validate_record(r)
  r["claims"][0]["relation_family"]="made_up"
  with self.assertRaisesRegex(ValueError,"relation_family"): validate_record(r)
 def test_unknown_causal_status_is_rejected(self):
  r=dict(self.records[0]); r["claims"]=[dict(r["claims"][0])]
  r["claims"][0]["causal_status"]="proven_cause"
  with self.assertRaisesRegex(ValueError,"causal_status"): validate_record(r)
 def test_reasoning_operations_are_controlled(self):
  r=dict(self.records[0]); r["claims"]=[dict(self.records[0]["claims"][0])]
  r["claims"][0]["reasoning_operations"]=["observe","compare"]
  validate_record(r)
  r["claims"][0]["reasoning_operations"]=["magic"]
  with self.assertRaisesRegex(ValueError,"reasoning_operations"): validate_record(r)

 def test_malformed_controlled_fields_raise_value_error(self):
  for field,value in (("period",[]),("source_type",{}),("review_status",[]),("method_families",[{}]),("concept_tags",[[]])):
   r=dict(self.records[0]); r[field]=value
   with self.subTest(field=field):
    with self.assertRaises(ValueError): validate_record(r)
  r=dict(self.records[0]); r["claims"]=[dict(self.records[0]["claims"][0])]
  r["claims"][0]["reasoning_operations"]=[{}]
  with self.assertRaises(ValueError): validate_record(r)

if __name__=="__main__": unittest.main()
