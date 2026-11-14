import unittest
from prototype.yixiang_benchmark_baselines_m47 import *

def out(**kw):
 d=dict(baseline_id="b",predicted_parents=("x","z"),selected_interventions=("x",),samples_used=10,
        total_cost=5,committed=True,evidence_sufficient=True,trace_valid=True,tool_errors=0)
 d.update(kw); return BaselineOutput(**d)

class M47Tests(unittest.TestCase):
 def test_perfect_parent_metrics(self):
  s=evaluate_episode(("x","z"),("x","z"),out(),10)
  self.assertEqual((s.precision,s.recall,s.f1,s.structural_hamming_distance),(1,1,1,0))
 def test_false_positive_shd(self): self.assertEqual(evaluate_episode(("x",),("x","z"),out(),10).structural_hamming_distance,1)
 def test_false_negative_shd(self): self.assertEqual(evaluate_episode(("x","z"),("x",),out(predicted_parents=("x",)),10).structural_hamming_distance,1)
 def test_no_prediction_recall_zero(self):
  s=evaluate_episode(("x",),("x",),out(predicted_parents=()),10); self.assertEqual(s.recall,0)
 def test_empty_truth_and_prediction_perfect(self):
  s=evaluate_episode((),(),out(predicted_parents=()),10); self.assertEqual(s.f1,1)
 def test_intervention_coverage(self): self.assertEqual(evaluate_episode(("x","z"),("x","z"),out(),10).intervention_coverage,.5)
 def test_budget_utilization(self): self.assertEqual(evaluate_episode(("x",),("x",),out(total_cost=4),10).budget_utilization,.4)
 def test_budget_violation(self): self.assertTrue(evaluate_episode(("x",),("x",),out(total_cost=11),10).budget_violation)
 def test_premature_commit_without_sufficient_evidence(self):
  self.assertTrue(evaluate_episode(("x",),("x",),out(evidence_sufficient=False),10).premature_commit)
 def test_premature_commit_without_interventions(self):
  self.assertTrue(evaluate_episode(("x",),("x",),out(selected_interventions=()),10).premature_commit)
 def test_nonpremature_commit(self): self.assertFalse(evaluate_episode(("x",),("x",),out(),10).premature_commit)
 def test_random_baseline_is_reproducible(self):
  self.assertEqual(random_intervention_baseline(("a","b","c"),2,7),random_intervention_baseline(("a","b","c"),2,7))
 def test_random_baseline_unique(self):
  self.assertEqual(len(set(random_intervention_baseline(("a","b","c"),3))),3)
 def test_random_baseline_caps_k(self): self.assertEqual(len(random_intervention_baseline(("a",),5)),1)
 def test_correlation_baseline_selects_linear_signal(self):
  rows=tuple({"x":i,"y":2*i,"z":(-1)**i} for i in range(1,8))
  self.assertEqual(correlation_screen_baseline(rows,"y",("x","z"),1),("x",))
 def test_correlation_baseline_constant_is_safe(self):
  rows=({"x":1,"y":2},{"x":1,"y":3})
  self.assertEqual(correlation_screen_baseline(rows,"y",("x",),1),("x",))
 def test_correlation_baseline_missing_column_skips(self):
  rows=({"x":1,"y":2},{"y":3})
  self.assertEqual(correlation_screen_baseline(rows,"y",("x",),1),())
 def test_oracle_baseline_sorted(self): self.assertEqual(oracle_diagnostic_baseline(("z","x","x")),("x","z"))
 def test_aggregate_scores(self):
  scores=[evaluate_episode(("x",),("x",),out(predicted_parents=("x",)),10)]*2
  self.assertEqual(aggregate_scores(scores)["episodes"],2)
  self.assertEqual(aggregate_scores(scores)["mean_f1"],1)
 def test_aggregate_empty_rejected(self):
  with self.assertRaisesRegex(ValueError,"scores_required"): aggregate_scores(())
