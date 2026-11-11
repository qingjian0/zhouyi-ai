import base64
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.e09_e12a6_evidence_bridge import branch_merge_authorization_signing_bytes
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring


class E09AuthorizationEnvelopeV2Tests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.keyring = E09Ed25519IssuerKeyring({"issuer-v2": public})
        self.event = {
            "episode_id": "episode-1",
            "event_id": "episode-1:authorization:1",
            "event_type": "branch_merge_authorization",
            "protocol_version": "0.3",
            "payload_schema": "branch_merge_authorization@2",
            "actor_role": "authorizer",
            "causation_refs": ["reveal-1"],
            "integrity_metadata": {"policy": "branch-merge-v2"},
            "payload": {
                "authorization_id": "episode-1:authorization:1",
                "issuer_id": "issuer-v2",
                "scope": "world/1",
                "parent_state_ref": "state-1",
                "branch_ids": ["left", "right"],
                "evidence_refs": ["reveal-1"],
                "issued_at": "2026-11-12T00:00:00+00:00",
                "expires_at": "2026-11-12T01:00:00+00:00",
                "signature_algorithm": "Ed25519",
                "signature_version": "E09-AUTHZ-SIG-V2",
                "audience": "e12a6-lifecycle",
                "authorization_sequence": 10,
            },
        }
        self.signed = branch_merge_authorization_signing_bytes(self.event)
        self.signature = base64.b64encode(self.private.sign(self.signed)).decode("ascii")

    def test_exact_envelope_verifies(self):
        self.assertTrue(self.keyring("issuer-v2", "Ed25519", self.signed, self.signature))

    def test_every_security_envelope_field_is_bound(self):
        mutations = {
            "episode_id": "episode-2",
            "event_id": "episode-1:authorization:2",
            "event_type": "evidence_reveal",
            "protocol_version": "0.2",
            "payload_schema": "branch_merge_authorization@1",
            "actor_role": "runner",
            "causation_refs": ["different-reveal"],
            "integrity_metadata": {"policy": "weakened"},
        }
        for field, changed in mutations.items():
            with self.subTest(field=field):
                altered = dict(self.event)
                altered[field] = changed
                changed_bytes = branch_merge_authorization_signing_bytes(altered)
                self.assertFalse(self.keyring("issuer-v2", "Ed25519", changed_bytes, self.signature))

    def test_every_grant_field_is_bound(self):
        for field, value in self.event["payload"].items():
            with self.subTest(field=field):
                altered = dict(self.event)
                altered["payload"] = dict(self.event["payload"])
                if isinstance(value, list):
                    altered["payload"][field] = value + ["changed"]
                elif isinstance(value, int):
                    altered["payload"][field] = value + 1
                else:
                    altered["payload"][field] = value + "-changed"
                changed_bytes = branch_merge_authorization_signing_bytes(altered)
                self.assertFalse(self.keyring("issuer-v2", "Ed25519", changed_bytes, self.signature))

    def test_domain_separation(self):
        self.assertIn(b"zhouyi:e09:branch-merge:v2", self.signed)


if __name__ == "__main__":
    unittest.main()
