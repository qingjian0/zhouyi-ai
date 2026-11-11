import unittest
from dataclasses import replace

from prototype.e12a8_signed_evaluator_receipts import (
    EvaluatorSigner, ReceiptReplayGuard, verify_receipt,
)
from prototype.e12a8_evaluator_firewall import Evaluator, run_learner_process

SUPPORT = ((0,0,1),(1,0,0),(0,1,2),(1,1,1),(2,0,2),(0,2,0))

class E12A10SignedReceiptTests(unittest.TestCase):
    def setUp(self):
        self.signer = EvaluatorSigner.generate("eval-prod", "key-2026-01")
        self.commit = run_learner_process("signed-1", SUPPORT, (2,2))
        self.verdict = Evaluator({"signed-1": 1}).evaluate(self.commit)

    def _receipt(self, sequence=1):
        return self.signer.sign_verdict(
            self.commit, self.verdict, candidate_ref="rule@1",
            scope_digest="sha256:scope-a", dataset_version="z3-v1",
            split_id="locked-test-01", sequence=sequence)

    def test_valid_receipt_verifies_with_public_key(self):
        receipt = self._receipt()
        self.assertTrue(verify_receipt(receipt, self.signer.public_key_bytes(),
            expected_context={"candidate_ref":"rule@1", "split_id":"locked-test-01"}))

    def test_payload_tampering_is_rejected(self):
        receipt = self._receipt()
        tampered = replace(receipt, gold_label=2)
        with self.assertRaises(ValueError):
            verify_receipt(tampered, self.signer.public_key_bytes())

    def test_signature_from_wrong_key_is_rejected(self):
        receipt = self._receipt()
        other = EvaluatorSigner.generate("other", "other-key")
        with self.assertRaises(ValueError):
            verify_receipt(receipt, other.public_key_bytes())

    def test_context_substitution_is_rejected(self):
        receipt = self._receipt()
        with self.assertRaises(ValueError):
            verify_receipt(receipt, self.signer.public_key_bytes(),
                           expected_context={"dataset_version":"attacker-dataset"})

    def test_replay_is_rejected(self):
        receipt = self._receipt()
        guard = ReceiptReplayGuard()
        verify_receipt(receipt, self.signer.public_key_bytes(), replay_guard=guard)
        with self.assertRaises(ValueError):
            verify_receipt(receipt, self.signer.public_key_bytes(), replay_guard=guard)

    def test_sequence_gap_is_rejected(self):
        receipt = self._receipt(sequence=2)
        with self.assertRaises(ValueError):
            verify_receipt(receipt, self.signer.public_key_bytes(),
                           replay_guard=ReceiptReplayGuard())

    def test_duplicate_commit_with_new_sequence_is_rejected(self):
        guard = ReceiptReplayGuard()
        first = self._receipt(sequence=1)
        verify_receipt(first, self.signer.public_key_bytes(), replay_guard=guard)
        second = self._receipt(sequence=2)
        with self.assertRaises(ValueError):
            verify_receipt(second, self.signer.public_key_bytes(), replay_guard=guard)

    def test_receipt_is_bound_to_prediction_commit(self):
        with self.assertRaises(ValueError):
            self.signer.sign_verdict(self.commit,
                replace(self.verdict, commit_digest="0"*64),
                candidate_ref="rule@1", scope_digest="s", dataset_version="d",
                split_id="test", sequence=1)

if __name__ == "__main__":
    unittest.main()
