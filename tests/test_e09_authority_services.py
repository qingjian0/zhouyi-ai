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


class _DomainRegistry:
    def resolve(self, *, episode_id, scope, observation_id):
        from prototype.e09_authority_services import E09DomainBinding
        return E09DomainBinding(
            world_family="family-a",
            registry_id="zhouyi-domain-registry",
            registry_version="2026-11-12.1",
        )


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
        self.authority = E09AuthorityService(
            self.store, authenticator=self.authenticator, signer=_Signer(self.private),
            clock=_FixedClock(datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)),
            max_grant_ttl=timedelta(hours=1),
            domain_registry=_DomainRegistry(),
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _prior_prediction(self):
        observation_id = "obs-1"
        observation_event = f"{self.episode}:observation:{observation_id}"
        self.authority.append_observation(
            "observer-cert", episode_id=self.episode, event_id=observation_event,
            idempotency_key=observation_event, observation_id=observation_id,
            query_id=observation_id, scope=self.scope, split="SUPPORT",
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
        )
        permit = verifier.verify_branch_merge_authorization(
            episode_id=self.episode, authorization_ref="grant-1",
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
            world_family_by_evidence={reveal_ref: "family-a"},
        )
        self.assertEqual(permit.issuer_id, "issuer-authority")
        self.assertEqual(permit.verifier_id, self.keyring.verifier_id)

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
        )
        receipt = verifier.issue_verification_receipt(
            episode_id=self.episode, authorization_ref="grant-receipt",
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
            world_family_by_evidence={reveal_ref: "family-a"},
            candidate_evidence_refs=[reveal_ref],
            candidate_evidence_world_family_by_ref={reveal_ref: "family-a"},
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
        self.assertIn("domain-registry:zhouyi-domain-registry@2026-11-12.1",
                      verified.evidence[0].provenance)
        self.assertNotIn("target_or_feedback", receipt["evidence"][0])

    def test_receipt_rejects_caller_world_family_relabel(self):
        reveal_ref = self._prior_prediction()
        self.authority.issue_branch_merge_authorization(
            "authorizer-cert", episode_id=self.episode, authorization_id="grant-spoof",
            scope=self.scope, parent_state_ref="parent-1", branch_ids=["left", "right"],
            evidence_refs=[reveal_ref], ttl=timedelta(minutes=45),
        )
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            receipt_signer=_NamedSigner(Ed25519PrivateKey.generate(), self.keyring.verifier_id),
        )
        with self.assertRaises(E09AuthorizationError):
            verifier.issue_verification_receipt(
                episode_id=self.episode, authorization_ref="grant-spoof",
                parent_state_ref="parent-1", branch_ids=("left", "right"),
                scope=self.scope, learner_track=self.track,
                world_family_by_evidence={reveal_ref: "attacker-family"},
                candidate_evidence_refs=[reveal_ref],
                candidate_evidence_world_family_by_ref={reveal_ref: "family-a"},
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


    def test_authenticated_structure_and_revision_writes_bind_scope_track_and_causation(self):
        bootstrap_ref = f"{self.episode}:structure:v1"
        self.authority.append_structure_version(
            "learner-cert", episode_id=self.episode, event_id=bootstrap_ref,
            idempotency_key=bootstrap_ref, scope=self.scope, learner_track=self.track,
            payload={"structure_id": "rules", "version_id": "v1", "kind": "rule_set",
                     "definition": {"snapshot": {"rules": []}},
                     "parent_version_ids": [], "support_evidence_ids": []},
        )
        reveal_ref = self._prior_prediction()
        next_ref = f"{self.episode}:structure:v2"
        self.authority.append_structure_version(
            "learner-cert", episode_id=self.episode, event_id=next_ref,
            idempotency_key=next_ref, scope=self.scope, learner_track=self.track,
            causation_refs=[reveal_ref],
            payload={"structure_id": "rules", "version_id": "v2", "kind": "rule_set",
                     "definition": {"snapshot": {"rules": ["r1"]}},
                     "parent_version_ids": ["v1"], "support_evidence_ids": [reveal_ref]},
        )
        revision_ref = f"{self.episode}:revision:rev-1"
        self.authority.append_revision(
            "learner-cert", episode_id=self.episode, event_id=revision_ref,
            idempotency_key=revision_ref, scope=self.scope, learner_track=self.track,
            causation_refs=[reveal_ref, next_ref],
            payload={"revision_id": "rev-1", "operation": "ADD_RULE",
                     "trigger_evidence_ids": [reveal_ref],
                     "before_version_ids": ["v1"], "after_version_ids": ["v2"]},
        )
        events = self.store.replay_episode(self.episode)
        structure = next(e for e in events if e["event_id"] == next_ref)
        revision = next(e for e in events if e["event_id"] == revision_ref)
        self.assertEqual(structure["actor_role"], "learner")
        self.assertEqual(structure["payload"]["scope"], self.scope)
        self.assertEqual(structure["payload"]["learner_track"], self.track)
        self.assertEqual(revision["actor_role"], "learner")
        self.assertEqual(revision["integrity_metadata"]["authenticated_workload"]["workload_id"],
                         "spiffe://zhouyi/learner")

    def test_structure_write_rejects_wrong_role_scope_and_unbound_support(self):
        bootstrap_ref = f"{self.episode}:structure:v1"
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_structure_version(
                "evaluator-cert", episode_id=self.episode, event_id=bootstrap_ref,
                idempotency_key=bootstrap_ref, scope=self.scope, learner_track=self.track,
                payload={"structure_id": "rules", "version_id": "v1", "kind": "rule_set",
                         "definition": {}, "parent_version_ids": [], "support_evidence_ids": []},
            )
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_structure_version(
                "wrong-scope-cert", episode_id=self.episode, event_id=bootstrap_ref,
                idempotency_key=bootstrap_ref, scope=self.scope, learner_track=self.track,
                payload={"structure_id": "rules", "version_id": "v1", "kind": "rule_set",
                         "definition": {}, "parent_version_ids": [], "support_evidence_ids": []},
            )
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_structure_version(
                "learner-cert", episode_id=self.episode, event_id=bootstrap_ref,
                idempotency_key=bootstrap_ref, scope=self.scope, learner_track=self.track,
                causation_refs=[],
                payload={"structure_id": "rules", "version_id": "v1", "kind": "rule_set",
                         "definition": {}, "parent_version_ids": ["missing"],
                         "support_evidence_ids": ["missing-reveal"]},
            )

    def test_revision_requires_trigger_and_resulting_structure_causation(self):
        bootstrap_ref = f"{self.episode}:structure:v1"
        self.authority.append_structure_version(
            "learner-cert", episode_id=self.episode, event_id=bootstrap_ref,
            idempotency_key=bootstrap_ref, scope=self.scope, learner_track=self.track,
            payload={"structure_id": "rules", "version_id": "v1", "kind": "rule_set",
                     "definition": {}, "parent_version_ids": [], "support_evidence_ids": []},
        )
        reveal_ref = self._prior_prediction()
        next_ref = f"{self.episode}:structure:v2"
        self.authority.append_structure_version(
            "learner-cert", episode_id=self.episode, event_id=next_ref,
            idempotency_key=next_ref, scope=self.scope, learner_track=self.track,
            causation_refs=[reveal_ref],
            payload={"structure_id": "rules", "version_id": "v2", "kind": "rule_set",
                     "definition": {}, "parent_version_ids": ["v1"],
                     "support_evidence_ids": [reveal_ref]},
        )
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_revision(
                "learner-cert", episode_id=self.episode, event_id="revision-missing-cause",
                idempotency_key="revision-missing-cause", scope=self.scope,
                learner_track=self.track, causation_refs=[reveal_ref],
                payload={"revision_id": "rev-bad", "operation": "ADD_RULE",
                         "trigger_evidence_ids": [reveal_ref],
                         "before_version_ids": ["v1"], "after_version_ids": ["v2"]},
            )


    def test_prediction_commit_requires_same_episode_observation_causation(self):
        observation_id = "obs-causal"
        observation_event = f"{self.episode}:observation:{observation_id}"
        self.authority.append_observation(
            "observer-cert", episode_id=self.episode, event_id=observation_event,
            idempotency_key=observation_event, observation_id=observation_id,
            query_id=observation_id, scope=self.scope, split="SUPPORT",
        )
        payload = {
            "prediction_id": "prediction-causal", "observation_id": observation_id,
            "query_id": observation_id, "scope": self.scope, "split": "SUPPORT",
            "model_version": "model-1", "learner_track": self.track,
            "decision_status": "PREDICT",
        }
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_prediction_commit(
                "learner-cert", episode_id=self.episode, event_id="commit-no-cause",
                idempotency_key="commit-no-cause", payload=payload, causation_refs=[],
            )
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_prediction_commit(
                "learner-cert", episode_id="other-episode", event_id="commit-wrong-episode",
                idempotency_key="commit-wrong-episode", payload=payload,
                causation_refs=[observation_event],
            )

    def test_reveal_requires_causation_to_the_exact_committed_prediction(self):
        reveal_ref = self._prior_prediction()
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_evidence_reveal(
                "evaluator-cert", episode_id=self.episode, event_id="reveal-no-cause",
                idempotency_key="reveal-no-cause",
                payload={"prediction_id": "prediction-1", "query_id": "obs-1",
                         "scope": self.scope, "split": "SUPPORT",
                         "commit_digest": "digest", "event_digest": "digest",
                         "learner_track": self.track, "target_or_feedback": "x"},
                causation_refs=[],
            )

    def test_adapter_workload_validation_requires_trusted_domain_registry(self):
        authority_without_registry = E09AuthorityService(
            self.store, authenticator=self.authenticator, signer=_Signer(self.private),
        )
        with self.assertRaises(E09AuthorizationError):
            authority_without_registry.validate_adapter_workloads(
                scope=self.scope, observer_credential="observer-cert",
                learner_credential="learner-cert", evaluator_credential="evaluator-cert",
            )


if __name__ == "__main__":
    unittest.main()
