import json
import unittest
from pathlib import Path
from prototype.yixiang_casebook_benchmark_adapter import convert_casebooks_to_pending_benchmark
from prototype.yixiang_benchmark import validate_dataset, evaluate_predictions

class M18Tests(unittest.TestCase):
    def load(self, name):
        path=Path(__file__).resolve().parents[1]/"data"/name
        return json.loads(path.read_text(encoding="utf-8"))
    def casebooks(self):
        return [self.load("yixiang_analogy_transfer_m17.v0.1.json"),self.load("yixiang_analogy_transfer_huainanzi_m17.v0.1.json"),self.load("yixiang_analogy_transfer_xunzi_m17.v0.1.json")]
    def test_all_m17_casebooks_convert_and_validate(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        validate_dataset(cases)
        self.assertEqual(len(cases),12)
    def test_every_case_remains_pending_review(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        self.assertTrue(all(c["label_status"]=="pending_review" for c in cases))
        self.assertTrue(all(c["reviewers"]==[] for c in cases))
    def test_placeholder_abstain_is_not_human_gold(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        self.assertTrue(all(c["gold_decision"]=="abstain" for c in cases))
        self.assertTrue(all("PENDING REVIEW" in c["gold_rationale"] for c in cases))
    def test_pending_cases_cannot_be_scored(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        predictions=[{"case_id":c["case_id"],"decision":"abstain"} for c in cases]
        with self.assertRaises(ValueError): evaluate_predictions(cases,predictions)
    def test_same_work_shares_independence_group(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        mozi=[c for c in cases if "《墨子·小取》" in c["independence_group"]]
        self.assertEqual(len({c["independence_group"] for c in mozi}),1)
    def test_all_cases_stay_exploratory_not_train_or_test(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        self.assertEqual({c["split_group"] for c in cases},{"exploratory"})
    def test_unknown_focus_is_rejected_not_silently_mapped(self):
        book=self.load("yixiang_analogy_transfer_m17.v0.1.json")
        book["cases"][0]["audit_focus"].append("unreviewed_new_axis")
        with self.assertRaises(ValueError): convert_casebooks_to_pending_benchmark([book])
    def test_missing_primary_source_is_rejected(self):
        book=self.load("yixiang_analogy_transfer_m17.v0.1.json")
        book["cases"][0]["source_ref"]=""
        with self.assertRaises(ValueError): convert_casebooks_to_pending_benchmark([book])
    def test_source_lineage_and_evidence_refs_are_preserved(self):
        cases=convert_casebooks_to_pending_benchmark(self.casebooks())
        first=cases[0]
        self.assertIn("mozi-xiaoqu",first["source_lineage"])
        self.assertTrue(first["evidence_refs"][0].startswith("casebook:"))
    def test_unmapped_case_does_not_create_partial_output(self):
        book=self.load("yixiang_analogy_transfer_m17.v0.1.json")
        book["cases"][1]["audit_focus"]=["not_mapped"]
        with self.assertRaises(ValueError): convert_casebooks_to_pending_benchmark([book])

if __name__=="__main__": unittest.main()