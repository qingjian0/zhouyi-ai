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
    StaticE09LearnerBindingResolver,
)
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_verification_receipt import verify_e09_verification_receipt
from prototype.e09_observation_receipt import E09ObservationReceiptVerifier
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore
from prototype.observation_contract import (
    EpistemicStatus, EvidenceRef, GroundingStatus, RecordEnvelope,
    SemanticUnitCandidate, TruthStatus, UnitKind, record_digest,
)


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


class _CandidateStore:
    def __init__(self, candidate):
        self.candidate = candidate

    def get_candidate(self, record_id):
        if self.candidate.envelope.record_id != record_id:
            return None
        return self.candidate


def _candidate_record(scope):
    return SemanticUnitCandidate(
        envelope=RecordEnvelope(
            schema_version="m2-record-v1",
            record_id="m2:candidate:1",
            record_kind="SemanticUnitCandidate",
            producer="test-extractor",
            producer_version="1",
            recorded_at="2026-11-12T00:00:00Z",
            scope=scope,
            source_refs=(EvidenceRef(
                document_id="doc-1",
                chunk_id="chunk-1",
                content_sha256=hashlib.sha256(b"candidate-source").hexdigest(),
                byte_start=0,
                byte_end=1,
                source_version="m1-v1",
            ),),
        ),
        kind=UnitKind.EVENT,
        surface_forms=("candidate",),
        grounding_status=GroundingStatus.GROUNDED,
        epistemic_status=EpistemicStatus.ASSERTED,
        truth_status=TruthStatus.UNKNOWN,
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

    def test_observation_input_is_stored_only_for_authority_resolved_learner(self):
        resolver = StaticE09LearnerBindingResolver({
            (self.episode, self.scope, self.track): "spiffe://zhouyi/learner",
        })
        authority = E09AuthorityService(
            self.store, authenticator=self.authenticator, signer=_Signer(self.private),
            clock=_FixedClock(datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)),
            max_grant_ttl=timedelta(hours=1), domain_registry=self.domain_registry,
            learner_binding_resolver=resolver,
        )
        inputs = {"features": [0, 1, 2], "source": "fixture"}
        result = authority.put_observation_input(
            "observer-cert", episode_id=self.episode, scope=self.scope,
            learner_track=self.track, feature_schema_version="e09-features-v1",
            payload=inputs,
        )
        self.assertEqual(result["payload_ref"], __import__(
            "prototype.shared_evidence_protocol", fromlist=["digest_payload"]
        ).digest_payload(inputs))
        self.assertEqual(self.store.get_payload(result["payload_ref"]), inputs)
        self.assertNotIn("assigned_learner_workload_id", result)

        with self.assertRaises(E09AuthorizationError):
            authority.put_observation_input(
                "observer-cert", episode_id=self.episode, scope=self.scope,
                learner_track="unassigned-track",
                feature_schema_version="e09-features-v1", payload=inputs,
            )
        with self.assertRaises(E09AuthorizationError):
            self.authority.put_observation_input(
                "observer-cert", episode_id=self.episode, scope=self.scope,
                learner_track=self.track, feature_schema_version="e09-features-v1",
                payload=inputs,
            )

    def test_observation_payload_reference_requires_existing_verified_vault_entry(self):
        from prototype.shared_evidence_protocol import digest_payload

        inputs = {"features": ["a", "b"], "source": "test"}
        payload_ref = digest_payload(inputs)
        self.store.put_payload(payload_ref, inputs)
        event_id = f"{self.episode}:payload-observation"
        receipt = self.authority.append_observation(
            "observer-cert", episode_id=self.episode, event_id=event_id,
            idempotency_key=event_id,
            payload={
                "observation_id": "payload-observation",
                "query_id": "payload-query",
                "scope": self.scope,
                "split": "SUPPORT",
                "payload_ref": payload_ref,
                "feature_schema_version": "e09-features-v1",
            },
        )
        stored = next(
            event for event in self.store.replay_episode(self.episode)
            if event["event_id"] == event_id
        )
        self.assertEqual(stored["payload"]["payload_ref"], payload_ref)
        self.assertEqual(stored["payload"]["feature_schema_version"], "e09-features-v1")
        self.assertEqual(stored["payload_schema"], "observation@6")
        self.assertEqual(receipt.event_id, event_id)

        missing_ref = digest_payload({"missing": "vault-entry"})
        with self.assertRaises(E09AuthorizationError):
            self.authority.append_observation(
                "observer-cert", episode_id=self.episode,
                event_id=f"{self.episode}:missing-payload-observation",
                idempotency_key=f"{self.episode}:missing-payload-observation",
                payload={
                    "observation_id": "missing-payload-observation",
                    "query_id": "missing-payload-query",
                    "scope": self.scope,
                    "split": "SUPPORT",
                    "payload_ref": missing_ref,
                    "feature_schema_version": "e09-features-v1",
                },
            )

    def test_trusted_learner_assignment_is_resolved_and_enforced(self):
        resolver = StaticE09LearnerBindingResolver({
            (self.episode, self.scope, self.track): "spiffe://zhouyi/learner",
        })
        authority = E09AuthorityService(
            self.store, authenticator=self.authenticator, signer=_Signer(self.private),
            clock=_FixedClock(datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)),
            max_grant_ttl=timedelta(hours=1), domain_registry=self.domain_registry,
            learner_binding_resolver=resolver,
        )
        observation_event = f"{self.episode}:bound-observation"
        authority.append_observation(
            "observer-cert", episode_id=self.episode, event_id=observation_event,
            idempotency_key=observation_event,
            payload={"observation_id": "bound-obs", "query_id": "bound-query",
                     "scope": self.scope, "split": "SUPPORT", "learner_track": self.track},
        )
        stored = self.store.replay_episode(self.episode)[0]["payload"]
        self.assertEqual(stored["learner_track"], self.track)
        self.assertEqual(stored["learner_workload_id"], "spiffe://zhouyi/learner")

        commit_payload = {
            "prediction_id": "bound-prediction", "observation_id": "bound-obs",
            "query_id": "bound-query", "scope": self.scope, "split": "SUPPORT",
            "model_version": "model-1", "learner_track": self.track,
            "decision_status": "PREDICT",
            "interop_commit_digest": hashlib.sha256(b"bound-prediction").hexdigest(),
        }
        authority.append_prediction_commit(
            "learner-cert", episode_id=self.episode,
            event_id=f"{self.episode}:bound-commit",
            idempotency_key=f"{self.episode}:bound-commit",
            causation_refs=[observation_event], payload=commit_payload,
        )
        forged = dict(commit_payload, prediction_id="forged-track", learner_track="learner-b")
        with self.assertRaises(E09AuthorizationError):
            authority.append_prediction_commit(
                "learner-cert", episode_id=self.episode,
                event_id=f"{self.episode}:forged-commit",
                idempotency_key=f"{self.episode}:forged-commit",
                causation_refs=[observation_event], payload=forged,
            )

    def test_secure_binding_requires_track_and_known_assignment(self):
        resolver = StaticE09LearnerBindingResolver({})
        authority = E09AuthorityService(
            self.store, authenticator=self.authenticator, signer=_Signer(self.private),
            domain_registry=self.domain_registry, learner_binding_resolver=resolver,
        )
        with self.assertRaises(E09AuthorizationError):
            authority.append_observation(
                "observer-cert", episode_id=self.episode, event_id="unassigned-observation",
                idempotency_key="unassigned-observation",
                payload={"observation_id": "unassigned", "query_id": "unassigned",
                         "scope": self.scope, "split": "SUPPORT", "learner_track": self.track},
            )

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

    def test_verifier_issues_candidate_bound_yixiang_observation_receipt(self):
        reveal_ref = self._prior_prediction()
        verifier_private = Ed25519PrivateKey.generate()
        verifier_public = verifier_private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        candidate_record = _candidate_record(self.scope)
        candidate_digest = record_digest(candidate_record)
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            receipt_signer=_NamedSigner(verifier_private, self.keyring.verifier_id),
            domain_registry=self.domain_registry,
            candidate_store=_CandidateStore(candidate_record),
        )
        receipt = verifier.issue_yixiang_observation_receipt(
            episode_id=self.episode,
            evidence_refs=[reveal_ref],
            scope=self.scope,
            learner_track=self.track,
            candidate_record_id=candidate_record.envelope.record_id,
            candidate_record_digest=candidate_digest,
        )
        receipt_keyring = E09Ed25519IssuerKeyring({
            self.keyring.verifier_id: verifier_public,
        })
        trusted_verifier = E09ObservationReceiptVerifier(
            signature_verifier=receipt_keyring.verify,
            trusted_verifier_id=self.keyring.verifier_id,
            domain_registry=self.domain_registry,
            clock=lambda: datetime(2026, 11, 12, 0, 30, 30, tzinfo=timezone.utc),
        )
        verified = trusted_verifier.verify(
            receipt,
            candidate_record_id=candidate_record.envelope.record_id,
            candidate_record_digest=candidate_digest,
            expected_scope=self.scope,
        )
        self.assertEqual(verified.event_ids, (reveal_ref,))
        self.assertEqual(verified.observation_ids, ("obs-1",))
        self.assertEqual(verified.domain_id, "domain:authority")
        self.assertEqual(verified.domain_registry_version, "v1")
        self.assertEqual(verified.candidate_record_digest, candidate_digest)
        self.assertEqual(receipt["audience"], "zhouyi-m2-yixiang-adapter")

    def test_observation_receipt_issuance_rejects_unstored_or_substituted_candidates(self):
        reveal_ref = self._prior_prediction()
        verifier_private = Ed25519PrivateKey.generate()
        signer = _NamedSigner(verifier_private, self.keyring.verifier_id)
        candidate_record = _candidate_record(self.scope)
        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            receipt_signer=signer,
            domain_registry=self.domain_registry,
        )
        digest = record_digest(candidate_record)
        with self.assertRaisesRegex(E09AuthorizationError, "authoritative M2 candidate store is required"):
            verifier.issue_yixiang_observation_receipt(
                episode_id=self.episode, evidence_refs=[reveal_ref], scope=self.scope,
                learner_track=self.track, candidate_record_id=candidate_record.envelope.record_id,
                candidate_record_digest=digest,
            )

        verifier = E09VerifierService(
            self.store, signature_verifier=self.keyring.verify,
            verifier_id=self.keyring.verifier_id,
            clock=_FixedClock(datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)),
            receipt_signer=signer,
            domain_registry=self.domain_registry,
            candidate_store=_CandidateStore(candidate_record),
        )
        with self.assertRaisesRegex(E09AuthorizationError, "does not match the authoritative M2 candidate"):
            verifier.issue_yixiang_observation_receipt(
                episode_id=self.episode, evidence_refs=[reveal_ref], scope=self.scope,
                learner_track=self.track, candidate_record_id=candidate_record.envelope.record_id,
                candidate_record_digest=hashlib.sha256(b"substituted").hexdigest(),
            )

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
