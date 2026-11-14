import unittest
from prototype.yixiang_adaptive_stopping_m41 import *

def terminal(**kw):
 d=dict(expected_reward=.9,expected_decision_loss=.05,confidence=.9,evidence_ref="val",validation_locked=True); d.update(kw); return TerminalOption(**d)
def continuation(**kw):
 d=dict(expected_future_reward=1.05,experiment_cost=.1,experiment_risk=.02,uncertainty_penalty=.01,evidence_ref="future",safety_approved=True,feasible=True); d.update(kw); return ContinuationOption(**d)

class M41Tests(unittest.TestCase):
 def test_continue_when_incremental_value_positive(self): self.assertEqual(audit_stopping(terminal(),continuation()).decision,Decision.CONTINUE)
 def test_stop_when_terminal_value_dominates(self): self.assertEqual(audit_stopping(terminal(expected_reward=1),continuation(expected_future_reward=.5)).decision,Decision.STOP)
 def test_review_when_confidence_low_and_continue_not_worthwhile(self): self.assertEqual(audit_stopping(terminal(confidence=.3),continuation(expected_future_reward=.5)).decision,Decision.REVIEW)
 def test_max_horizon_stops(self): self.assertEqual(audit_stopping(terminal(),continuation(),max_experiments_reached=True).decision,Decision.STOP)
 def test_unapproved_continuation_stops_if_confident(self): self.assertEqual(audit_stopping(terminal(),continuation(safety_approved=False)).decision,Decision.STOP)
 def test_unapproved_continuation_reviews_if_uncertain(self): self.assertEqual(audit_stopping(terminal(confidence=.2),continuation(safety_approved=False)).decision,Decision.REVIEW)
 def test_infeasible_continuation(self): self.assertIn("continuation_not_eligible",audit_stopping(terminal(),continuation(feasible=False)).warnings)
 def test_risk_limit(self): self.assertEqual(audit_stopping(terminal(),continuation(experiment_risk=2),max_risk=1).decision,Decision.STOP)
 def test_validation_must_be_locked(self): self.assertIn("validation_not_locked",audit_stopping(terminal(validation_locked=False),continuation()).issues)
 def test_missing_evidence_ref(self): self.assertIn("missing_evidence_reference",audit_stopping(terminal(evidence_ref=""),continuation()).issues)
 def test_nan_is_rejected(self): self.assertIn("non_finite_value",audit_stopping(terminal(expected_reward=float("nan")),continuation()).issues)
 def test_confidence_range(self): self.assertIn("invalid_confidence",audit_stopping(terminal(confidence=2),continuation()).issues)
 def test_negative_cost_rejected(self): self.assertIn("negative_cost_risk_or_margin",audit_stopping(terminal(),continuation(experiment_cost=-1)).issues)
 def test_stop_is_not_truth_certification(self): self.assertFalse(audit_stopping(terminal(),continuation()).terminal_truth_certified)
 def test_no_execution_authority(self): self.assertFalse(audit_stopping(terminal(),continuation()).execution_authorized)
 def test_margin_reported(self):
  r=audit_stopping(terminal(),continuation()); self.assertAlmostEqual(r.margin,r.continue_value-r.stop_value)
