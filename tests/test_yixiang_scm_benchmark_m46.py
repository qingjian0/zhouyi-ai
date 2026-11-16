import unittest
from prototype.yixiang_scm_benchmark_m46 import *

def env(seed=7):
 return SCMEnvironment(SCMSpec("toy",(
  SCMNode("x",(),(),noise_scale=1),
  SCMNode("z",("x",),(2.0,),noise_scale=0),
  SCMNode("y",("z",),(3.0,),intercept=1,noise_scale=0),
 ),seed,10))

class M46Tests(unittest.TestCase):
 def test_node_names_topological(self): self.assertEqual(env().node_names,("x","z","y"))
 def test_direct_parents_oracle(self): self.assertEqual(env().direct_parents("y"),("z",))
 def test_ancestors_oracle(self): self.assertEqual(env().ancestors("y"),("x","z"))
 def test_oracle_labels_evaluator_only(self): self.assertTrue(env().oracle("y")["ground_truth_available_to_evaluator_only"])
 def test_repeated_observation_is_persistent(self):
  e=env(); self.assertEqual(e.sample((0,)),e.sample((0,)))
 def test_same_seed_same_population(self): self.assertEqual(env(8).sample((0,1)),env(8).sample((0,1)))
 def test_different_seed_changes_noise(self): self.assertNotEqual(env(8).sample((0,)),env(9).sample((0,)))
 def test_do_intervention_sets_value(self):
  row=env().sample((0,),{"x":5})[0]; self.assertEqual(dict(row.values)["x"],5.0)
 def test_do_intervention_recomputes_descendants(self):
  row=env().sample((0,),{"x":5})[0]
  self.assertAlmostEqual(dict(row.values)["z"],10.0)
  self.assertAlmostEqual(dict(row.values)["y"],31.0)
 def test_intervention_bypasses_target_equation(self):
  row=env().sample((0,),{"z":4})[0]; self.assertEqual(dict(row.values)["z"],4)
  self.assertAlmostEqual(dict(row.values)["y"],13)
 def test_unknown_intervention_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"unknown_intervention_target"): env().sample((0,),{"q":1})
 def test_nonfinite_intervention_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"non_finite_intervention"): env().sample((0,),{"x":float("nan")})
 def test_invalid_unit_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"unit_id_out_of_range"): env().sample((10,))
 def test_duplicate_nodes_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"invalid_or_duplicate_node"):
   SCMEnvironment(SCMSpec("x",(SCMNode("a",(),()),SCMNode("a",(),())),1,2))
 def test_unknown_parent_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"unknown_parent"):
   SCMEnvironment(SCMSpec("x",(SCMNode("a",("b",),(1,)),),1,2))
 def test_cycle_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"cyclic_graph"):
   SCMEnvironment(SCMSpec("x",(SCMNode("a",("b",),(1,)),SCMNode("b",("a",),(1,))),1,2))
 def test_parent_coefficient_mismatch_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"parent_coefficient_mismatch"):
   SCMEnvironment(SCMSpec("x",(SCMNode("a",(),()),SCMNode("b",("a",),())),1,2))
 def test_negative_noise_rejected(self):
  with self.assertRaisesRegex(SCMValidationError,"invalid_node_parameter"):
   SCMEnvironment(SCMSpec("x",(SCMNode("a",(),(),noise_scale=-1),),1,2))
 def test_population_must_be_positive(self):
  with self.assertRaisesRegex(SCMValidationError,"invalid_model_or_population"):
   SCMEnvironment(SCMSpec("x",(SCMNode("a",(),()),),1,0))
 def test_output_retains_unit_and_intervention(self):
  row=env().sample((2,),{"x":1})[0]
  self.assertEqual(row.unit_id,2); self.assertEqual(row.intervention,(("x",1.0),))
