import json
import unittest
from pathlib import Path
from prototype.yixiang_contrastive_pair_metrics import evaluate_contrastive_pairs

class M21Tests(unittest.TestCase):
    def cases(self):
        path=Path(__file__).resolve().parents[1]/"data"/"yixiang_analogy_transfer_adversarial_m20.v0.1.json"
        return json.loads(path.read_text(encoding="utf-8"))
    def gold_predictions(self):
        return [{"case_id":c["case_id"],"decision":c["gold_decision"]} for c in self.cases()]
    def score(self,cases,predictions):
        return evaluate_contrastive_pairs(cases,predictions,allow_fixture_expected=True)
    def test_perfect_contrastive_predictions(self):
        r=self.score(self.cases(),self.gold_predictions())
        self.assertEqual(r["pair_count"],8)
        self.assertEqual(r["pair_exact_accuracy"],1.0)
        self.assertEqual(r["decision_flip_sensitivity"],1.0)
        self.assertEqual(r["submitted_pairs"],8)
        self.assertEqual(r["collapsed_pair_count"],0)
    def test_all_abstain_has_zero_coverage(self):
        predictions=[{"case_id":c["case_id"],"decision":"abstain"} for c in self.cases()]
        r=self.score(self.cases(),predictions)
        self.assertEqual(r["pair_selective_coverage"],0.0)
        self.assertIsNone(r["pair_selective_risk"])
        self.assertEqual(r["pair_exact_accuracy"],0.0)
    def test_same_decision_for_both_members_is_collapsed(self):
        predictions=self.gold_predictions()
        group=self.cases()[0]["independence_group"]
        ids={c["case_id"] for c in self.cases() if c["independence_group"]==group}
        predictions=[dict(p,decision="reject") if p["case_id"] in ids else p for p in predictions]
        r=self.score(self.cases(),predictions)
        self.assertEqual(r["collapsed_pair_count"],1)
    def test_missing_one_prediction_abstains_pair(self):
        predictions=self.gold_predictions()[1:]
        r=self.score(self.cases(),predictions)
        self.assertLess(r["pair_selective_coverage"],1.0)
        self.assertLess(r["submitted_pairs"],r["pair_count"])
    def test_duplicate_predictions_rejected(self):
        p=self.gold_predictions(); p.append(p[0])
        with self.assertRaises(ValueError): self.score(self.cases(),p)
    def test_unknown_prediction_id_rejected(self):
        with self.assertRaises(ValueError): self.score(self.cases(),[{"case_id":"unknown","decision":"accept"}])
    def test_groups_must_contain_exactly_two_cases(self):
        cases=self.cases()+[dict(self.cases()[0],case_id="extra-case")]
        with self.assertRaises(ValueError): self.score(cases,[])
    def test_expected_decisions_must_differ(self):
        cases=self.cases()
        group=cases[0]["independence_group"]
        members=[c for c in cases if c["independence_group"]==group]
        members[1]["gold_decision"]=members[0]["gold_decision"]
        with self.assertRaises(ValueError): self.score(cases,[])
    def test_pair_cannot_cross_split(self):
        cases=self.cases()
        group=cases[0]["independence_group"]
        next(c for c in cases if c["independence_group"]==group and c["case_id"]!=cases[0]["case_id"])["split_group"]="test"
        with self.assertRaises(ValueError): self.score(cases,[])
    def test_case_level_accuracy_can_hide_pair_collapse(self):
        predictions=self.gold_predictions()
        group=self.cases()[0]["independence_group"]
        ids={c["case_id"] for c in self.cases() if c["independence_group"]==group}
        predictions=[dict(p,decision="accept") if p["case_id"] in ids else p for p in predictions]
        r=self.score(self.cases(),predictions)
        self.assertEqual(r["collapsed_pair_count"],1)
        self.assertLess(r["pair_exact_accuracy"],1.0)

    def test_fixture_scoring_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            evaluate_contrastive_pairs(self.cases(),self.gold_predictions())
        self.assertEqual(self.score(self.cases(),self.gold_predictions())["pair_exact_accuracy"],1.0)
    def test_pending_review_cases_cannot_be_scored(self):
        cases=self.cases()
        cases[0]["label_status"]="pending_review"
        with self.assertRaises(ValueError):
            self.score(cases,self.gold_predictions())

if __name__=="__main__": unittest.main()