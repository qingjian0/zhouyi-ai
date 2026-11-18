import unittest
from prototype.yixiang_ablation_evaluation_m48 import *

def runs(variant,vals,seed=1):
 return tuple(EpisodeRun(variant,f"e{i}",seed,(("f1",v),("cost",10-v))) for i,v in enumerate(vals))

class M48Tests(unittest.TestCase):
 def test_paired_effect(self):
  r=compare_ablation(runs("full",[.9,.8]),runs("no_search",[.7,.6]),(MetricSpec("f1",True),))
  self.assertTrue(r.valid); self.assertAlmostEqual(r.effects[0].mean_effect,.2)
 def test_lower_is_better_direction(self):
  r=compare_ablation(runs("full",[.8,.7]),runs("no_search",[.5,.4]),(MetricSpec("cost",False),))
  self.assertAlmostEqual(r.effects[0].mean_effect,.3)
 def test_episode_mismatch_invalid(self):
  r=compare_ablation(runs("full",[.9,.8]),runs("ablation",[.7]),(MetricSpec("f1",True),))
  self.assertIn("episode_sets_not_paired",r.issues)
 def test_duplicate_full_episode_invalid(self):
  x=EpisodeRun("full","e",1,(("f1",1),))
  y=EpisodeRun("full","e",1,(("f1",1),))
  r=compare_ablation((x,y),(EpisodeRun("ab","e",1,(("f1",0),)),),(MetricSpec("f1",True),))
  self.assertIn("duplicate_full_episode",r.issues)
 def test_duplicate_ablation_episode_invalid(self):
  x=EpisodeRun("ab","e",1,(("f1",0),))
  r=compare_ablation(runs("full",[1]),(x,x),(MetricSpec("f1",True),))
  self.assertIn("duplicate_ablation_episode",r.issues)
 def test_missing_metric_invalid(self):
  r=compare_ablation(runs("full",[1]),(EpisodeRun("ab","e0",1,(("other",0),)),),(MetricSpec("f1",True),))
  self.assertIn("missing_or_invalid_metric:f1",r.issues)
 def test_nonfinite_metric_invalid(self):
  r=compare_ablation((EpisodeRun("full","e",1,(("f1",float("nan")),)),),
    (EpisodeRun("ab","e",1,(("f1",0),)),),(MetricSpec("f1",True),))
  self.assertIn("missing_or_invalid_metric:f1",r.issues)
 def test_full_variant_name_required(self):
  r=compare_ablation(runs("wrong",[1]),runs("ab",[0]),(MetricSpec("f1",True),))
  self.assertIn("full_variant_id_must_be_full",r.issues)
 def test_single_ablation_variant_required(self):
  a=(EpisodeRun("a","e",1,(("f1",1),)),EpisodeRun("b","e2",1,(("f1",1),)))
  f=(EpisodeRun("full","e",1,(("f1",1),)),EpisodeRun("full","e2",1,(("f1",1),)))
  self.assertIn("ablation_variant_mismatch",compare_ablation(f,a,(MetricSpec("f1",True),)).issues)
 def test_deterministic_bootstrap(self):
  args=(runs("full",[.9,.8,.7]),runs("ablation",[.6,.5,.4]),(MetricSpec("f1",True),))
  self.assertEqual(compare_ablation(*args,seed=3),compare_ablation(*args,seed=3))
 def test_ci_contains_mean_for_constant_effect(self):
  r=compare_ablation(runs("full",[.8,.8,.8]),runs("ablation",[.5,.5,.5]),(MetricSpec("f1",True),))
  e=r.effects[0]; self.assertAlmostEqual(e.lower_bound,.3); self.assertAlmostEqual(e.upper_bound,.3)
 def test_positive_bootstrap_required(self):
  r=compare_ablation(runs("full",[1]),runs("ab",[0]),(MetricSpec("f1",True),),bootstrap_samples=0)
  self.assertIn("bootstrap_samples_must_be_positive",r.issues)
 def test_empty_inputs_invalid(self):
  self.assertIn("runs_and_metrics_required",compare_ablation((),(),()).issues)
 def test_multiple_seeds_warn(self):
  f=(EpisodeRun("full","e",1,(("f1",1),)),EpisodeRun("full","e2",2,(("f1",1),)))
  a=(EpisodeRun("ab","e",3,(("f1",0),)),EpisodeRun("ab","e2",4,(("f1",0),)))
  self.assertIn("multiple_seeds_within_variant_require_stratified_analysis",
    compare_ablation(f,a,(MetricSpec("f1",True),)).warnings)
 def test_effect_direction_zero_when_equal(self):
  r=compare_ablation(runs("full",[.5,.5]),runs("ab",[.5,.5]),(MetricSpec("f1",True),))
  self.assertEqual(r.effects[0].mean_effect,0)
 def test_paired_episode_count(self):
  r=compare_ablation(runs("full",[1,2,3]),runs("ab",[0,1,2]),(MetricSpec("f1",True),))
  self.assertEqual(r.effects[0].paired_episodes,3)
 def test_warning_prevents_overclaim(self):
  r=compare_ablation(runs("full",[1]),runs("ab",[0]),(MetricSpec("f1",True),))
  self.assertTrue(any("not_universal" in w for w in r.warnings))
 def test_duplicate_metric_rejected_as_invalid(self):
  r=compare_ablation((EpisodeRun("full","e",1,(("f1",1),("f1",2))),),
    (EpisodeRun("ab","e",1,(("f1",0),)),),(MetricSpec("f1",True),))
  self.assertIn("missing_or_invalid_metric:f1",r.issues)
