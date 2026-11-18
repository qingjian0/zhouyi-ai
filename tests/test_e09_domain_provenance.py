import hashlib
import tempfile
import unittest
from pathlib import Path

from prototype.e09_authority_services import (
    E09AuthenticatedWorkload, E09AuthorizationError, E09AuthorityService,
)
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e09_e12a6_evidence_bridge import (
    E09EvidenceBindingError, resolve_e09_reveal,
)
from prototype.shared_evidence_protocol import (
    DOMAIN_BOUND_PROTOCOL_VERSION, ProtocolError, SQLiteEvidenceStore,
)


class Authenticator:
    def __init__(self, identities):
        self.identities = identities

    def authenticate(self, credential):
        if credential not in self.identities:
            raise ValueError("unknown credential")
        return self.identities[credential]


class Signer:
    def sign(self, issuer_id, message):
        return "unused-test-signature"


def identity(name, roles, scope):
    return E09AuthenticatedWorkload(
        workload_id=f"spiffe://test/{name}",
        issuer_id=f"issuer:{name}",
        roles=frozenset(roles),
        scopes=frozenset({scope}),
        identity_provider="test-spiffe",
        authentication_method="mTLS",
        credential_fingerprint=hashlib.sha256(name.encode()).hexdigest(),
    )


class E09DomainProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteEvidenceStore(Path(self.tmp.name) / "e09.db")
        self.scope = "world/domain-test"
        self.episode = "episode-domain-test"
        self.registry = StaticE09DomainRegistry({
            self.scope: E09DomainBinding(
                domain_id="domain:trusted-a",
                world_family="family:trusted-a",
                registry_id="registry:production",
                registry_version="2026-11-v1",
            ),
        })
        self.auth = Authenticator({
            "observer": identity("observer", {"observer"}, self.scope),
            "learner": identity("learner", {"learner"}, self.scope),
            "evaluator": identity("evaluator", {"evaluator"}, self.scope),
        })
        self.authority = E09AuthorityService(
            self.store, authenticator=self.auth, signer=Signer(),
            domain_registry=self.registry,
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def append_observation(self):
        event_id = f"{self.episode}:observation:obs-1"
        receipt = self.authority.append_observation(
            "observer", episode_id=self.episode, event_id=event_id,
            idempotency_key=event_id,
            payload={
                "observation_id": "obs-1", "query_id": "query-1",
                "scope": self.scope, "split": "SUPPORT",
            },
        )
        return event_id, receipt

    def append_commit(self):
        observation_event, _ = self.append_observation()
        commit_event = f"{self.episode}:prediction:pred-1"
        digest = hashlib.sha256(b"pred-1").hexdigest()
        receipt = self.authority.append_prediction_commit(
            "learner", episode_id=self.episode, event_id=commit_event,
            idempotency_key=commit_event, causation_refs=[observation_event],
            payload={
                "prediction_id": "pred-1", "observation_id": "obs-1",
                "model_version": "model-1", "learner_track": "track-1",
                "decision_status": "PREDICT", "query_id": "query-1",
                "scope": self.scope, "split": "SUPPORT",
                "interop_commit_digest": digest,
            },
        )
        return observation_event, commit_event, digest, receipt

    def append_reveal(self):
        _, commit_event, digest, commit = self.append_commit()
        reveal_event = f"{self.episode}:reveal:pred-1"
        self.authority.append_evidence_reveal(
            "evaluator", episode_id=self.episode, event_id=reveal_event,
            idempotency_key=reveal_event, causation_refs=[commit_event],
            payload={
                "prediction_id": "pred-1", "learner_track": "track-1",
                "target_or_feedback": "private-label", "query_id": "query-1",
                "scope": self.scope, "split": "SUPPORT",
                "commit_digest": digest, "event_digest": commit.payload_digest,
            },
        )
        return reveal_event

    def test_observation_domain_is_derived_from_registry(self):
        event_id, _ = self.append_observation()
        event = next(e for e in self.store.replay_episode(self.episode) if e["event_id"] == event_id)
        self.assertEqual(event["protocol_version"], DOMAIN_BOUND_PROTOCOL_VERSION)
        self.assertEqual(event["payload_schema"], "observation@4")
        self.assertEqual(event["actor_role"], "observer")
        self.assertEqual(event["payload"]["domain_id"], "domain:trusted-a")
        self.assertEqual(event["payload"]["world_family"], "family:trusted-a")
        self.assertEqual(event["payload"]["domain_registry_id"], "registry:production")
        self.assertEqual(event["payload"]["domain_registry_version"], "2026-11-v1")

    def test_unknown_observation_fields_are_rejected(self):
        with self.assertRaisesRegex(E09AuthorizationError, "exact v0.4 caller schema"):
            self.authority.append_observation(
                "observer", episode_id=self.episode, event_id="obs-extra",
                idempotency_key="obs-extra",
                payload={
                    "observation_id": "obs-1", "query_id": "query-1",
                    "scope": self.scope, "split": "SUPPORT",
                    "world_family": "attacker-family",
                },
            )

    def test_missing_or_revoked_registry_entries_fail_closed(self):
        missing_registry = StaticE09DomainRegistry({
            "world/other": E09DomainBinding("d", "f", "r", "v1"),
        })
        missing_authority = E09AuthorityService(
            self.store, authenticator=self.auth, signer=Signer(),
            domain_registry=missing_registry,
        )
        with self.assertRaisesRegex(E09AuthorizationError, "missing or revoked"):
            missing_authority.append_observation(
                "observer", episode_id=self.episode, event_id="obs-missing",
                idempotency_key="obs-missing",
                payload={"observation_id": "obs-missing", "query_id": "q",
                         "scope": self.scope, "split": "SUPPORT"},
            )
        self.registry.revoke(self.scope)
        with self.assertRaisesRegex(E09AuthorizationError, "missing or revoked"):
            self.append_observation()

    def test_commit_cannot_relabel_observation_domain(self):
        observation_event, _ = self.append_observation()
        binding = self.registry.resolve(self.scope)
        metadata = {"authenticated_workload": {
            "workload_id": "spiffe://test/learner", "issuer_id": "issuer:learner",
            "identity_provider": "test-spiffe", "authentication_method": "mTLS",
            "credential_fingerprint": hashlib.sha256(b"learner").hexdigest(),
        }}
        payload = {
            "prediction_id": "pred-bad", "observation_id": "obs-1",
            "model_version": "model-1", "learner_track": "track-1",
            "decision_status": "PREDICT", "query_id": "query-1",
            "scope": self.scope, "split": "SUPPORT",
            "interop_commit_digest": hashlib.sha256(b"pred-bad").hexdigest(),
            "domain_id": "domain:attacker", "world_family": "family:attacker",
            "domain_registry_id": binding.registry_id,
            "domain_registry_version": binding.registry_version,
        }
        with self.assertRaisesRegex(ProtocolError, "does not match trusted observation"):
            self.store.append_event(
                episode_id=self.episode, event_id="commit-bad",
                event_type="prediction_commit", idempotency_key="commit-bad",
                payload=payload, actor_role="learner",
                causation_refs=[observation_event], integrity_metadata=metadata,
                payload_schema="prediction_commit@4",
                protocol_version=DOMAIN_BOUND_PROTOCOL_VERSION,
            )

    def test_reveal_cannot_relabel_commit_domain(self):
        _, commit_event, digest, commit = self.append_commit()
        metadata = {"authenticated_workload": {
            "workload_id": "spiffe://test/evaluator", "issuer_id": "issuer:evaluator",
            "identity_provider": "test-spiffe", "authentication_method": "mTLS",
            "credential_fingerprint": hashlib.sha256(b"evaluator").hexdigest(),
        }}
        payload = {
            "prediction_id": "pred-1", "learner_track": "track-1",
            "target_or_feedback": "label", "query_id": "query-1",
            "scope": self.scope, "split": "SUPPORT",
            "commit_digest": digest, "event_digest": commit.payload_digest,
            "domain_id": "domain:attacker", "world_family": "family:attacker",
            "domain_registry_id": "registry:production",
            "domain_registry_version": "2026-11-v1",
        }
        with self.assertRaisesRegex(ProtocolError, "does not match trusted prediction commit"):
            self.store.append_event(
                episode_id=self.episode, event_id="reveal-bad",
                event_type="evidence_reveal", idempotency_key="reveal-bad",
                payload=payload, actor_role="evaluator",
                causation_refs=[commit_event], integrity_metadata=metadata,
                payload_schema="evidence_reveal@4",
                protocol_version=DOMAIN_BOUND_PROTOCOL_VERSION,
            )

    def test_resolver_derives_world_family_and_receipt_provenance(self):
        reveal_ref = self.append_reveal()
        evidence = resolve_e09_reveal(
            self.store, episode_id=self.episode, evidence_ref=reveal_ref,
            scope=self.scope, learner_track="track-1",
            domain_registry=self.registry,
        )
        self.assertEqual(evidence.world_family, "family:trusted-a")
        self.assertEqual(evidence.domain_id, "domain:trusted-a")
        self.assertEqual(evidence.domain_registry_id, "registry:production")
        self.assertEqual(evidence.domain_registry_version, "2026-11-v1")
        with self.assertRaisesRegex(E09EvidenceBindingError, "overrides are forbidden"):
            resolve_e09_reveal(
                self.store, episode_id=self.episode, evidence_ref=reveal_ref,
                scope=self.scope, learner_track="track-1",
                world_family="family:attacker", domain_registry=self.registry,
            )

    def test_revoked_registry_invalidates_previously_recorded_evidence(self):
        reveal_ref = self.append_reveal()
        self.registry.revoke(self.scope)
        with self.assertRaisesRegex(E09EvidenceBindingError, "missing or revoked"):
            resolve_e09_reveal(
                self.store, episode_id=self.episode, evidence_ref=reveal_ref,
                scope=self.scope, learner_track="track-1",
                domain_registry=self.registry,
            )


if __name__ == "__main__":
    unittest.main()
