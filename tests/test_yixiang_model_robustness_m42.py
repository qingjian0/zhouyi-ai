import unittest
from prototype.yixiang_model_robustness_m42 import *

def s(i="s",**kw):
 d=dict(scenario_id=i,policy_value=.8,prior_shift=.1,likelihood_shift=.1,measurement_shift=.1,
        confounding=Confounding.ADDRESSED,assumptions_ref="assume",evidence_ref="evidence",calibrated=True)
 d.update(kw); return StressScenario(**d)

class M42Tests(unittest.TestCase):
 def test_robust_within_declared_set(self): self.assertEqual(audit_model_robustness(.9,(s(),)).status,RobustnessStatus.ROBUST_WITHIN_DECLARED_SET)
 def test_fragile_when_worst_below_threshold(self): self.assertEqual(audit_model_robustness(.9,(s(policy_value=.1),),minimum_acceptable_value=.5).status,RobustnessStatus.FRAGILE)
 def test_unknown_confounding_requires_review(self): self.assertEqual(audit_model_robustness(.9,(s(confounding=Confounding.UNKNOWN),)).status,RobustnessStatus.REVIEW_REQUIRED)
 def test_unmodeled_confounding_requires_review(self): self.assertEqual(audit_model_robustness(.9,(s(confounding=Confounding.UNMODELED),)).status,RobustnessStatus.REVIEW_REQUIRED)
 def test_sensitivity_bounded_confounds_allowed(self): self.assertEqual(audit_model_robustness(.9,(s(confounding=Confounding.SENSITIVITY_BOUNDED),)).status,RobustnessStatus.ROBUST_WITHIN_DECLARED_SET)
 def test_shift_exceeds_bound_requires_review(self): self.assertEqual(audit_model_robustness(.9,(s(likelihood_shift=.5),)).status,RobustnessStatus.REVIEW_REQUIRED)
 def test_duplicate_scenario_blocked(self): self.assertIn("duplicate_scenario_id",audit_model_robustness(.9,(s(),s())).issues)
 def test_no_scenarios_blocked(self): self.assertEqual(audit_model_robustness(.9,()).status,RobustnessStatus.BLOCKED)
 def test_missing_provenance_blocked(self): self.assertTrue(any(x.startswith("missing_provenance") for x in audit_model_robustness(.9,(s(evidence_ref=""),)).issues))
 def test_uncalibrated_scenario_blocked(self): self.assertIn("uncalibrated_scenario:s",audit_model_robustness(.9,(s(calibrated=False),)).issues)
 def test_nan_value_blocked(self): self.assertIn("non_finite_scenario:s",audit_model_robustness(.9,(s(policy_value=float("nan")),)).issues)
 def test_negative_shift_blocked(self): self.assertTrue(any(x.startswith("negative_shift") for x in audit_model_robustness(.9,(s(prior_shift=-.1),)).issues))
 def test_worst_case_includes_nominal(self): self.assertEqual(audit_model_robustness(.95,(s(policy_value=.8),)).worst_case_value,.8)
 def test_best_case_and_range(self):
  r=audit_model_robustness(.9,(s(policy_value=.8),)); self.assertAlmostEqual(r.value_range,.1)
 def test_no_causal_claim_permission(self): self.assertFalse(audit_model_robustness(.9,(s(),)).causal_claim_permitted)
 def test_confounder_not_ruled_out_warning(self):
  self.assertIn("no_unmeasured_confounder_is_ruled_out_by_this_audit",audit_model_robustness(.9,(s(),)).warnings)
