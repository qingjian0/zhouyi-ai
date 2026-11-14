import unittest
from prototype.yixiang_benchmark_metrics_m48 import *

class M48Tests(unittest.TestCase):
 def test_perfect_graph(self):
  m=evaluate_graph((("X","Y"),),(("X","Y"),)); self.assertEqual(m.f1,1.0); self.assertEqual(m.structural_hamming_distance,0)
 def test_missing_edge(self):
  m=evaluate_graph((),(("X","Y"),)); self.assertEqual(m.false_negative,1); self.assertEqual(m.recall,0)
 def test_extra_edge(self):
  m=evaluate_graph((("X","Y"),),(("A","B"),)); self.assertEqual(m.false_positive,1)
 def test_reversal_costs_two(self):
  m=evaluate_graph((("Y","X"),),(("X","Y"),)); self.assertEqual(m.structural_hamming_distance,2)
 def test_empty_graphs(self): self.assertEqual(evaluate_graph((),()).f1,1.0)
 def test_duplicate_edges_collapsed(self): self.assertEqual(evaluate_graph((("X","Y"),("X","Y")),(("X","Y"),)).true_positive,1)
 def test_f1_harmonic_mean(self):
  m=evaluate_graph((("X","Y"),("A","B")),(("X","Y"),("C","D"))); self.assertAlmostEqual(m.f1,.5)
 def test_compare_groups_by_method_and_ablation(self):
  a=evaluate_graph((("X","Y"),),(("X","Y"),))
  b=evaluate_graph((),(("X","Y"),))
  s=compare_methods((MethodResult("Zhouyi","s1",1,a),MethodResult("baseline","s1",1,b)))
  self.assertIn(("Zhouyi","full"),s); self.assertIn(("baseline","full"),s)
 def test_aggregate_mean(self):
  a=evaluate_graph((("X","Y"),),(("X","Y"),)); b=evaluate_graph((),(("X","Y"),))
  s=compare_methods((MethodResult("m","s",1,a),MethodResult("m","s",2,b)))
  self.assertEqual(s[("m","full")]["runs"],2); self.assertAlmostEqual(s[("m","full")]["mean_recall"],.5)
 def test_empty_comparison(self): self.assertEqual(compare_methods(()),{})
 def test_missing_method_rejected(self):
  a=evaluate_graph((),())
  with self.assertRaises(ValueError): compare_methods((MethodResult("","s",1,a),))
 def test_ablation_separated(self):
  a=evaluate_graph((),())
  s=compare_methods((MethodResult("m","s",1,a,"full"),MethodResult("m","s",2,a,"no_relation")))
  self.assertEqual(len(s),2)
