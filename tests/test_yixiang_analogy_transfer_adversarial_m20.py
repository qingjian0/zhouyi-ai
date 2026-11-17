import json
import unittest
from pathlib import Path
from prototype.yixiang_benchmark import validate_dataset, evaluate_predictions, group_leakage

class M20Tests(unittest.TestCase):
    def load(self):
        path=Path(__file__).resolve().parents[1]/"data"/"yixiang_analogy_transfer_adversarial_m20.v0.1.json"
        return json.loads(path.read_text(encoding="utf-8"))
    def test_all_cases_validate_as_synthetic_fixtures(self):
        cases=self.load(); validate_dataset(cases)
        self.assertEqual(len(cases),16)
        self.assertTrue(all(c["source_status"]=="synthetic_fixture" and c["label_status"]=="fixture_expected" and not c["reviewers"] for c in cases))
    def test_eight_contrastive_pairs_are_kept_together(self):
        cases=self.load(); groups={}
        for c in cases: groups.setdefault(c["independence_group"],set()).add(c["split_group"])
        self.assertEqual(len(groups),8)
        self.assertTrue(all(len(splits)==1 for splits in groups.values()))
    def test_relation_direction_pair(self):
        by={c["case_id"]:c for c in self.load()}
        self.assertEqual(by["m20:relation-direction:direction-preserved"]["gold_decision"],"accept")
        self.assertEqual(by["m20:relation-direction:direction-reversed"]["gold_decision"],"reject")
    def test_same_result_does_not_certify_mechanism(self):
        by={c["case_id"]:c for c in self.load()}
        self.assertEqual(by["m20:same-result-mechanism:same-result-unseen-mechanism"]["gold_decision"],"abstain")
    def test_context_sensitive_cases_require_scope(self):
        self.assertTrue(all(c["scope_conditions"] for c in self.load() if c["gold_decision"]=="conditional"))
    def test_reject_cases_preserve_counterexamples(self):
        self.assertTrue(all(c["known_counterexamples"] for c in self.load() if c["gold_decision"]=="reject"))
    def test_holdout_contains_unseen_transfer_families(self):
        cases=[c for c in self.load() if c["split_group"]=="holdout"]
        self.assertGreaterEqual(len(cases),6)
        self.assertTrue(any("species-context" in c["case_id"] for c in cases))
        self.assertTrue(any("class-vs-quantity" in c["case_id"] for c in cases))
    def test_fixture_scoring_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError): evaluate_predictions(self.load(),[])
        result=evaluate_predictions(self.load(),[],allow_fixture_expected=True)
        self.assertEqual(result["evaluation_basis"],"fixture_expected")
    def test_no_classical_text_is_mislabeled_as_gold(self):
        self.assertTrue(all(c["source_lineage"][0].startswith("fixture:") for c in self.load()))
    def test_pairwise_source_leakage_is_detectable(self):
        report=group_leakage(self.load(),group_field="independence_group")
        self.assertEqual(report["leakage_count"],0)

if __name__=="__main__": unittest.main()