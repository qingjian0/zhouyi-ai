import unittest
from prototype.yixiang_inference_audit import (
    AnchorRole, AuditDecision, EvidenceAnchor, InferenceMove,
    InferenceMoveClaim, audit_inference_move,
)


def claim(move=InferenceMove.EXEMPLIFICATION, roles=None, **overrides):
    refs = {AnchorRole.SOURCE: "src:1", AnchorRole.TARGET: "tgt:1",
            AnchorRole.PRECEDENT: "precedent:1", AnchorRole.STANDARD: "standard:1"}
    anchors = tuple(EvidenceAnchor(role, refs[role], f"{role.value} evidence")
                    for role in (roles or (AnchorRole.SOURCE, AnchorRole.TARGET)))
    values = dict(claim_id="claim-1", move=move, source_observation_id="obs-a",
        target_observation_id="obs-b", shared_basis=("same relation role",),
        warrant="the shared basis is relevant under the stated scope",
        conclusion="provisional extension", scope_conditions=("same operating context",),
        known_differences=("material differs",), anchors=anchors)
    values.update(overrides)
    return InferenceMoveClaim(**values)


class InferenceMoveAuditTests(unittest.TestCase):
    def test_complete_move_only_ready_for_human_review(self):
        result = audit_inference_move(claim())
        self.assertEqual(result.decision, AuditDecision.HUMAN_REVIEW)
        self.assertEqual(result.claim_ceiling, "argument_form_and_traceability_only")
        self.assertIn("not_truth_certified", result.explicit_non_claims)

    def test_missing_scope_blocks(self):
        result = audit_inference_move(claim(scope_conditions=()))
        self.assertEqual(result.decision, AuditDecision.BLOCKED)
        self.assertIn("MISSING_SCOPE_CONDITIONS", result.reason_codes)

    def test_missing_known_difference_blocks(self):
        result = audit_inference_move(claim(known_differences=()))
        self.assertIn("MISSING_KNOWN_DIFFERENCES", result.reason_codes)

    def test_class_extension_requires_source_and_target(self):
        result = audit_inference_move(claim(move=InferenceMove.CLASS_EXTENSION))
        self.assertEqual(result.decision, AuditDecision.HUMAN_REVIEW)

    def test_precedent_requires_precedent_and_target(self):
        result = audit_inference_move(claim(move=InferenceMove.PRECEDENT_APPEAL,
            roles=(AnchorRole.PRECEDENT, AnchorRole.TARGET)))
        self.assertEqual(result.decision, AuditDecision.HUMAN_REVIEW)

    def test_standard_requires_standard_and_target(self):
        result = audit_inference_move(claim(move=InferenceMove.STANDARD_COMPARISON,
            roles=(AnchorRole.STANDARD, AnchorRole.TARGET)))
        self.assertEqual(result.decision, AuditDecision.HUMAN_REVIEW)

    def test_parallel_form_requires_source_and_target(self):
        result = audit_inference_move(claim(move=InferenceMove.PARALLEL_FORM))
        self.assertEqual(result.decision, AuditDecision.HUMAN_REVIEW)

    def test_missing_move_specific_role_blocks(self):
        result = audit_inference_move(claim(move=InferenceMove.PRECEDENT_APPEAL))
        self.assertIn("MISSING_MOVE_SPECIFIC_EVIDENCE_ROLE", result.reason_codes)

    def test_duplicate_anchor_ref_is_reported(self):
        anchors = (EvidenceAnchor(AnchorRole.SOURCE, "same", "source"),
                   EvidenceAnchor(AnchorRole.TARGET, "same", "target"))
        result = audit_inference_move(claim(anchors=anchors))
        self.assertIn("DUPLICATE_EVIDENCE_ANCHOR", result.reason_codes)

    def test_same_source_and_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            audit_inference_move(claim(target_observation_id="obs-a"))

    def test_invalid_anchor_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EvidenceAnchor"):
            audit_inference_move(claim(anchors=("not-an-anchor",)))


if __name__ == "__main__":
    unittest.main()
