import unittest
from prototype.yixiang_causal_intervention_m33 import *

def intervention(**kw):
    d=dict(intervention_id="i",composition_id="cmp",kind=InterventionKind.REMOVE_MEMBER,
           target_id="member-a",control_condition="present",treatment_condition="removed",
           controlled_factors=("temperature",),changed_factors=("member-a",),
           predicted_direction="decrease",preregistration_ref="pre-1")
    d.update(kw); return Intervention(**d)
def evidence(i, family=None, review=EvidenceReview.REVIEWED):
    return CausalEvidence(i,f"src-{family or i}","experiment",review,"ctx")
def unit(i, condition, outcome, ref, assignment=AssignmentKind.RANDOMIZED):
    return StudyUnit(i,"family-1","ctx","source-"+i,"i",condition,outcome,"whole-output",(() if ref is None else (ref,)),assignment)
def pair(**kw):
    d=dict(pair_id="p",intervention_id="i",unit_family="family-1",
           control_unit_id="u0",treatment_unit_id="u1",matching_basis="matched units",
           exchangeability_argument="conditional exchangeability",
           consistency_argument="well-defined treatment",
           positivity_argument="both conditions possible",
           interference_assessment="no cross-unit interference")
    d.update(kw); return CounterfactualPair(**d)
def claim(**kw):
    d=dict(claim_id="c",intervention_id="i",estimand="ATE",
           target_population="target family",identification_strategy="randomized assignment",
           assumptions=("consistency","no interference"),alternative_explanations=("measurement drift",),
           effect_estimate="-0.3",uncertainty_method="bootstrap CI",
           evidence_refs=("e0","e1"),reviewer_ids=("r1",))
    d.update(kw); return CausalClaim(**d)
def base(**kw):
    d=dict(interventions=(intervention(),),units=(unit("u0","present",1.0,"e0"),
           unit("u1","removed",0.7,"e1")),evidence=(evidence("e0"),evidence("e1")))
    d.update(kw); return audit_causal_interventions_m33(**d)

class M33Tests(unittest.TestCase):
    def test_no_causal_truth_certification(self):
        self.assertFalse(base().causal_truth_established)
    def test_distinct_intervention_conditions_required(self):
        self.assertIn("intervention_conditions_must_differ:i",base(interventions=(intervention(treatment_condition="present"),)).issues)
    def test_changed_factor_required(self):
        self.assertIn("intervention_requires_changed_factor:i",base(interventions=(intervention(changed_factors=()),)).issues)
    def test_factor_cannot_be_changed_and_controlled(self):
        self.assertIn("factor_both_changed_and_controlled:i",base(interventions=(intervention(controlled_factors=("member-a",)),)).issues)
    def test_context_change_must_name_context(self):
        self.assertIn("context_intervention_must_change_context:i",base(interventions=(intervention(kind=InterventionKind.CHANGE_CONTEXT),)).issues)
    def test_order_swap_must_name_order(self):
        self.assertIn("order_intervention_must_change_order:i",base(interventions=(intervention(kind=InterventionKind.SWAP_ORDER),)).issues)
    def test_unknown_unit_intervention(self):
        self.assertIn("unknown_unit_intervention:u0",base(interventions=(),units=(unit("u0","present",1,"e0"),)).issues)
    def test_unit_requires_evidence(self):
        self.assertIn("unit_requires_evidence:u0",base(units=(unit("u0","present",1,None),unit("u1","removed",.7,None)),evidence=()).issues)
    def test_unknown_unit_evidence(self):
        self.assertIn("unknown_unit_evidence:u0:e0",base(evidence=(evidence("e1"),)).issues)
    def test_unit_evidence_context_must_match(self):
        es=(CausalEvidence("e0","s0","experiment",EvidenceReview.REVIEWED,"other"),evidence("e1"))
        self.assertIn("unit_evidence_context_mismatch:u0:e0",base(evidence=es).issues)
    def test_pair_requires_known_units(self):
        self.assertIn("unknown_pair_unit:p",base(pairs=(pair(treatment_unit_id="missing"),)).issues)
    def test_pair_requires_known_intervention(self):
        self.assertIn("unknown_pair_intervention:p",base(pairs=(pair(intervention_id="missing"),)).issues)
    def test_pair_units_must_be_distinct(self):
        self.assertIn("counterfactual_pair_requires_distinct_units:p",base(units=(unit("u0","present",1,"e0"),),pairs=(pair(treatment_unit_id="u0"),)).issues)
    def test_pair_conditions_must_match(self):
        self.assertIn("pair_condition_mismatch:p",base(pairs=(pair(control_unit_id="u1"),)).issues)
    def test_pair_family_must_match(self):
        self.assertIn("pair_unit_family_mismatch:p",base(units=(unit("u0","present",1,"e0"),StudyUnit("u1","other","ctx","s","i","removed",.7,"whole-output",("e1",),AssignmentKind.RANDOMIZED)),pairs=(pair(unit_family="family-1"),)).issues)
    def test_pair_outcome_measure_must_match(self):
        self.assertIn("pair_outcome_measure_mismatch:p",base(units=(unit("u0","present",1,"e0"),StudyUnit("u1","family-1","ctx","s","i","removed",.7,"other",("e1",),AssignmentKind.RANDOMIZED)),pairs=(pair(),)).issues)
    def test_pair_requires_identification_assumptions(self):
        self.assertIn("incomplete_counterfactual_assumptions:p",base(pairs=(pair(exchangeability_argument=""),)).issues)
    def test_duplicate_pair_id(self):
        self.assertIn("duplicate_pair_id",base(pairs=(pair(),pair())).issues)
    def test_unit_cannot_be_reused_across_pairs(self):
        p2=pair(pair_id="p2",control_unit_id="u0",treatment_unit_id="u1")
        self.assertIn("unit_reused_across_pairs:p2",base(pairs=(pair(),p2)).issues)
    def test_claim_requires_known_intervention(self):
        self.assertIn("unknown_claim_intervention:c",base(claims=(claim(intervention_id="x"),)).issues)
    def test_claim_requires_counterfactual_design(self):
        self.assertIn("causal_claim_requires_counterfactual_design:c",base(claims=(claim(),)).issues)
    def test_observational_claim_is_not_causal(self):
        c=claim(identification_strategy="observational regression")
        us=(unit("u0","present",1.0,"e0",AssignmentKind.OBSERVATIONAL),
            unit("u1","removed",0.7,"e1",AssignmentKind.OBSERVATIONAL))
        r=base(units=us,pairs=(pair(),),claims=(c,))
        self.assertEqual(r.claim_dispositions,(("c","associational_only"),))
        self.assertEqual(r.disposition,CausalDisposition.ASSOCIATIONAL_ONLY)
    def test_claim_requires_assumptions_and_alternatives(self):
        self.assertIn("causal_claim_requires_assumptions_alternatives_reviewers:c",base(pairs=(pair(),),claims=(claim(assumptions=()),)).issues)
    def test_claim_requires_reviewers(self):
        self.assertIn("causal_claim_requires_assumptions_alternatives_reviewers:c",base(pairs=(pair(),),claims=(claim(reviewer_ids=()),)).issues)
    def test_claim_requires_evidence(self):
        self.assertIn("causal_claim_requires_evidence:c",base(pairs=(pair(),),claims=(claim(evidence_refs=()),)).issues)
    def test_claim_rejects_unknown_evidence(self):
        self.assertIn("unknown_claim_evidence:c",base(pairs=(pair(),),claims=(claim(evidence_refs=("missing",)),)).issues)
    def test_duplicate_claim_id(self):
        self.assertIn("duplicate_claim_id",base(pairs=(pair(),),claims=(claim(),claim())).issues)
    def test_unreviewed_evidence_requires_review(self):
        r=base(pairs=(pair(),),evidence=(evidence("e0",review=EvidenceReview.UNREVIEWED),evidence("e1")))
        self.assertEqual(r.disposition,CausalDisposition.REVIEW_REQUIRED)
    def test_simulated_design_is_not_real_world_causal_evidence(self):
        us=(unit("u0","present",1.0,"e0",AssignmentKind.SIMULATED),
            unit("u1","removed",0.7,"e1",AssignmentKind.SIMULATED))
        r=base(units=us,pairs=(pair(),),claims=(claim(),))
        self.assertEqual(r.claim_dispositions,(("c","simulation_only"),))
        self.assertEqual(r.disposition,CausalDisposition.ASSOCIATIONAL_ONLY)
    def test_pair_context_family_must_match(self):
        us=(unit("u0","present",1.0,"e0"),
            StudyUnit("u1","family-1","other","source-u1","i","removed",0.7,"whole-output",("e1",),AssignmentKind.RANDOMIZED))
        es=(evidence("e0"),CausalEvidence("e1","src-e1","experiment",EvidenceReview.REVIEWED,"other"))
        self.assertIn("pair_context_family_mismatch:p",base(units=us,evidence=es,pairs=(pair(),)).issues)
    def test_no_claim_remains_associational_only(self):
        self.assertEqual(base().disposition,CausalDisposition.ASSOCIATIONAL_ONLY)
    def test_disputed_evidence_does_not_certify_causality(self):
        r=base(pairs=(pair(),),claims=(claim(),),evidence=(evidence("e0",review=EvidenceReview.DISPUTED),evidence("e1")))
        self.assertFalse(r.causal_truth_established)

if __name__ == "__main__": unittest.main()
