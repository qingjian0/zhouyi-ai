import unittest
from prototype.yixiang_causal_mechanism_discovery_m36 import *

def obs(split="discover", kind=EvidenceKind.OBSERVATIONAL, **kw):
    d=dict(evidence_id="e1",kind=kind,source_family="src1",dataset_split=split,
           review_state=ReviewState.REVIEWED,observed_variables=("X","Y"),
           intervention_target="",design_ref="design",limitation_refs=("limits",))
    d.update(kw); return Evidence(**d)
def hyp(**kw):
    d=dict(hypothesis_id="h1",variable_ids=("X","Y"),directed_edges=(("X","Y"),),
           functional_form_ref="f",scope="ctx-a",evidence_refs=("e1",),
           alternative_hypothesis_ids=("h2",),confounding_state=ConfoundingState.ADDRESSED,
           latent_variable_refs=("U-inventory",),discovery_split="discover",
           validation_split="holdout",assumptions=("consistency","no-unmeasured-confounding"),
           reviewer_ids=("reviewer",),state=HypothesisState.PROPOSED)
    d.update(kw); return MechanismHypothesis(**d)
def audit(**kw):
    d=dict(evidence=(obs(),),hypotheses=(hyp(),)); d.update(kw)
    return audit_mechanism_discovery(**d)

class M36Tests(unittest.TestCase):
    def test_observational_only_is_associational(self):
        self.assertEqual(audit().disposition,DiscoveryDisposition.ASSOCIATIONAL_ONLY)
    def test_never_certifies_truth(self): self.assertFalse(audit().causal_truth_established)
    def test_duplicate_evidence_id(self): self.assertIn("duplicate_evidence_id",audit(evidence=(obs(),obs())).issues)
    def test_duplicate_hypothesis_id(self): self.assertIn("duplicate_hypothesis_id",audit(hypotheses=(hyp(),hyp())).issues)
    def test_incomplete_evidence(self): self.assertIn("incomplete_evidence:e1",audit(evidence=(obs(source_family=""),)).issues)
    def test_intervention_requires_target(self):
        e=obs(kind=EvidenceKind.INTERVENTIONAL,intervention_target="",design_ref="d")
        self.assertIn("intervention_requires_target_and_design:e1",audit(evidence=(e,)).issues)
    def test_intervention_requires_design(self):
        e=obs(kind=EvidenceKind.INTERVENTIONAL,intervention_target="X",design_ref="")
        self.assertIn("intervention_requires_target_and_design:e1",audit(evidence=(e,)).issues)
    def test_counterfactual_requires_design(self):
        e=obs(kind=EvidenceKind.COUNTERFACTUAL,design_ref="")
        self.assertIn("counterfactual_requires_generation_or_identification_design:e1",audit(evidence=(e,)).issues)
    def test_discovery_and_validation_must_differ(self):
        self.assertIn("discovery_validation_split_overlap:h1",audit(hypotheses=(hyp(discovery_split="holdout"),)).issues)
    def test_hypothesis_requires_evidence(self): self.assertIn("hypothesis_requires_evidence:h1",audit(hypotheses=(hyp(evidence_refs=()),)).issues)
    def test_unknown_evidence_ref(self): self.assertIn("unknown_evidence:h1:missing",audit(hypotheses=(hyp(evidence_refs=("missing",)),)).issues)
    def test_hypothesis_requires_assumptions(self): self.assertIn("hypothesis_requires_assumptions:h1",audit(hypotheses=(hyp(assumptions=()),)).issues)
    def test_hypothesis_requires_scope(self): self.assertIn("incomplete_hypothesis:h1",audit(hypotheses=(hyp(scope=""),)).issues)
    def test_duplicate_variables(self): self.assertIn("duplicate_variable:h1",audit(hypotheses=(hyp(variable_ids=("X","X")),)).issues)
    def test_unknown_confounding_warns(self): self.assertIn("confounding_unresolved:h1",audit(hypotheses=(hyp(confounding_state=ConfoundingState.UNKNOWN),)).warnings)
    def test_latent_inventory_unknown_warns(self): self.assertIn("latent_variable_inventory_unknown:h1",audit(hypotheses=(hyp(confounding_state=ConfoundingState.UNKNOWN,latent_variable_refs=()),)).warnings)
    def test_no_alternatives_warns(self): self.assertIn("no_competing_explanation_registered:h1",audit(hypotheses=(hyp(alternative_hypothesis_ids=()),)).warnings)
    def test_no_reviewer_warns(self): self.assertIn("hypothesis_requires_human_review:h1",audit(hypotheses=(hyp(reviewer_ids=()),)).warnings)
    def test_disputed_evidence_warns(self): self.assertIn("disputed_evidence:e1",audit(evidence=(obs(review_state=ReviewState.DISPUTED),)).warnings)
    def test_observational_warning(self): self.assertIn("observational_only:h1",audit().warnings)
    def test_counterfactual_not_empirical_intervention(self):
        e=obs(kind=EvidenceKind.COUNTERFACTUAL)
        r=audit(evidence=(e,))
        self.assertIn("counterfactual_without_empirical_intervention:h1",r.warnings)
    def test_intervention_can_reach_review(self):
        e=obs(kind=EvidenceKind.INTERVENTIONAL,intervention_target="X")
        r=audit(evidence=(e,))
        self.assertEqual(r.disposition,DiscoveryDisposition.REVIEW_REQUIRED)
    def test_validation_data_cannot_be_discovery_evidence(self):
        e=obs(split="holdout")
        self.assertIn("validation_data_used_as_discovery_evidence:h1",audit(evidence=(e,)).issues)
    def test_source_family_reuse_warns(self):
        e1=obs(); e2=obs(split="discover",evidence_id="e2",source_family="src1")
        r=audit(evidence=(e1,e2),hypotheses=(hyp(evidence_refs=("e1","e2")),))
        self.assertIn("shared_source_family:h1",r.warnings)
    def test_refuted_requires_failed_test(self):
        self.assertIn("refuted_hypothesis_requires_failed_or_reversed_test:h1",audit(hypotheses=(hyp(state=HypothesisState.REFUTED),)).issues)
    def test_refuted_with_failed_test(self):
        f=FalsificationRecord("f1","h1","e1","increase","decrease","reversed")
        self.assertNotIn("refuted_hypothesis_requires_failed_or_reversed_test:h1",audit(falsifications=(f,),hypotheses=(hyp(state=HypothesisState.REFUTED),)).issues)
    def test_falsification_unknown_hypothesis(self):
        f=FalsificationRecord("f1","bad","e1","x","y","failed")
        self.assertIn("falsification_unknown_hypothesis:f1",audit(falsifications=(f,)).issues)
    def test_falsification_unknown_evidence(self):
        f=FalsificationRecord("f1","h1","bad","x","y","failed")
        self.assertIn("falsification_unknown_evidence:f1",audit(falsifications=(f,)).issues)
    def test_unresolved_counterexample_warns(self):
        f=FalsificationRecord("f1","h1","e1","x","y","unresolved",True)
        self.assertIn("unresolved_counterexample:f1",audit(falsifications=(f,)).warnings)
    def test_missing_hypotheses_is_associational(self):
        self.assertEqual(audit(hypotheses=()).disposition,DiscoveryDisposition.ASSOCIATIONAL_ONLY)
    def test_multiple_hypotheses_preserved(self):
        h2=hyp(hypothesis_id="h2",evidence_refs=("e1",),alternative_hypothesis_ids=("h1",))
        self.assertEqual(len(audit(hypotheses=(hyp(),h2)).issues),0)

if __name__ == "__main__":
    unittest.main()
