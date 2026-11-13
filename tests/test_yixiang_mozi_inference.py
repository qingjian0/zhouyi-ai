import unittest

from prototype.yixiang_mozi_inference import (
    ConclusionKind, InferenceMove, MoziTransferClaim, RelationStatus,
    TransferDecision, assess_mozi_transfer,
)


class MoziInferenceTests(unittest.TestCase):
    def claim(self, **overrides):
        values = dict(
            claim_id="mozi-001",
            move=InferenceMove.TUI,
            conclusion_kind=ConclusionKind.STRUCTURAL,
            source_case="source-case",
            target_case="target-case",
            shared_basis=("same relevant relation",),
            material_differences=("different material context",),
            scope_conditions=("same task and reference frame",),
            supporting_refs=("text:xiaoqu:section-3",),
        )
        values.update(overrides)
        return MoziTransferClaim(**values)

    def test_move_is_not_a_truth_guarantee(self):
        result = assess_mozi_transfer(self.claim(move=InferenceMove.MOU))
        self.assertEqual(result.decision, TransferDecision.SCOPE_RECORDED)
        self.assertFalse(result.move_is_truth_guarantee)

    def test_missing_basis_is_refused(self):
        result = assess_mozi_transfer(self.claim(shared_basis=()))
        self.assertEqual(result.decision, TransferDecision.REFUSE)
        self.assertIn("NO_EXPLICIT_SHARED_BASIS", result.reason_codes)

    def test_same_predicate_label_with_different_scope_abstains(self):
        result = assess_mozi_transfer(self.claim(
            predicate_relation=RelationStatus.DIFFERENT,
        ))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)
        self.assertIn("PREDICATE_SCOPE_MISMATCH", result.reason_codes)

    def test_same_result_different_cause_blocks_causal_transfer(self):
        result = assess_mozi_transfer(self.claim(
            conclusion_kind=ConclusionKind.CAUSAL,
            causal_basis_relation=RelationStatus.DIFFERENT,
        ))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)
        self.assertIn("SAME_RESULT_DIFFERENT_CAUSE", result.reason_codes)
        self.assertEqual(result.causal_conclusion, "not_established")

    def test_unknown_cause_does_not_become_same_cause(self):
        result = assess_mozi_transfer(self.claim(
            conclusion_kind=ConclusionKind.CAUSAL,
        ))
        self.assertIn("CAUSAL_BASIS_UNIDENTIFIED", result.reason_codes)

    def test_universal_claim_requires_counterexample_search(self):
        result = assess_mozi_transfer(self.claim(universal_conclusion=True))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)
        self.assertIn("UNIVERSAL_CLAIM_WITHOUT_COUNTEREXAMPLE_SEARCH", result.reason_codes)

    def test_challenging_evidence_requires_scope_refinement(self):
        result = assess_mozi_transfer(self.claim(
            challenging_refs=("counterexample:1",),
            challenge_search_performed=True,
        ))
        self.assertEqual(result.decision, TransferDecision.ABSTAIN)
        self.assertIn("CHALLENGING_EVIDENCE_REQUIRES_SCOPE_REFINEMENT", result.reason_codes)

    def test_invalid_enum_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "move"):
            assess_mozi_transfer(self.claim(move="analogy"))


if __name__ == "__main__":
    unittest.main()
