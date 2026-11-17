import base64
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_verification_receipt import (
    E09VerificationReceiptError,
    verify_e09_verification_receipt,
    verification_receipt_signing_bytes,
)
from prototype.e12a6_lifecycle_contract import Evidence, SplitRole


class E09VerificationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.verifier_id = "verifier-trust-bundle-v1"
        self.keyring = E09Ed25519IssuerKeyring({self.verifier_id: public})
        self.now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        evidence_id = "episode-1:reveal:prediction-1"
        self.receipt = {
            "schema_version": "e09_verification_receipt@2",
            "receipt_id": "receipt-001",
            "nonce": "nonce-001",
            "audience": "e12a6-lifecycle-writer",
            "verifier_id": self.verifier_id,
            "episode_id": "episode-1",
            "authorization_ref": "grant-001",
            "scope": "world/receipt-test",
            "parent_state_ref": "parent-001",
            "branch_ids": ["branch-a", "branch-b"],
            "authorization_evidence_refs": [evidence_id],
            "evidence_refs": [evidence_id],
            "issuer_id": "issuer-authority",
            "authorization_event_digest": "a" * 64,
            "issued_at": "2026-11-12T00:29:00+00:00",
            "expires_at": "2026-11-12T00:31:00+00:00",
            "evidence": [{
                "evidence_id": evidence_id,
                "episode_id": "episode-1",
                "world_family": "family-a",
                "split_role": SplitRole.TRAIN.value,
                "observation_id": "obs-001",
                "outcome": f"opaque-e09-evidence-ref:{evidence_id}",
                "model_version": "model-001",
                "measurement_cost": 0.0,
                "prediction_commit_step": 2,
                "label_visibility_step": 3,
                "provenance": "opaque-e09-event-digest:" + "b" * 64,
                "domain_id": "domain:receipt-test",
                "domain_registry_id": "registry:receipt-test",
                "domain_registry_version": "v1",
            }],
            "signature_algorithm": "Ed25519",
            "signature": "",
        }
        self._sign(self.receipt)

    def _sign(self, receipt):
        receipt["signature"] = base64.b64encode(
            self.private.sign(verification_receipt_signing_bytes(receipt))
        ).decode("ascii")

    def _verify(self, receipt=None, *, now=None, scope=None):
        return verify_e09_verification_receipt(
            self.receipt if receipt is None else receipt,
            signature_verifier=self.keyring.verify,
            trusted_verifier_id=self.verifier_id,
            now=self.now if now is None else now,
            expected_scope=self.receipt["scope"] if scope is None else scope,
            expected_parent_state_ref=self.receipt["parent_state_ref"],
            expected_branch_ids=("branch-a", "branch-b"),
            expected_evidence_refs=tuple(self.receipt["evidence_refs"]),
            expected_authorization_evidence_refs=tuple(self.receipt["authorization_evidence_refs"]),
        )

    def test_valid_receipt_returns_typed_redacted_evidence(self):
        verified = self._verify()
        self.assertEqual(verified.receipt_id, "receipt-001")
        self.assertEqual(verified.verifier_id, self.verifier_id)
        self.assertEqual(verified.evidence[0].split_role, SplitRole.TRAIN)
        self.assertTrue(verified.evidence[0].outcome.startswith("opaque-e09-evidence-ref:"))

    def test_any_signed_field_mutation_invalidates_receipt(self):
        altered = dict(self.receipt)
        altered["scope"] = "world/other"
        with self.assertRaises(E09VerificationReceiptError):
            self._verify(altered)

    def test_wrong_writer_scope_is_rejected(self):
        with self.assertRaises(E09VerificationReceiptError):
            self._verify(scope="world/other")

    def test_expired_receipt_is_rejected(self):
        with self.assertRaises(E09VerificationReceiptError):
            self._verify(now=datetime(2026, 11, 12, 0, 31, tzinfo=timezone.utc))

    def test_receipt_with_raw_label_is_rejected_even_when_resigned(self):
        altered = dict(self.receipt)
        altered["evidence"] = [dict(self.receipt["evidence"][0])]
        altered["evidence"][0]["outcome"] = "actual-secret-label"
        self._sign(altered)
        with self.assertRaises(E09VerificationReceiptError):
            self._verify(altered)

    def test_unknown_fields_fail_closed(self):
        altered = dict(self.receipt)
        altered["debug"] = "not-in-schema"
        with self.assertRaises(E09VerificationReceiptError):
            self._verify(altered)


if __name__ == "__main__":
    unittest.main()
