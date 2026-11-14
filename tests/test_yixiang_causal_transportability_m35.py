import unittest
from prototype.yixiang_causal_transportability_m35 import *
def domains():
 return (DomainSpec("src","pop1","ctx1","measure1","treat1","outcome1","data1"),
         DomainSpec("tgt","pop2","ctx2","measure1","treat1","outcome1","data2"))
def mechanism():
 return MechanismSpec("mech","Y",("A","X"),"f-ref",("ctx1","ctx2"),("ev",))
def claim(state=InvarianceState.EVIDENCE_SUPPORTED,**kw):
 d=dict(claim_id="c",mechanism_id="mech",source_domain_id="src",target_domain_id="tgt",
        state=state,evidence_refs=("ev",),counterexample_refs=(),reviewer_ids=("r",),scope="contexts 1 and 2")
 d.update(kw); return InvarianceClaim(**d)
def query():
 return TransportQuery("q","src","tgt","A","Y","ATE","target pop","diagram","proof",("source trial","target covariates"))
def audit(**kw):
 d=dict(domains=domains(),mechanisms=(mechanism(),)); d.update(kw); return audit_transportability(**d)
class M35Tests(unittest.TestCase):
 def test_complete_query_requires_review_not_certification(self):
  r=audit(invariance_claims=(claim(),),queries=(query(),))
  self.assertEqual(r.disposition,TransportDisposition.REVIEW_REQUIRED); self.assertFalse(r.causal_truth_established)
 def test_no_query_not_identified(self): self.assertEqual(audit().disposition,TransportDisposition.NOT_IDENTIFIED)
 def test_claimed_invariance_is_conditional(self):
  r=audit(invariance_claims=(claim(InvarianceState.CLAIMED),),queries=(query(),))
  self.assertEqual(r.disposition,TransportDisposition.CONDITIONAL)
 def test_unknown_invariance_is_conditional(self):
  r=audit(invariance_claims=(claim(InvarianceState.UNKNOWN),),queries=(query(),))
  self.assertEqual(r.disposition,TransportDisposition.CONDITIONAL)
 def test_duplicate_domains(self): self.assertIn("duplicate_domain_id",audit(domains=(domains()[0],domains()[0])).issues)
 def test_incomplete_domain(self):
  d=DomainSpec("src","","ctx","m","t","y","data")
  self.assertIn("incomplete_domain_spec:src",audit(domains=(d,domains()[1])).issues)
 def test_duplicate_mechanisms(self): self.assertIn("duplicate_mechanism_id",audit(mechanisms=(mechanism(),mechanism())).issues)
 def test_mechanism_requires_evidence(self):
  m=MechanismSpec("mech","Y",("A",),"f",("ctx",),())
  self.assertIn("incomplete_mechanism_spec:mech",audit(mechanisms=(m,)).issues)
 def test_duplicate_parent(self):
  m=MechanismSpec("mech","Y",("A","A"),"f",("ctx",),("ev",))
  self.assertIn("duplicate_mechanism_parent:mech",audit(mechanisms=(m,)).issues)
 def test_self_referential_mechanism(self):
  m=MechanismSpec("mech","Y",("Y",),"f",("ctx",),("ev",))
  self.assertIn("self_referential_mechanism:mech",audit(mechanisms=(m,)).issues)
 def test_difference_unknown_domain(self):
  d=DomainDifference("d","bad","tgt","Y",DifferenceKind.MECHANISM_FUNCTION,"changed",("ev",))
  self.assertIn("difference_unknown_domain:d",audit(differences=(d,)).issues)
 def test_difference_requires_evidence(self):
  d=DomainDifference("d","src","tgt","Y",DifferenceKind.POPULATION_DISTRIBUTION,"shift",())
  self.assertIn("incomplete_domain_difference:d",audit(differences=(d,)).issues)
 def test_duplicate_differences(self):
  d=DomainDifference("d","src","tgt","X",DifferenceKind.POPULATION_DISTRIBUTION,"shift",("ev",))
  self.assertIn("duplicate_domain_difference_id",audit(differences=(d,d)).issues)
 def test_claim_unknown_mechanism(self):
  c=claim(mechanism_id="absent")
  self.assertIn("claim_unknown_mechanism:c",audit(invariance_claims=(c,)).issues)
 def test_claim_requires_scope_and_review(self):
  c=claim(scope="",reviewer_ids=())
  self.assertIn("invariance_claim_requires_scope_and_review:c",audit(invariance_claims=(c,)).issues)
 def test_supported_claim_requires_evidence(self):
  c=claim(evidence_refs=())
  self.assertIn("supported_invariance_requires_evidence:c",audit(invariance_claims=(c,)).issues)
 def test_refuted_claim_requires_counterexample(self):
  c=claim(InvarianceState.REFUTED)
  self.assertIn("refuted_invariance_requires_counterexample:c",audit(invariance_claims=(c,)).issues)
 def test_mechanism_difference_conflicts_with_invariance(self):
  d=DomainDifference("d","src","tgt","Y",DifferenceKind.MECHANISM_FUNCTION,"function changed",("ev",))
  self.assertIn("mechanism_difference_conflicts_with_invariance:c",audit(differences=(d,),invariance_claims=(claim(),)).issues)
 def test_query_requires_selection_diagram_and_proof(self):
  q=TransportQuery("q","src","tgt","A","Y","ATE","pop","","",("data",))
  self.assertIn("incomplete_transport_query:q",audit(queries=(q,)).issues)
 def test_query_requires_data_inventory(self):
  q=TransportQuery("q","src","tgt","A","Y","ATE","pop","diagram","proof",())
  self.assertIn("transport_query_requires_data_inventory:q",audit(queries=(q,)).issues)
 def test_query_unknown_domain(self):
  q=TransportQuery("q","src","bad","A","Y","ATE","pop","diagram","proof",("data",))
  self.assertIn("query_unknown_domain:q",audit(queries=(q,)).issues)
 def test_query_requires_distinct_domains(self):
  q=TransportQuery("q","src","src","A","Y","ATE","pop","diagram","proof",("data",))
  self.assertIn("transport_query_requires_distinct_domains:q",audit(queries=(q,)).issues)
 def test_measurement_shift_must_be_declared(self):
  ds=(domains()[0],DomainSpec("tgt","pop2","ctx2","scale2","treat1","outcome1","data2"))
  self.assertIn("unrecorded_measurement_difference:q",audit(domains=ds,queries=(query(),)).issues)
 def test_treatment_version_shift_must_be_declared(self):
  ds=(domains()[0],DomainSpec("tgt","pop2","ctx2","measure1","treat2","outcome1","data2"))
  self.assertIn("unrecorded_treatment_version_difference:q",audit(domains=ds,queries=(query(),)).issues)
 def test_outcome_definition_shift_must_be_declared(self):
  ds=(domains()[0],DomainSpec("tgt","pop2","ctx2","measure1","treat1","outcome2","data2"))
  self.assertIn("unrecorded_outcome_definition_difference:q",audit(domains=ds,queries=(query(),)).issues)
 def test_valid_claim_not_causal_truth(self):
  r=audit(invariance_claims=(claim(),),queries=(query(),))
  self.assertFalse(r.causal_truth_established)
if __name__=="__main__": unittest.main()
