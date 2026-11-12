import base64
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.e09_authority_services import (
    E09AuthenticatedWorkload,
    E09AuthenticationError,
    E09AuthorizationError,
    E09AuthorityService,
    E09VerifierService,
)
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_verification_receipt import verify_e09_verification_receipt
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore


class _Authenticator:
    def __init__(self, identities):
        self.identities = identities

    def authenticate(self, credential):
        if credential not in self.identities:
            raise ValueError("unknown test credential")
        return self.identities[credential]


class _Signer:
    def __init__(self, private_key):
        self.private_key = private_key

    def sign(self, issuer_id, message):
        if issuer_id != "issuer-authority":
            raise ValueError("unknown issuer")
        return base64.b64encode(self.private_key.sign(message)).decode("ascii")


class _FixedClock:
    def __init__(self, current):
        self.current = current

    def now(self):
        return self.current


class _NamedSigner:
    def __init__(self, private_key, key_id):
        self.private_key = private_key
        self.key_id = key_id

    def sign(self, issuer_id, message):
        if issuer_id != self.key_id:
            raise ValueError("unexpected signer key ID")
        return base64.b64encode(self.private_key.sign(message)).decode("ascii")


def _identity(workload_id, issuer_id, roles, scopes):
    return E09AuthenticatedWorkload(
        workload_id=workload_id,
        issuer_id=issuer_id,
        roles=frozenset(roles),
        scopes=frozenset(scopes),
        identity_provider="test-spiffe-authority",
        authentication_method="mTLS",
        credential_fingerprint=hashlib.sha256(workload_id.encode()).hexdigest(),
    )


class E09AuthorityServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.episode = "episode-authority-service"
        self.scope = "world/authority"
        self.track = "learner-a"
        self.store = SQLiteEvidenceStore(Path(self.tmp.name) / "e09.db")
        self.private = Ed25519PrivateKey.generate()
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.keyring = E09Ed25519IssuerKeyring({"issuer-authority": public})
        self.authenticator = _Authenticator({
            "observer-cert": _identity("spiffe://zhouyi/observer", "issuer-observer",
                                        {"observer"}, {self.scope}),
            "evaluator-cert": _identity("spiffe://zhouyi/evaluator", "issuer-evaluator",
                                         {"evaluator"}, {self.scope}),
            "authorizer-cert": _identity("spiffe://zhouyi/authorizer", "issuer-authority",
                                          {"authorizer"}, {self.scope}),
            "learner-cert": _identity("spiffe://zhouyi/learner", "issuer-learner",
                                       {"learner"}, {self.scope}),
            "wrong-scope-cert": _identity("spiffe://zhouyi/other", "issuer-other",
                                           {"authorizer"}, {"world/other"}),
        })
        self.domain_registry = StaticE09DomainRegistry({
            self.scope: E09DomainBinding(
                domain_id="domain:authority", world_family="family-a",
                registry_id="registry:authority", registry_version="v1",
            ),
        })
        self.authority = E09AuthorityService(
            self.store, authenticator=self.authenticator, signer=_Signer(self.private),
            clock=_FixedClock(datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)),
            max_grant_ttl=timedelta(hours=1), domain_registry=self.domain_registry,
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _prior_prediction(self):
        observation_id = "obs-1"
        observation_event = f"{self.episode}:observation:{observation_id}"
        self.authority.append_observation(
            "observer-cert", episode_id=self.episode, event_id=observation_event,
            idempotency_key=observation_event,
            payload={"observation_id": observation_id, "query_id": observation_id,
                     "scope": self.scope, "split": "SUPPORT"},
        )
        prediction_id = "prediction-1"
        commit_event = f"{self.episode}:prediction:{prediction_id}"
        semantic_digest = hashlib.sha256(prediction_id.encode()).hexdigest()
        commit = self.authority.append_prediction_commit(
            "learner-cert", episode_id=self.episode, event_id=commit_event,
            idempotency_key=commit_event, causation_refs=[observation_event],
            payload={"prediction_id": prediction_id, "observation_id": observation_id,
                     "query_id": observation_id, "scope": self.scope, "split": "SUPPORT",
                     "model_version": "model-1", "learner_track": self.track,
                     "decision_status": "PREDICT", "interop_commit_digest": semantic_digest},
        )
        reveal_ref = f"{self.episode}:reveal:{prediction_id}"
        self.authority.append_evidence_reveal(
            "evaluator-cert", episode_id=self.episode, event_id=reveal_ref,
            idempotency_key=reveal_ref,
            payload={"prediction_id": prediction_id, "query_id": observation_id,
                     "scope": self.scope, "split": "SUPPORT",
                     "commit_digest": semantic_digest, "event_digest": commit.payload_digest,
                     "learner_track": self.track, "target_or_feedback": "raw-label-secret"},
            causation_refs=[commit_event],
        )
        return reveal_ref

    def test_authenticated_evaluator_role_is_derived_and_audited(self):
        reveal_ref = self._prior_prediction()
        reveal = next(
            event for event in self.store.replay_episode(self.episode)
            if event["event_id"] == reveal_ref
        )
        self.assertEqual(reveal["actor_role"], "evaluator")
        self.assertEqual(
            reveal["integrity_metadata"]["authenticated_workload"]["workload_id"],
            "spiffe://zhouyi/evaluator",
        )
        self.assertEqual(reveal["payload"]["target_or_feedback"], "raw-label-secret")

    def test_learner_cannot_append_reveal(self):
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_evidence_reveal(
                "learner-cert", episode_id=self.episode, event_id="reveal-denied",
                idempotency_key="reveal-denied",
                payload={"scope": self.scope, "target_or_feedback": "x"},
                causation_refs=[],
            )

    def test_unknown_credentials_fail_authentication(self):
        with self.assertRaises(E09AuthenticationError):
            self.authority.append_evidence_reveal(
                "unknown-cert", episode_id=self.episode, event_id="reveal-denied",
                idempotency_key="reveal-denied",
                payload={"scope": self.scope, "target_or_feedback": "x"},
                causation_refs=[],
            )

    def test_authorizer_scope_is_enforced(self):
        with self.assertRaises(E09AuthorizationError):
            self.authority.issue_branch_merge_authorization(
                "wrong-scope-cert", episode_id=self.episode, authorization_id="grant-denied",
                scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
                evidence_refs=["reveal-1"], ttl=timedelta(minutes=45),
            )

    def test_signed_grant_is_bound_to_authenticated_issuer_and_service_clock(self):
        reveal_ref = self._prior_prediction()
        receipt = self.authority.issue_branch_merge_authorization(
            "authorizer-cert", episode_id=self.episode, authorization_id="grant-1",
            scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
            evidence_refs=[reveal_ref], ttl=timedelta(minutes=45),
        )
        self.assertEqual(receipt.sequence_no, 4)
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            domain_registry=self.domain_registry,
        )
        permit = verifier.verify_branch_merge_authorization(
            episode_id=self.episode, authorization_ref="grant-1",
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
        )
        self.assertEqual(permit.issuer_id, "issuer-authority")
        self.assertEqual(permit.verifier_id, self.keyring.verifier_id)
        self.assertTrue(permit.domain_provenance_verified)

    def test_verifier_issues_signed_redacted_cross_process_receipt(self):
        reveal_ref = self._prior_prediction()
        self.authority.issue_branch_merge_authorization(
            "authorizer-cert", episode_id=self.episode, authorization_id="grant-receipt",
            scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
            evidence_refs=[reveal_ref], ttl=timedelta(minutes=45),
        )
        verifier_private = Ed25519PrivateKey.generate()
        verifier_public = verifier_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            receipt_signer=_NamedSigner(verifier_private, self.keyring.verifier_id),
            domain_registry=self.domain_registry,
        )
        receipt = verifier.issue_verification_receipt(
            episode_id=self.episode, authorization_ref="grant-receipt",
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
            candidate_evidence_refs=[reveal_ref],
        )
        receipt_keyring = E09Ed25519IssuerKeyring({self.keyring.verifier_id: verifier_public})
        verified = verify_e09_verification_receipt(
            receipt, signature_verifier=receipt_keyring.verify,
            trusted_verifier_id=self.keyring.verifier_id,
            now=datetime(2026, 11, 12, 0, 30, 30, tzinfo=timezone.utc),
            expected_scope=self.scope, expected_parent_state_ref="parent-1",
            expected_branch_ids=("left", "right"), expected_evidence_refs=(reveal_ref,),
            expected_authorization_evidence_refs=(reveal_ref,),
        )
        self.assertEqual(verified.authorization_ref, "grant-receipt")
        self.assertEqual(verified.evidence[0].outcome, f"opaque-e09-evidence-ref:{reveal_ref}")
        self.assertEqual(verified.evidence[0].domain_id, "domain:authority")
        self.assertEqual(verified.evidence[0].domain_registry_id, "registry:authority")
        self.assertEqual(verified.evidence[0].domain_registry_version, "v1")
        self.assertEqual(receipt["schema_version"], "e09_verification_receipt@2")
        self.assertNotIn("target_or_feedback", receipt["evidence"][0])

    def test_verifier_rejects_caller_supplied_world_family_override(self):
        reveal_ref = self._prior_prediction()
        self.authority.issue_branch_merge_authorization(
            "authorizer-cert", episode_id=self.episode, authorization_id="grant-override",
            scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
            evidence_refs=[reveal_ref], ttl=timedelta(minutes=45),
        )
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            domain_registry=self.domain_registry,
        )
        with self.assertRaisesRegex(E09AuthorizationError, "overrides are forbidden"):
            verifier.verify_branch_merge_authorization(
                episode_id=self.episode, authorization_ref="grant-override",
                parent_state_ref="parent-1", branch_ids=("left", "right"),
                scope=self.scope, learner_track=self.track,
                world_family_by_evidence={reveal_ref: "attacker-selected-family"},
            )

    def test_caller_cannot_supply_verification_time(self):
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
        )
        with self.assertRaises(E09AuthorizationError):
            verifier.verify_branch_merge_authorization(now=datetime.now(timezone.utc))


    def test_authority_rejects_grant_lifetime_above_policy(self):
        with self.assertRaises(E09AuthorizationError):
            self.authority.issue_branch_merge_authorization(
                "authorizer-cert", episode_id=self.episode, authorization_id="grant-too-long",
                scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
                evidence_refs=["reveal-1"], ttl=timedelta(hours=2),
            )

    def test_authorizer_identity_not_request_payload_controls_issuer(self):
        reveal_ref = self._prior_prediction()
        receipt = self.authority.issue_branch_merge_authorization(
            "authorizer-cert", episode_id=self.episode, authorization_id="grant-2",
            scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
            evidence_refs=[reveal_ref], ttl=timedelta(minutes=45),
        )
        event = next(e for e in self.store.replay_episode(self.episode) if e["event_id"] == "grant-2")
        self.assertEqual(event["payload"]["issuer_id"], "issuer-authority")
        self.assertEqual(event["actor_role"], "authorizer")
        self.assertFalse(receipt.replayed)


if __name__ == "__main__":
    unittest.main()
