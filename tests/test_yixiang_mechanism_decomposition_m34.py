import unittest
from prototype.yixiang_mechanism_decomposition_m34 import *
def var(role="mediator"): return MechanismVariable("m",role,"scale","after treatment before outcome","ctx")
def est(kind=EstimandKind.TOTAL_EFFECT): return EffectEstimand("e",kind,"A","Y","target","additive","randomized",("consistency","positivity"),"pre")
def cell(cid,levels=(("A","0"),("B","1"))): return FactorialCell(cid,"cmp","ctx","obj","src",levels,1.0,"additive",AssignmentDesign.RANDOMIZED,("ev",))
def base(**kw):
 d=dict(variables=(var(),),strata=(ContextStratum("s","ctx","obj","scale","population"),)); d.update(kw); return audit_mechanism_decomposition(**d)
class M34Tests(unittest.TestCase):
 def test_additive_interaction(self): self.assertEqual(factorial_interaction_contrast(1,2,3,7),3)
 def test_zero_interaction(self): self.assertEqual(factorial_interaction_contrast(1,2,3,4),0)
 def test_duplicate_variables(self): self.assertIn("duplicate_variable_id",base(variables=(var(),var())).issues)
 def test_mediator_unknown_variable(self):
  m=MediatorSpec("med","A","Y","missing",("assumption",),"audited","not assumed",("alt",)); self.assertIn("unknown_mediator_variable:med",base(mediators=(m,)).issues)
 def test_mediator_role(self):
  m=MediatorSpec("med","A","Y","m",("assumption",),"audited","not assumed",("alt",)); self.assertIn("mediator_role_mismatch:med",base(variables=(var("feature"),),mediators=(m,)).issues)
 def test_mediator_assumptions(self):
  m=MediatorSpec("med","A","Y","m",(),"audited","not assumed",("alt",)); self.assertIn("mediator_requires_identification_assumptions:med",base(mediators=(m,)).issues)
 def test_post_treatment_confounding(self):
  m=MediatorSpec("med","A","Y","m",("assumption",),"","not assumed",("alt",)); self.assertIn("mediator_requires_treatment_induced_confounding_audit:med",base(mediators=(m,)).issues)
 def test_cross_world(self):
  m=MediatorSpec("med","A","Y","m",("assumption",),"audited","",("alt",)); self.assertIn("mediator_requires_cross_world_assumption_audit:med",base(mediators=(m,)).issues)
 def test_alternative_paths(self):
  m=MediatorSpec("med","A","Y","m",("assumption",),"audited","not assumed",()); self.assertIn("mediator_requires_alternative_paths:med",base(mediators=(m,)).issues)
 def test_natural_mediation_requires_spec(self): self.assertIn("natural_mediation_estimand_requires_mediator_spec:e",base(estimands=(est(EstimandKind.NATURAL_INDIRECT),)).issues)
 def test_estimand_assumptions(self):
  e=EffectEstimand("e",EstimandKind.TOTAL_EFFECT,"A","Y","target","additive","design",(),"pre"); self.assertIn("estimand_requires_assumptions:e",base(estimands=(e,)).issues)
 def test_duplicate_estimands(self): self.assertIn("duplicate_estimand_id",base(estimands=(est(),est())).issues)
 def test_factor_cell_evidence(self):
  c=FactorialCell("c","cmp","ctx","obj","src",(("A","1"),),1.0,"additive",AssignmentDesign.RANDOMIZED,()); self.assertIn("factorial_cell_requires_evidence:c",base(cells=(c,)).issues)
 def test_duplicate_factor_level(self): self.assertIn("duplicate_factor_level:c",base(cells=(cell("c",(("A","0"),("A","1"))),)).issues)
 def test_duplicate_cells(self): self.assertIn("duplicate_factorial_cell_id",base(cells=(cell("c"),cell("c"))).issues)
 def test_unknown_estimand(self):
  x=EffectEstimate("x","missing",1.0,"se","ci","est","validation",("r",),("ev",)); self.assertIn("unknown_estimate_estimand:x",base(estimates=(x,)).issues)
 def test_incomplete_estimate(self):
  x=EffectEstimate("x","e",1.0,"","ci","est","validation",(),()); self.assertIn("incomplete_effect_estimate:x",base(estimands=(est(),),estimates=(x,)).issues)
 def test_discovery_split(self):
  x=EffectEstimate("x","e",1.0,"se","ci","est","discovery",("r",),("ev",)); self.assertIn("discovery_split_cannot_validate_effect:x",base(estimands=(est(),),estimates=(x,)).issues)
 def test_invariance_two_strata(self):
  a=MeasurementInvarianceAudit("a","scale",("s",),"scalar",("ev",),("r",)); self.assertIn("incomplete_measurement_invariance_audit:a",base(invariance_audits=(a,)).issues)
 def test_invariance_unknown_stratum(self):
  a=MeasurementInvarianceAudit("a","scale",("s","missing"),"scalar",("ev",),("r",)); self.assertIn("unknown_invariance_stratum:a",base(invariance_audits=(a,)).issues)
 def test_stratum_measurement(self):
  s=ContextStratum("s","ctx","obj","",""); self.assertIn("incomplete_context_stratum:s",base(strata=(s,)).issues)
 def test_path_evidence(self):
  p=MechanismPath("p",("A","M","Y"),(),"ctx","candidate"); self.assertIn("incomplete_mechanism_path:p",base(paths=(p,)).issues)
 def test_path_repeated_nodes(self):
  p=MechanismPath("p",("A","M","A"),("e1","e2"),"ctx","candidate"); self.assertIn("cyclic_or_repeated_mechanism_node:p",base(paths=(p,)).issues)
 def test_shap_not_causal(self):
  a=AttributionRecord("SHAP","0.8","causal_contribution"); self.assertIn("predictive_attribution_cannot_be_causal:SHAP",base(attributions=(a,)).issues)
 def test_attention_not_causal(self):
  a=AttributionRecord("attention","high","causal_effect"); self.assertIn("predictive_attribution_cannot_be_causal:attention",base(attributions=(a,)).issues)
 def test_valid_never_certifies_truth(self):
  r=base(); self.assertTrue(r.valid); self.assertFalse(r.causal_truth_established); self.assertEqual(r.disposition,"review_required")
if __name__=="__main__": unittest.main()
