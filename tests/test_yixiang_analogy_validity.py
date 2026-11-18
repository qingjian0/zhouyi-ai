import unittest

from prototype.yixiang_analogy_validity import (
    AnalogyDecision, AnalogyTransfer, TransferKind, assess_analogy_transfer,
)


class AnalogyValidityTests(unittest.TestCase):
    def make(self, **changes):
        values = dict(
            transfer_id="a-1", source_case_ref="source:1", target_case_ref="target:1",
            transfer_kind=TransferKind.FUNCTION,
            source_relation="different_means_same_end",
            target_relation="different_means_same_end",
            shared_basis=("目的相同",),
            relevance_argument=("任务目标是当前比较维度",),
            scope_conditions=("限定于已说明的任务与条件",),
            critical_differences=("工具与过程不同",),
            source_evidence_refs=("source:edition:1",),
            target_evidence_refs=("target:edition:2",),
            counterexamples_tested=("目标变化时不再等价",),
            unresolved_defeaters=(), causal_evidence_refs=(),
        )
        values.update(changes)
        return AnalogyTransfer(**values)

    def test_complete_scoped_functional_analogy_is_accepted(self):
        result = assess_analogy_transfer(self.make())
        self.assertEqual(result.decision, AnalogyDecision.ACCEPT_SCOPED)
        self.assertIn("仅在", result.permitted_claim)

    def test_relation_mismatch_is_rejected(self):
        result = assess_analogy_transfer(self.make(target_relation="causal_chain"))
        self.assertEqual(result.decision, AnalogyDecision.REJECT)
        self.assertIn("RELATION_STRUCTURE_MISMATCH", result.reason_codes)

    def test_no_shared_basis_is_rejected(self):
        result = assess_analogy_transfer(self.make(shared_basis=()))
        self.assertEqual(result.decision, AnalogyDecision.REJECT)

    def test_missing_scope_abstains(self):
        result = assess_analogy_transfer(self.make(scope_conditions=()))
        self.assertEqual(result.decision, AnalogyDecision.ABSTAIN)
        self.assertIn("SCOPE_CONDITIONS_MISSING", result.reason_codes)

    def test_missing_relevance_argument_abstains(self):
        result = assess_analogy_transfer(self.make(relevance_argument=()))
        self.assertIn("RELEVANCE_OF_SHARED_BASIS_UNJUSTIFIED", result.reason_codes)

    def test_missing_critical_differences_abstains(self):
        result = assess_analogy_transfer(self.make(critical_differences=()))
        self.assertIn("CRITICAL_DIFFERENCES_NOT_RECORDED", result.reason_codes)

    def test_each_domain_requires_its_own_evidence(self):
        result = assess_analogy_transfer(self.make(target_evidence_refs=()))
        self.assertIn("SIDE_SPECIFIC_EVIDENCE_MISSING", result.reason_codes)

    def test_counterexample_test_is_required(self):
        result = assess_analogy_transfer(self.make(counterexamples_tested=()))
        self.assertIn("NO_COUNTEREXAMPLE_TEST", result.reason_codes)

    def test_unresolved_defeater_blocks_acceptance(self):
        result = assess_analogy_transfer(self.make(unresolved_defeaters=("目标条件尚未核实",)))
        self.assertEqual(result.decision, AnalogyDecision.ABSTAIN)
        self.assertIn("UNRESOLVED_DEFEATER_PRESENT", result.reason_codes)

    def test_causal_transfer_needs_causal_evidence(self):
        result = assess_analogy_transfer(self.make(transfer_kind=TransferKind.CAUSAL))
        self.assertIn("CAUSAL_TRANSFER_WITHOUT_CAUSAL_EVIDENCE", result.reason_codes)

    def test_causal_transfer_with_evidence_can_be_scoped(self):
        result = assess_analogy_transfer(self.make(
            transfer_kind=TransferKind.CAUSAL,
            causal_evidence_refs=("intervention:study:1",),
        ))
        self.assertEqual(result.decision, AnalogyDecision.ACCEPT_SCOPED)

    def test_invalid_tuple_is_rejected_as_bad_input(self):
        with self.assertRaises(ValueError):
            assess_analogy_transfer(self.make(shared_basis=("ok", " ")))

    def test_no_scalar_similarity_score_is_exposed(self):
        self.assertFalse(hasattr(assess_analogy_transfer(self.make()), "score"))


if __name__ == "__main__":
    unittest.main()
