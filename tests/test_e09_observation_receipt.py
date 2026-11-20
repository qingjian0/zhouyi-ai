import base64
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_observation_receipt import (
    E09ObservationReceiptError,
    E09ObservationReceiptVerifier,
    build_observation_receipt,
)


class _Signer:
    def __init__(self, key):
        self.key = key

    def sign(self, verifier_id, message):
        return base64.b64encode(self.key.sign(message)).decode("ascii")


class E09ObservationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.verifier_id = "e09-observation-verifier-v1"
        self.keyring = E09Ed25519IssuerKeyring({self.verifier_id: public})
        self.registry = StaticE09DomainRegistry({
            "world:test": E09DomainBinding(
                domain_id="domain:test", world_family="family:test",
                registry_id="registry:test", registry_version="v1",
            )
        })
        self.verifier = E09ObservationReceiptVerifier(
            signature_verifier=self.keyring.verify,
            trusted_verifier_id=self.verifier_id,
            domain_registry=self.registry,
            clock=lambda: self.now,
        )
        self.receipt = self.make_receipt()

    def make_receipt(self, **changes):
        args = dict(
            signer=_Signer(self.private),
            verifier_id=self.verifier_id,
            episode_id="episode:test",
            scope="world:test",
            learner_track="learner:test",
            candidate_record_id="candidate:1",
            candidate_record_digest=hashlib.sha256(b"candidate body").hexdigest(),
            domain_id="domain:test",
            world_family="family:test",
            domain_registry_id="registry:test",
            domain_registry_version="v1",
            observations=[{
                "event_id": "episode:test:reveal:1",
                "event_digest": hashlib.sha256(b"event").hexdigest(),
                "observation_id": "observation:1",
                "episode_id": "episode:test",
            }],
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        args.update(changes)
        return build_observation_receipt(**args)

    def verify(self, receipt=None, **expected):
        args = dict(
            candidate_record_id="candidate:1",
            candidate_record_digest=hashlib.sha256(b"candidate body").hexdigest(),
            expected_scope="world:test",
        )
        args.update(expected)
        return self.verifier.verify(self.receipt if receipt is None else receipt, **args)

    def test_valid_receipt_binds_candidate_and_observation(self):
        verified = self.verify()
        self.assertEqual(verified.candidate_record_id, "candidate:1")
        self.assertEqual(verified.event_ids, ("episode:test:reveal:1",))
        self.assertEqual(verified.observation_ids, ("observation:1",))
        self.assertEqual(verified.domain_registry_version, "v1")

    def test_candidate_body_digest_mismatch_is_rejected(self):
        with self.assertRaisesRegex(E09ObservationReceiptError, "body digest mismatch"):
            self.verify(candidate_record_digest="0" * 64)

    def test_cross_scope_is_rejected(self):
        with self.assertRaisesRegex(E09ObservationReceiptError, "scope mismatch"):
            self.verify(expected_scope="world:other")

    def test_expired_receipt_is_rejected(self):
        self.now += timedelta(minutes=1)
        with self.assertRaisesRegex(E09ObservationReceiptError, "expired"):
            self.verify()

    def test_tampered_event_binding_invalidates_signature(self):
        altered = dict(self.receipt)
        altered["observations"] = [dict(self.receipt["observations"][0])]
        altered["observations"][0]["event_id"] = "forged:event"
        with self.assertRaisesRegex(E09ObservationReceiptError, "signature is invalid"):
            self.verify(altered)

    def test_revoked_domain_registration_is_rejected(self):
        self.registry.revoke("world:test")
        with self.assertRaisesRegex(E09ObservationReceiptError, "missing or revoked"):
            self.verify()

    def test_unknown_fields_fail_closed(self):
        altered = dict(self.receipt)
        altered["debug"] = "not-signed-schema"
        with self.assertRaisesRegex(E09ObservationReceiptError, "missing or unknown"):
            self.verify(altered)


if __name__ == "__main__":
    unittest.main()
