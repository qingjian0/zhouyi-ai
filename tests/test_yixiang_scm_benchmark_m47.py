import unittest
from prototype.yixiang_scm_benchmark_m47 import *

class M47Tests(unittest.TestCase):
 def test_deterministic_seed(self): self.assertEqual(generate_scm(SCMConfig()).observational,generate_scm(SCMConfig()).observational)
 def test_different_seed_changes_data(self): self.assertNotEqual(generate_scm(SCMConfig(seed=1)).observational,generate_scm(SCMConfig(seed=2)).observational)
 def test_confounding_edges_present(self): self.assertIn(("U","Y"),generate_scm(SCMConfig()).ground_truth_edges)
 def test_no_confounding_edges(self): self.assertNotIn(("U","Y"),generate_scm(SCMConfig(confounding=False)).ground_truth_edges)
 def test_mechanism_shift_changes_scenario_id(self): self.assertNotEqual(generate_scm(SCMConfig()).scenario_id,generate_scm(SCMConfig(mechanism_shift=True)).scenario_id)
 def test_intervention_samples_bounded(self):
  d=generate_scm(SCMConfig(n=100,intervention_fraction=.2)); self.assertEqual(len(d.interventional),20)
 def test_observational_samples(self): self.assertEqual(len(generate_scm(SCMConfig(n=100)).observational),100)
 def test_measurement_shift_deterministic(self): self.assertEqual(generate_scm(SCMConfig(measurement_shift=.2)).observational,generate_scm(SCMConfig(measurement_shift=.2)).observational)
 def test_selection_bias_reduces_or_preserves_sample(self): self.assertLessEqual(len(generate_scm(SCMConfig(selection_bias=True)).observational),200)
 def test_invalid_size(self):
  with self.assertRaises(ValueError): generate_scm(SCMConfig(n=2))
 def test_invalid_intervention_fraction(self):
  with self.assertRaises(ValueError): generate_scm(SCMConfig(intervention_fraction=2))
 def test_negative_measurement_shift(self):
  with self.assertRaises(ValueError): generate_scm(SCMConfig(measurement_shift=-1))
