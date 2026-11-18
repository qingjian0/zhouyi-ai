import unittest
from prototype.yixiang_active_experiment_design_m37 import *
def pred(h,m,sd=1): return MechanismPrediction(h,m,sd,"pred:"+h)
def candidate(eid="e1",means=(0,4),**kw):
 d=dict(experiment_id=eid,intervention_target="X",intervention_value="set:1",context="ctx-a",
 predictions=(pred("h1",means[0]),pred("h2",means[1])),cost=1,risk_level=.1,max_acceptable_risk=.5,
 feasibility=CandidateStatus.FEASIBLE,safety_review=SafetyReview.APPROVED,design_ref="design",
 measurement_ref="measure",source_family="src",selection_split="select",validation_split="holdout",limitation_refs=("lim",))
 d.update(kw); return ExperimentCandidate(**d)
def rank(*cs,**kw):
 options={"max_cost":10,"max_risk":1}; options.update(kw)
 return rank_experiments(("h1","h2"),cs,**options)
class M37Tests(unittest.TestCase):
 def test_selects_discriminating_candidate(self): self.assertEqual(rank(candidate()).selected_experiment_id,"e1")
 def test_no_separation_has_no_design(self): self.assertEqual(rank(candidate(means=(2,2))).disposition,DesignDisposition.NO_DISCRIMINATING_DESIGN)
 def test_prefers_larger_separation(self): self.assertEqual(rank(candidate("a",means=(0,2)),candidate("b",means=(0,5))).ranked[0].experiment_id,"b")
 def test_cost_adjusted_score_reported(self):
  r=rank(candidate(cost=2)); self.assertAlmostEqual(r.ranked[0].cost_adjusted_score,r.ranked[0].discrimination_score/3)
 def test_budget_excludes_candidate(self): self.assertFalse(rank(candidate(cost=20)).ranked)
 def test_risk_limit_excludes_candidate(self): self.assertFalse(rank(candidate(risk_level=2)).ranked)
 def test_candidate_risk_limit_enforced(self): self.assertFalse(rank(candidate(risk_level=.8,max_acceptable_risk=.5)).ranked)
 def test_safety_pending_excluded(self): self.assertFalse(rank(candidate(safety_review=SafetyReview.PENDING)).ranked)
 def test_safety_rejected_excluded(self): self.assertFalse(rank(candidate(safety_review=SafetyReview.REJECTED)).ranked)
 def test_infeasible_excluded(self): self.assertFalse(rank(candidate(feasibility=CandidateStatus.BLOCKED)).ranked)
 def test_duplicate_candidate_ids_block(self): self.assertIn("duplicate_experiment_id",rank(candidate("x"),candidate("x")).issues)
 def test_missing_prediction_blocks(self):
  c=candidate(predictions=(pred("h1",0),))
  self.assertTrue(any(x.startswith("missing_hypothesis_predictions") for x in rank(c).issues))
 def test_unknown_prediction_blocks(self):
  c=candidate(predictions=(pred("h1",0),pred("h2",1),pred("h3",2)))
  self.assertTrue(any(x.startswith("unknown_hypothesis_predictions") for x in rank(c).issues))
 def test_duplicate_prediction_blocks(self):
  c=candidate(predictions=(pred("h1",0),pred("h1",1),pred("h2",2)))
  self.assertTrue(any(x.startswith("duplicate_prediction") for x in rank(c).issues))
 def test_negative_prediction_sd_blocks(self):
  c=candidate(predictions=(pred("h1",0,-1),pred("h2",2)))
  self.assertTrue(any(x.startswith("invalid_prediction") for x in rank(c).issues))
 def test_prediction_requires_ref(self):
  c=candidate(predictions=(MechanismPrediction("h1",0,1,""),pred("h2",2)))
  self.assertTrue(any(x.startswith("invalid_prediction") for x in rank(c).issues))
 def test_selection_validation_overlap_blocks(self): self.assertTrue(any(x.startswith("selection_validation_split_overlap") for x in rank(candidate(validation_split="select")).issues))
 def test_incomplete_candidate_blocks(self): self.assertTrue(any(x.startswith("incomplete_candidate") for x in rank(candidate(design_ref="")).issues))
 def test_negative_cost_blocks(self): self.assertTrue(any(x.startswith("negative_cost_or_risk") for x in rank(candidate(cost=-1)).issues))
 def test_negative_risk_blocks(self): self.assertTrue(any(x.startswith("negative_cost_or_risk") for x in rank(candidate(risk_level=-1)).issues))
 def test_invalid_budget_blocks(self): self.assertIn("invalid_global_budget_or_risk_limit",rank(candidate(),max_cost=-1).issues)
 def test_single_hypothesis_blocks(self):
  r=rank_experiments(("h1",),(candidate(),),max_cost=10,max_risk=1)
  self.assertIn("at_least_two_competing_hypotheses_required",r.issues)
 def test_selected_requires_human_review(self): self.assertIn("human_review_required_before_experiment_execution",rank(candidate()).warnings)
 def test_never_establishes_truth(self): self.assertFalse(rank(candidate()).causal_truth_established)
 def test_prediction_coverage_explicit(self): self.assertEqual(rank(candidate()).ranked[0].covered_hypotheses,("h1","h2"))
 def test_tie_break_deterministic(self): self.assertEqual(rank(candidate("z",means=(0,3)),candidate("a",means=(0,3))).ranked[0].experiment_id,"a")
 def test_descending_ranking(self):
  r=rank(candidate("a",means=(0,2)),candidate("b",means=(0,5)),candidate("c",means=(0,3)))
  scores=[x.discrimination_score for x in r.ranked]; self.assertEqual(scores,sorted(scores,reverse=True))
 def test_rejected_candidate_warned(self): self.assertIn("safety_rejected:e1",rank(candidate(safety_review=SafetyReview.REJECTED)).warnings)
 def test_budget_warning(self): self.assertIn("candidate_exceeds_budget:e1",rank(candidate(cost=11)).warnings)
