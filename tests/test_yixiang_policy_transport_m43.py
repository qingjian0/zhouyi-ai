import unittest
from prototype.yixiang_policy_transport_m43 import *

def fixture(**kw):
 s=Domain("source","pop","ctx","measure","action-v1","outcome")
 t=Domain("target","pop","ctx","measure","action-v1","outcome")
 d=dict(source=s,target=t,source_policy_ref="policy",target_support_ref="support",target_overlap=.95,
        target_value_estimate=.7,differences=(),invariants=(),target_validation_ref="validation",target_population_defined=True)
 d.update(kw); return PolicyTransportQuery(**d)

class M43Tests(unittest.TestCase):
 def test_same_context_conditionally_transportable(self): self.assertEqual(audit_policy_transport(fixture()).status,TransportStatus.CONDITIONALLY_TRANSPORTABLE)
 def test_population_difference_requires_record(self):
  q=fixture(target=Domain("target","pop2","ctx","measure","action-v1","outcome"))
  self.assertTrue(any(x.startswith("unrecorded_domain_difference:population") for x in audit_policy_transport(q).issues))
 def test_adjusted_population_difference_review(self):
  q=fixture(target=Domain("target","pop2","ctx","measure","action-v1","outcome"),
   differences=(DomainDifference(Difference.POPULATION,"shift","e",True),))
  self.assertEqual(audit_policy_transport(q).status,TransportStatus.CONDITIONALLY_TRANSPORTABLE)
 def test_unadjusted_difference_review(self):
  q=fixture(differences=(DomainDifference(Difference.POPULATION,"shift","e",False),))
  self.assertEqual(audit_policy_transport(q).status,TransportStatus.REVIEW_REQUIRED)
 def test_low_overlap_review(self): self.assertEqual(audit_policy_transport(fixture(target_overlap=.2)).status,TransportStatus.REVIEW_REQUIRED)
 def test_invalid_overlap_blocked(self): self.assertIn("invalid_target_overlap",audit_policy_transport(fixture(target_overlap=2)).issues)
 def test_missing_target_population_blocked(self): self.assertIn("target_population_not_defined",audit_policy_transport(fixture(target_population_defined=False)).issues)
 def test_refuted_invariance_blocks(self):
  inv=MechanismInvariant("m",Invariance.REFUTED,"s","t","reviewer")
  self.assertTrue(any(x.startswith("mechanism_invariance_refuted") for x in audit_policy_transport(fixture(invariants=(inv,))).issues))
 def test_unknown_invariance_requires_review(self):
  inv=MechanismInvariant("m",Invariance.UNKNOWN,"s","t","reviewer")
  self.assertEqual(audit_policy_transport(fixture(invariants=(inv,))).status,TransportStatus.REVIEW_REQUIRED)
 def test_supported_invariance(self):
  inv=MechanismInvariant("m",Invariance.SUPPORTED,"s","t","reviewer")
  self.assertEqual(audit_policy_transport(fixture(invariants=(inv,))).status,TransportStatus.CONDITIONALLY_TRANSPORTABLE)
 def test_invariant_without_evidence_blocks(self):
  inv=MechanismInvariant("m",Invariance.SUPPORTED,"","t","reviewer")
  self.assertTrue(any(x.startswith("invariant_missing_review_evidence") for x in audit_policy_transport(fixture(invariants=(inv,))).issues))
 def test_context_change_requires_mechanism_and_selection_record(self):
  q=fixture(target=Domain("target","pop","ctx2","measure","action-v1","outcome"))
  issues=audit_policy_transport(q).issues
  self.assertIn("unrecorded_domain_difference:mechanism",issues)
  self.assertIn("unrecorded_domain_difference:selection",issues)
 def test_action_version_change_requires_record(self):
  q=fixture(target=Domain("target","pop","ctx","measure","action-v2","outcome"))
  self.assertIn("unrecorded_domain_difference:action_version",audit_policy_transport(q).issues)
 def test_measurement_change_requires_record(self):
  q=fixture(target=Domain("target","pop","ctx","measure2","action-v1","outcome"))
  self.assertIn("unrecorded_domain_difference:measurement",audit_policy_transport(q).issues)
 def test_outcome_change_requires_record(self):
  q=fixture(target=Domain("target","pop","ctx","measure","action-v1","outcome2"))
  self.assertIn("unrecorded_domain_difference:outcome_definition",audit_policy_transport(q).issues)
 def test_missing_difference_evidence_blocks(self):
  q=fixture(differences=(DomainDifference(Difference.POPULATION,"shift","","true"),))
  self.assertTrue(any(x.startswith("difference_missing_evidence") for x in audit_policy_transport(q).issues))
 def test_no_execution_authority(self): self.assertFalse(audit_policy_transport(fixture()).policy_execution_authorized)
 def test_no_effect_certification(self): self.assertFalse(audit_policy_transport(fixture()).causal_effect_certified)

 def test_context_change_without_invariance_evidence_blocks(self):
  q=fixture(target=Domain("target","pop","ctx2","measure","action-v1","outcome"),
   differences=(DomainDifference(Difference.MECHANISM,"mechanism changed","m",True),
                DomainDifference(Difference.SELECTION,"selection changed","s",True)))
  self.assertIn("missing_mechanism_invariance_evidence",audit_policy_transport(q).issues)
