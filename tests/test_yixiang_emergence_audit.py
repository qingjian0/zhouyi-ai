import unittest

from prototype.yixiang_emergence_audit import (
    EmergenceClaim, EmergenceDecision, audit_emergence_claim,
)


def claim(**overrides):
    values = dict(
        claim_id="em-1",
        composite_proposal_id="ycx:a+b",
        emergent_property="feedback_stabilizes the whole",
        member_only_predictions=("local role correspondence", "shared function"),
        member_baseline_refs=("member:a", "member:b"),
        bridge_evidence_refs=("bridge:1",),
        composite_level_evidence_refs=("composite:1",),
        scope_conditions=("same task", "same operating range"),
        alternative_explanations=("external controller", "measurement artifact"),
        falsification_conditions=("remove feedback link", "change operating range"),
    )
    values.update(overrides)
    return EmergenceClaim(**values)


class EmergenceAuditTests(unittest.TestCase):
    def test_complete_claim_only_enters_human_review(self):
        result = audit_emergence_claim(claim())
        self.assertEqual(result.decision, EmergenceDecision.HUMAN_REVIEW)
        self.assertEqual(result.claim_ceiling, "emergence_claim_structure_and_traceability_only")
        self.assertIn("not_proof_of_ontological_emergence", result.non_claims)

    def test_property_already_predicted_by_member_is_blocked(self):
        result = audit_emergence_claim(claim(
            member_only_predictions=("feedback stabilizes the whole",),
        ))
        self.assertEqual(result.decision, EmergenceDecision.BLOCKED)
        self.assertIn("PROPERTY_ALREADY_PRESENT_IN_MEMBER_ONLY_BASELINE", result.reason_codes)

    def test_member_evidence_cannot_be_reused_as_bridge_evidence(self):
        result = audit_emergence_claim(claim(
            bridge_evidence_refs=("member:a",),
        ))
        self.assertIn("MEMBER_AND_BRIDGE_EVIDENCE_OVERLAP", result.reason_codes)

    def test_member_evidence_cannot_be_reused_as_composite_evidence(self):
        result = audit_emergence_claim(claim(
            composite_level_evidence_refs=("member:b",),
        ))
        self.assertIn("MEMBER_AND_COMPOSITE_EVIDENCE_OVERLAP", result.reason_codes)

    def test_bridge_evidence_cannot_be_reused_as_composite_evidence(self):
        result = audit_emergence_claim(claim(
            composite_level_evidence_refs=("bridge:1",),
        ))
        self.assertIn("BRIDGE_AND_COMPOSITE_EVIDENCE_OVERLAP", result.reason_codes)

    def test_missing_falsification_conditions_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "falsification_conditions"):
            audit_emergence_claim(claim(falsification_conditions=()))

    def test_missing_alternative_explanations_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "alternative_explanations"):
            audit_emergence_claim(claim(alternative_explanations=()))

    def test_duplicate_evidence_refs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be unique"):
            audit_emergence_claim(claim(member_baseline_refs=("same", "same")))


if __name__ == "__main__":
    unittest.main()
