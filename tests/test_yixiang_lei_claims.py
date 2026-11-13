import unittest

from prototype.yixiang_lei_claims import (
    ClaimDecision, ClaimKind, EvidenceKind, LeiClaim, assess_lei_claim,
)


class LeiClaimTests(unittest.TestCase):
    def claim(self, **overrides):
        values = dict(
            claim_id="lei-001",
            kind=ClaimKind.ARGUMENTATIVE_ANALOGY,
            subject="case-a",
            predicate_or_target="case-b",
            shared_basis=("same relational structure",),
            differences=("different material context",),
            scope_conditions=("same task class",),
            evidence_refs=("text:chapter:1",),
            evidence_kind=EvidenceKind.CLASSICAL_TEXT,
        )
        values.update(overrides)
        return LeiClaim(**values)

    def test_analogy_is_recorded_without_claiming_truth(self):
        result = assess_lei_claim(self.claim())
        self.assertEqual(result.decision, ClaimDecision.SCOPE_RECORDED)
        self.assertTrue(result.scope_only)
        self.assertEqual(result.causal_conclusion, "not_established")

    def test_no_shared_basis_is_refused(self):
        result = assess_lei_claim(self.claim(shared_basis=()))
        self.assertEqual(result.decision, ClaimDecision.REFUSE)
        self.assertIn("NO_EXPLICIT_BASIS", result.reason_codes)

    def test_action_outcome_separates_intention_action_conditions_and_result(self):
        result = assess_lei_claim(self.claim(
            kind=ClaimKind.ACTION_OUTCOME,
            actor_intention="protect the deceased",
            action_method="construct elaborate tomb",
            operating_conditions=("known grave-robbery risk",),
            observed_outcomes=("tomb was later disturbed",),
        ))
        self.assertEqual(result.decision, ClaimDecision.ABSTAIN)
        self.assertIn("CAUSALITY_NOT_ESTABLISHED", result.reason_codes)
        self.assertNotIn("INTENTION_NOT_RECORDED", result.reason_codes)
        self.assertNotIn("ACTION_METHOD_NOT_RECORDED", result.reason_codes)

    def test_action_outcome_without_intention_does_not_backfill_it(self):
        result = assess_lei_claim(self.claim(
            kind=ClaimKind.ACTION_OUTCOME,
            action_method="method-a",
            operating_conditions=("condition-a",),
            observed_outcomes=("outcome-a",),
        ))
        self.assertIn("INTENTION_NOT_RECORDED", result.reason_codes)

    def test_practical_utility_requires_criteria_and_delayed_outcome(self):
        result = assess_lei_claim(self.claim(
            kind=ClaimKind.PRACTICAL_UTILITY,
            utility_criteria=("goal achieved without unacceptable harm",),
            observed_outcomes=("initially successful",),
        ))
        self.assertEqual(result.decision, ClaimDecision.ABSTAIN)
        self.assertIn("DELAYED_RESULT_NOT_RECORDED", result.reason_codes)

    def test_model_output_cannot_authenticate_a_claim(self):
        result = assess_lei_claim(self.claim(evidence_kind=EvidenceKind.MODEL_OUTPUT))
        self.assertEqual(result.decision, ClaimDecision.ABSTAIN)
        self.assertIn("MODEL_OUTPUT_IS_NOT_INDEPENDENT_EVIDENCE", result.reason_codes)

    def test_intervention_evidence_is_still_only_a_candidate_for_review(self):
        result = assess_lei_claim(self.claim(
            kind=ClaimKind.ACTION_OUTCOME,
            actor_intention="goal",
            action_method="method",
            operating_conditions=("condition",),
            observed_outcomes=("result",),
            evidence_kind=EvidenceKind.INTERVENTION,
            causal_identification="intervention_or_identification_evidence",
        ))
        self.assertEqual(result.decision, ClaimDecision.SCOPE_RECORDED)
        self.assertEqual(
            result.causal_conclusion,
            "candidate_intervention_evidence_requires_review",
        )

    def test_symbolic_correspondence_is_separate_from_empirical_causality(self):
        result = assess_lei_claim(self.claim(
            kind=ClaimKind.SYMBOLIC_CORRESPONDENCE,
            causal_identification="not_asserted",
        ))
        self.assertEqual(result.decision, ClaimDecision.SCOPE_RECORDED)
        self.assertEqual(result.causal_conclusion, "not_established")

    def test_symbolic_correspondence_cannot_be_promoted_to_causal_claim(self):
        result = assess_lei_claim(self.claim(
            kind=ClaimKind.SYMBOLIC_CORRESPONDENCE,
            evidence_kind=EvidenceKind.INTERVENTION,
            causal_identification="intervention_or_identification_evidence",
        ))
        self.assertEqual(result.decision, ClaimDecision.ABSTAIN)
        self.assertIn(
            "SYMBOLIC_CORRESPONDENCE_CANNOT_ESTABLISH_EMPIRICAL_CAUSALITY",
            result.reason_codes,
        )

    def test_invalid_sequence_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "scope_conditions"):
            assess_lei_claim(self.claim(scope_conditions=["not-a-tuple"]))


if __name__ == "__main__":
    unittest.main()
