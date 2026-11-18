import unittest
from prototype.yixiang_interpretation_firewall import (
    Decision, EvidenceLayer, PredicateKind, Resolution,
    YixiangInterpretationClaim, assess_interpretation,
)

class InterpretationFirewallTests(unittest.TestCase):
    def claim(self, **changes):
        values = dict(
            claim_id="interp-001", lexeme_resolution=Resolution.RESOLVED,
            referent_resolution=Resolution.RESOLVED, category_resolution=Resolution.RESOLVED,
            predicate_kind=PredicateKind.ATTRIBUTE, source_text_ref="text:mozi-xiaoqu:section-1",
            interpretation_ref="interpretation:reading-a", evidence_layer=EvidenceLayer.PRIMARY_TEXT,
            contextual_conditions=("within the cited argumentative passage",),
        )
        values.update(changes)
        return YixiangInterpretationClaim(**values)

    def test_complete_primary_text_record_is_scope_only(self):
        result = assess_interpretation(self.claim())
        self.assertEqual(result.decision, Decision.SCOPE_RECORDED)
        self.assertTrue(result.interpretation_scope_only)
        self.assertFalse(result.empirical_causality_established)

    def test_ambiguous_lexeme_blocks_fixed_referent(self):
        self.assertEqual(assess_interpretation(self.claim(lexeme_resolution=Resolution.AMBIGUOUS)).decision, Decision.REFUSE)

    def test_unknown_referent_abstains(self):
        result = assess_interpretation(self.claim(referent_resolution=Resolution.UNKNOWN))
        self.assertEqual(result.decision, Decision.ABSTAIN)
        self.assertIn("REFERENT_NOT_RESOLVED", result.reason_codes)

    def test_missing_context_abstains(self):
        result = assess_interpretation(self.claim(contextual_conditions=()))
        self.assertIn("TEXTUAL_CONTEXT_NOT_RECORDED", result.reason_codes)

    def test_competing_readings_are_not_collapsed(self):
        result = assess_interpretation(self.claim(competing_readings=("a", "b")))
        self.assertIn("COMPETING_READING_REQUIRES_ADJUDICATION", result.reason_codes)

    def test_model_output_cannot_authenticate_interpretation(self):
        result = assess_interpretation(self.claim(evidence_layer=EvidenceLayer.MODEL_OUTPUT, model_output_used_as_evidence=True))
        self.assertIn("MODEL_OUTPUT_CANNOT_AUTHENTICATE_INTERPRETATION", result.reason_codes)

    def test_commentary_stays_separate_from_primary_text(self):
        result = assess_interpretation(self.claim(evidence_layer=EvidenceLayer.COMMENTARY))
        self.assertIn("INTERPRETIVE_SOURCE_MUST_REMAIN_LAYERED", result.reason_codes)

    def test_textual_causal_claim_does_not_establish_empirical_causality(self):
        result = assess_interpretation(self.claim(predicate_kind=PredicateKind.CAUSAL, causal_status="text_claimed"))
        self.assertFalse(result.empirical_causality_established)
        self.assertIn("TEXTUAL_CAUSAL_CLAIM_REQUIRES_SEPARATE_EMPIRICAL_IDENTIFICATION", result.reason_codes)

    def test_duplicate_witness_refs_are_not_independent(self):
        result = assess_interpretation(self.claim(independent_witness_refs=("w1", "w1")))
        self.assertIn("DUPLICATE_WITNESS_REFERENCE", result.reason_codes)

if __name__ == "__main__":
    unittest.main()
