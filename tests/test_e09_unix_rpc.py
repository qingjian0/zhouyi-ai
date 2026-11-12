import hashlib
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from prototype.e09_authority_services import (
    E09AuthenticatedWorkload,
    E09AuthenticationError,
    E09AuthorityService,
    E09DomainBinding,
)
from prototype.e09_unix_rpc import (
    E09AuthorityUnixRPC,
    UnixPeerWorkloadAuthenticator,
)
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.unix_ipc import (
    IPCRemoteError,
    StaticUnixPeerResolver,
    UnixJSONRPCClient,
)


class _UnusedSigner:
    def sign(self, issuer_id, message):
        return "unused-test-signature"


class _DomainRegistry:
    def resolve(self, *, episode_id, scope, observation_id):
        return E09DomainBinding(
            world_family="family-test",
            registry_id="test-registry",
            registry_version="1",
        )


class _LearnerBindingRegistry:
    def resolve(self, *, episode_id, scope, learner_track):
        if learner_track != "track-a":
            raise ValueError("unassigned learner track")
        return "spiffe://zhouyi/learner"


def _principal(workload_id, role, scope):
    return E09AuthenticatedWorkload(
        workload_id=workload_id,
        issuer_id=f"issuer-{role}",
        roles=frozenset({role}),
        scopes=frozenset({scope}),
        identity_provider="test-unix-peer",
        authentication_method="SO_PEERCRED",
        credential_fingerprint=hashlib.sha256(workload_id.encode()).hexdigest(),
    )


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED"), "Linux SO_PEERCRED is required")
class E09AuthorityUnixRPCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scope = "scope/rpc-test"
        self.episode = "episode-rpc-test"
        self.observer = _principal("spiffe://zhouyi/observer", "observer", self.scope)
        self.learner = _principal("spiffe://zhouyi/learner", "learner", self.scope)
        self.other_learner = _principal("spiffe://zhouyi/learner-other", "learner", self.scope)
        self.evaluator = _principal("spiffe://zhouyi/evaluator", "evaluator", self.scope)
        self.authenticator = UnixPeerWorkloadAuthenticator({
            p.workload_id: p for p in (
                self.observer, self.learner, self.other_learner, self.evaluator
            )
        })
        self.store = SQLiteEvidenceStore(self.root / "e09.sqlite")
        self.authority = E09AuthorityService(
            self.store,
            authenticator=self.authenticator,
            signer=_UnusedSigner(),
            domain_registry=_DomainRegistry(),
            learner_binding_resolver=_LearnerBindingRegistry(),
        )
        self._counter = 0

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _client(self, principal):
        self._counter += 1
        socket_path = self.root / f"rpc-{self._counter}.sock"
        resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                principal.workload_id, principal.roles, principal.scopes,
            ),
        })
        server = E09AuthorityUnixRPC(
            self.authority, peer_resolver=resolver, socket_path=str(socket_path),
        )
        server.start()
        deadline = time.monotonic() + 2
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(socket_path.exists())
        return server, UnixJSONRPCClient(socket_path)

    def _call(self, principal, operation, body, operation_id):
        server, client = self._client(principal)
        try:
            return client.request(operation, body, operation_id=operation_id)
        finally:
            server.close()

    def test_observer_learner_evaluator_rpc_roles_and_lineage(self):
        observation_input = {"features": ["wind", "rain"], "value": 7}
        stored = self._call(
            self.observer, "observation.put_input",
            {"scope": self.scope, "payload": observation_input}, "put-input-1",
        )
        observation_event = f"{self.episode}:observation:obs-1"
        observation = self._call(
            self.observer, "observation.append",
            {
                "episode_id": self.episode,
                "event_id": observation_event,
                "observation_id": "obs-1",
                "query_id": "query-1",
                "scope": self.scope,
                "split": "SUPPORT",
                "learner_track": "track-a",
                "payload_ref": stored["payload_ref"],
                "feature_schema_version": "features-v1",
            },
            "append-observation-1",
        )
        self.assertEqual(observation["event_id"], observation_event)
        stored_observation = next(
            event for event in self.store.replay_episode(self.episode)
            if event["event_id"] == observation_event
        )
        self.assertEqual(
            stored_observation["payload"].get("learner_workload_id"),
            self.learner.workload_id,
        )

        loaded = self._call(
            self.learner, "observation.read_input",
            {"episode_id": self.episode, "observation_id": "obs-1", "scope": self.scope},
            "read-input-1",
        )
        self.assertEqual(loaded["payload"], observation_input)
        with self.assertRaises(IPCRemoteError) as input_error:
            self._call(
                self.other_learner, "observation.read_input",
                {"episode_id": self.episode, "observation_id": "obs-1", "scope": self.scope},
                "read-other-learners-input",
            )
        self.assertEqual(input_error.exception.code, "permission_denied")

        prediction_id = "prediction-1"
        commit_event = f"{self.episode}:prediction:{prediction_id}"
        digest = "a" * 64
        commit = self._call(
            self.learner, "prediction.commit",
            {
                "episode_id": self.episode,
                "event_id": commit_event,
                "causation_refs": [observation_event],
                "payload": {
                    "prediction_id": prediction_id,
                    "observation_id": "obs-1",
                    "query_id": "query-1",
                    "scope": self.scope,
                    "split": "SUPPORT",
                    "model_version": "model-1",
                    "learner_track": "track-a",
                    "decision_status": "PREDICT",
                    "interop_commit_digest": digest,
                    "actor_role": "evaluator",
                },
            },
            "commit-prediction-1",
        )
        self.assertEqual(commit["event_id"], commit_event)

        reveal_event = f"{self.episode}:reveal:{prediction_id}"
        reveal = self._call(
            self.evaluator, "evidence.reveal",
            {
                "episode_id": self.episode,
                "event_id": reveal_event,
                "causation_refs": [commit_event],
                "payload": {
                    "prediction_id": prediction_id,
                    "query_id": "query-1",
                    "scope": self.scope,
                    "split": "SUPPORT",
                    "commit_digest": digest,
                    "event_digest": commit["payload_digest"],
                    "learner_track": "track-a",
                    "target_or_feedback": "secret-label",
                    "reveal_source": "test",
                },
            },
            "reveal-evidence-1",
        )
        self.assertEqual(reveal["event_id"], reveal_event)

        learned_feedback = self._call(
            self.learner, "evidence.read_support_feedback",
            {
                "episode_id": self.episode,
                "reveal_event_id": reveal_event,
                "scope": self.scope,
            },
            "read-support-feedback-1",
        )
        self.assertEqual(learned_feedback["feedback"], "secret-label")
        self.assertEqual(learned_feedback["prediction_id"], prediction_id)

        learner_projection = self._call(
            self.learner, "episode.read_for_learner",
            {
                "episode_id": self.episode,
                "scope": self.scope,
                "learner_track": "track-a",
            },
            "read-learner-episode-1",
        )
        self.assertTrue(learner_projection["events"])
        self.assertNotIn("secret-label", str(learner_projection))
        reveal_projection = next(
            item for item in learner_projection["events"]
            if item["event_id"] == reveal_event
        )
        self.assertNotIn("target_or_feedback", reveal_projection["payload"])
        self.assertNotIn("reveal_source", reveal_projection["payload"])

        with self.assertRaises(IPCRemoteError) as evaluator_error:
            self._call(
                self.evaluator, "episode.read_for_learner",
                {
                    "episode_id": self.episode,
                    "scope": self.scope,
                    "learner_track": "track-a",
                },
                "evaluator-read-learner-episode",
            )
        self.assertEqual(evaluator_error.exception.code, "permission_denied")

        events = self.store.replay_episode(self.episode)
        by_id = {event["event_id"]: event for event in events}
        self.assertEqual(by_id[observation_event]["actor_role"], "observer")
        self.assertEqual(by_id[commit_event]["actor_role"], "learner")
        self.assertEqual(by_id[reveal_event]["actor_role"], "evaluator")
        self.assertEqual(
            by_id[commit_event]["integrity_metadata"]["authenticated_workload"]["workload_id"],
            self.learner.workload_id,
        )
        self.assertEqual(by_id[commit_event]["actor_role"], "learner")
        self.assertEqual(by_id[reveal_event]["payload"]["target_or_feedback"], "secret-label")

    def test_learner_cannot_read_gate_feedback(self):
        observation_event = f"{self.episode}:observation:gate-obs"
        self._call(
            self.observer, "observation.append",
            {
                "episode_id": self.episode,
                "event_id": observation_event,
                "observation_id": "gate-obs",
                "query_id": "gate-query",
                "scope": self.scope,
                "split": "GATE_DEV",
                "learner_track": "track-a",
            },
            "append-gate-observation",
        )
        prediction_id = "gate-prediction"
        commit_event = f"{self.episode}:prediction:{prediction_id}"
        digest = "b" * 64
        commit = self._call(
            self.learner, "prediction.commit",
            {
                "episode_id": self.episode,
                "event_id": commit_event,
                "causation_refs": [observation_event],
                "payload": {
                    "prediction_id": prediction_id,
                    "observation_id": "gate-obs",
                    "query_id": "gate-query",
                    "scope": self.scope,
                    "split": "GATE_DEV",
                    "model_version": "model-1",
                    "learner_track": "track-a",
                    "decision_status": "PREDICT",
                    "interop_commit_digest": digest,
                },
            },
            "commit-gate-prediction",
        )
        reveal_event = f"{self.episode}:reveal:{prediction_id}"
        self._call(
            self.evaluator, "evidence.reveal",
            {
                "episode_id": self.episode,
                "event_id": reveal_event,
                "causation_refs": [commit_event],
                "payload": {
                    "prediction_id": prediction_id,
                    "query_id": "gate-query",
                    "scope": self.scope,
                    "split": "GATE_DEV",
                    "commit_digest": digest,
                    "event_digest": commit["payload_digest"],
                    "learner_track": "track-a",
                    "target_or_feedback": "must-not-leak",
                    "reveal_source": "test",
                },
            },
            "reveal-gate-evidence",
        )
        with self.assertRaises(IPCRemoteError) as caught:
            self._call(
                self.learner, "evidence.read_support_feedback",
                {
                    "episode_id": self.episode,
                    "reveal_event_id": reveal_event,
                    "scope": self.scope,
                },
                "read-gate-feedback",
            )
        self.assertEqual(caught.exception.code, "permission_denied")

    def test_support_feedback_and_replay_are_bound_to_the_committing_learner(self):
        observation_event = f"{self.episode}:observation:identity-obs"
        self._call(
            self.observer, "observation.append",
            {
                "episode_id": self.episode, "event_id": observation_event,
                "observation_id": "identity-obs", "query_id": "identity-query",
                "scope": self.scope, "split": "SUPPORT",
                "learner_track": "track-a",
            },
            "identity-observation",
        )
        prediction_id = "identity-prediction"
        commit_event = f"{self.episode}:prediction:{prediction_id}"
        digest = "c" * 64
        commit = self._call(
            self.learner, "prediction.commit",
            {
                "episode_id": self.episode, "event_id": commit_event,
                "causation_refs": [observation_event],
                "payload": {
                    "prediction_id": prediction_id, "observation_id": "identity-obs",
                    "query_id": "identity-query", "scope": self.scope,
                    "split": "SUPPORT", "model_version": "model-1",
                    "learner_track": "track-a", "decision_status": "PREDICT",
                    "interop_commit_digest": digest,
                },
            },
            "identity-commit",
        )
        reveal_event = f"{self.episode}:reveal:{prediction_id}"
        self._call(
            self.evaluator, "evidence.reveal",
            {
                "episode_id": self.episode, "event_id": reveal_event,
                "causation_refs": [commit_event],
                "payload": {
                    "prediction_id": prediction_id, "query_id": "identity-query",
                    "scope": self.scope, "split": "SUPPORT",
                    "commit_digest": digest, "event_digest": commit["payload_digest"],
                    "learner_track": "track-a", "target_or_feedback": "private-to-learner-a",
                    "reveal_source": "test",
                },
            },
            "identity-reveal",
        )
        with self.assertRaises(IPCRemoteError) as feedback_error:
            self._call(
                self.other_learner, "evidence.read_support_feedback",
                {"episode_id": self.episode, "reveal_event_id": reveal_event, "scope": self.scope},
                "other-learner-feedback",
            )
        self.assertEqual(feedback_error.exception.code, "permission_denied")
        other_projection = self._call(
            self.other_learner, "episode.read_for_learner",
            {"episode_id": self.episode, "scope": self.scope, "learner_track": "track-a"},
            "other-learner-projection",
        )
        self.assertEqual(other_projection["events"], [])

    def test_observer_cannot_choose_learner_workload_or_unassigned_track(self):
        with self.assertRaises(IPCRemoteError) as forged:
            self._call(
                self.observer, "observation.append",
                {
                    "episode_id": self.episode,
                    "event_id": "forged-observation",
                    "observation_id": "forged-observation",
                    "query_id": "forged-query",
                    "scope": self.scope,
                    "split": "SUPPORT",
                    "learner_track": "track-a",
                    "learner_workload_id": self.other_learner.workload_id,
                },
                "forged-learner-binding",
            )
        self.assertEqual(forged.exception.code, "invalid_body")

        with self.assertRaises(IPCRemoteError) as unassigned:
            self._call(
                self.observer, "observation.append",
                {
                    "episode_id": self.episode,
                    "event_id": "unassigned-observation",
                    "observation_id": "unassigned-observation",
                    "query_id": "unassigned-query",
                    "scope": self.scope,
                    "split": "SUPPORT",
                    "learner_track": "track-unknown",
                },
                "unassigned-learner-track",
            )
        self.assertEqual(unassigned.exception.code, "permission_denied")

    def test_learner_cannot_append_observation_or_reveal(self):
        with self.assertRaises(IPCRemoteError) as observation_error:
            self._call(
                self.learner, "observation.append",
                {
                    "episode_id": self.episode, "event_id": "obs-denied",
                    "observation_id": "obs-denied", "query_id": "q",
                    "scope": self.scope, "split": "SUPPORT",
                    "learner_track": "track-a",
                },
                "obs-denied",
            )
        self.assertEqual(observation_error.exception.code, "permission_denied")

        with self.assertRaises(IPCRemoteError) as reveal_error:
            self._call(
                self.learner, "evidence.reveal",
                {
                    "episode_id": self.episode, "event_id": "reveal-denied",
                    "causation_refs": [],
                    "payload": {"scope": self.scope, "target_or_feedback": "secret"},
                },
                "reveal-denied",
            )
        self.assertEqual(reveal_error.exception.code, "permission_denied")

    def test_rpc_rejects_malformed_causation_array_before_store_access(self):
        with self.assertRaises(IPCRemoteError) as caught:
            self._call(
                self.learner, "prediction.commit",
                {
                    "episode_id": self.episode,
                    "event_id": "commit-invalid",
                    "causation_refs": "not-an-array",
                    "payload": {},
                },
                "commit-invalid",
            )
        self.assertEqual(caught.exception.code, "invalid_body")

    def test_peer_claims_must_match_authority_workload_policy(self):
        forged = _principal("spiffe://zhouyi/observer", "learner", self.scope)
        from prototype.unix_ipc import UnixPeerIdentity
        with self.assertRaises(E09AuthenticationError):
            self.authenticator.authenticate(
                UnixPeerIdentity(
                    pid=os.getpid(), uid=os.getuid(), gid=os.getgid(),
                    workload_id=forged.workload_id,
                    roles=forged.roles, scopes=forged.scopes,
                )
            )


if __name__ == "__main__":
    unittest.main()
