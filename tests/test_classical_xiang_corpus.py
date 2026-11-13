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
 def test_exact_locator_required(self):
  r=dict(self.records[0]); r["locator"]={"chapter":"系辞上传"}
  with self.assertRaisesRegex(ValueError,"exact chapter"): validate_record(r)
 def test_model_cannot_self_review(self):
  r=dict(self.records[0]); r["source_type"]="model_generated"; r["review_status"]="reviewed"
  with self.assertRaisesRegex(ValueError,"self-certify"): validate_record(r)
 def test_duplicate_claim_id_rejected(self):
  r=dict(self.records[0]); r["claims"]=[dict(r["claims"][0]),dict(r["claims"][0])]
  with self.assertRaisesRegex(ValueError,"duplicate"): validate_record(r)
if __name__=="__main__": unittest.main()
