import unittest
from prototype.yixiang_inference_audit import (
    AnchorRole, AuditDecision, EvidenceAnchor, InferenceMove,
    InferenceMoveClaim, audit_inference_move,
)


def claim(move=InferenceMove.EXEMPLIFICATION, roles=None, **overrides):
    refs = {AnchorRole.SOURCE: "src:1", AnchorRole.TARGET: "tgt:1",
            AnchorRole.PRECEDENT: "precedent:1", AnchorRole.STANDARD: "standard:1"}
    observation_ids = {AnchorRole.SOURCE: "obs-a", AnchorRole.TARGET: "obs-b",
                       AnchorRole.PRECEDENT: "precedent-obs", AnchorRole.STANDARD: "standard-obs"}
    anchors = tuple(EvidenceAnchor(role, refs[role], f"{role.value} evidence", observation_ids[role])
                    for role in (roles or (AnchorRole.SOURCE, AnchorRole.TARGET)))
    values = dict(claim_id="claim-1", move=move, source_observation_id="obs-a",
        target_observation_id="obs-b", shared_basis=("same relation role",),
        warrant="the shared basis is relevant under the stated scope",
        conclusion="provisional extension", scope_conditions=("same operating context",),
        known_differences=("material differs",), anchors=anchors,
        evidence_refs=tuple(refs[role] for role in (roles or (AnchorRole.SOURCE, AnchorRole.TARGET))))
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
        anchors = (EvidenceAnchor(AnchorRole.SOURCE, "same", "source", "obs-a"),
                   EvidenceAnchor(AnchorRole.TARGET, "same", "target", "obs-b"))
        result = audit_inference_move(claim(anchors=anchors, evidence_refs=("same",)))
        self.assertIn("DUPLICATE_EVIDENCE_ANCHOR", result.reason_codes)


    def test_unlinked_anchor_is_blocked(self):
        result = audit_inference_move(claim(evidence_refs=("different-ref",)))
        self.assertIn("UNLINKED_EVIDENCE_ANCHOR", result.reason_codes)

    def test_source_anchor_must_match_source_observation(self):
        anchors = (EvidenceAnchor(AnchorRole.SOURCE, "src:1", "source evidence", "wrong-obs"),
                   EvidenceAnchor(AnchorRole.TARGET, "tgt:1", "target evidence", "obs-b"))
        result = audit_inference_move(claim(anchors=anchors))
        self.assertIn("SOURCE_ANCHOR_OBSERVATION_MISMATCH", result.reason_codes)

    def test_same_source_and_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must differ"):
            audit_inference_move(claim(target_observation_id="obs-a"))

    def test_invalid_anchor_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "EvidenceAnchor"):
            audit_inference_move(claim(anchors=("not-an-anchor",)))


if __name__ == "__main__":
    unittest.main()
