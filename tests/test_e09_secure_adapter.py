import hashlib
import tempfile
import unittest
from pathlib import Path

from prototype.e09_authority_services import (
    E09AuthenticatedWorkload,
    E09AuthorityService,
    StaticE09LearnerBindingResolver,
)
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e09_counterexample_learner import CounterexampleRuleLearner, Example
from prototype.e09_incremental_learner import IncrementalConjunctionLearner
from prototype.e09_prequential import PrequentialRunner
from prototype.e09_shared_protocol_adapter import (
    E09ProtocolAdapterError,
    E09SharedProtocolAdapter,
)
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


DOMAINS = ((0, 1), (0, 1), (0, 1, 2))
BOOTSTRAP = [
    ("seed-1", Example((0, 0, 0), "yes")),
    ("seed-2", Example((0, 1, 0), "yes")),
    ("seed-3", Example((1, 0, 0), "no")),
    ("seed-4", Example((1, 1, 0), "no")),
]
SCOPE = "e09/test"
EPISODE = "episode-secure"
TRACK = "e09"


class Authenticator:
    identities = {
        "observer": E09AuthenticatedWorkload(
            "spiffe://test/observer", "issuer-observer", frozenset({"observer"}),
            frozenset({SCOPE}), "test-idp", "mTLS", hashlib.sha256(b"observer").hexdigest(),
        ),
        "learner": E09AuthenticatedWorkload(
            "spiffe://test/learner", "issuer-learner", frozenset({"learner"}),
            frozenset({SCOPE}), "test-idp", "mTLS", hashlib.sha256(b"learner").hexdigest(),
        ),
        "evaluator": E09AuthenticatedWorkload(
            "spiffe://test/evaluator", "issuer-evaluator", frozenset({"evaluator"}),
            frozenset({SCOPE}), "test-idp", "mTLS", hashlib.sha256(b"evaluator").hexdigest(),
        ),
    }

    def authenticate(self, credential):
        if credential not in self.identities:
            raise ValueError("unknown credential")
        return self.identities[credential]


class Signer:
    def sign(self, issuer_id, message):
        return "unused-test-signature"


def make_authority(store, *, assigned=True, additional_assignments=None):
    assignments = (
        {(EPISODE, SCOPE, TRACK): "spiffe://test/learner"}
        if assigned else {}
    )
    assignments.update(additional_assignments or {})
    return E09AuthorityService(
        store,
        authenticator=Authenticator(),
        signer=Signer(),
        domain_registry=StaticE09DomainRegistry({
            SCOPE: E09DomainBinding("domain-e09", "family-e09", "test-registry", "v1")
        }),
        learner_binding_resolver=StaticE09LearnerBindingResolver(assignments),
    )


def make_runner():
    learner = IncrementalConjunctionLearner(DOMAINS, min_support=2)
    runner = PrequentialRunner(learner, revision_mode="INCREMENTAL_INDEX")
    runner.bootstrap(BOOTSTRAP)
    return runner


class E09SecureAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / "e09.sqlite3"
        self.store = SQLiteEvidenceStore(self.database)
        self.addCleanup(lambda: self.store.close())
        self.authority = make_authority(self.store)

    def test_secure_mode_routes_all_event_writes_through_authenticated_authority(self):
        adapter = E09SharedProtocolAdapter(
            make_runner(), self.store,
            episode_id=EPISODE, scope=SCOPE,
            authority=self.authority,
            observer_credential="observer",
            learner_credential="learner",
            evaluator_credential="evaluator",
        )
        commit = adapter.predict_and_commit("obs-secure", (0, 0, 2))
        reveal_event_id = adapter.reveal(commit["prediction_id"], "no")
        adapter.revise(commit["prediction_id"])

        events = adapter.replay()
        self.assertEqual(
            [event["event_type"] for event in events],
            ["structure_version", "observation", "prediction_commit",
             "evidence_reveal", "structure_version", "revision"],
        )
        expected_roles = {
            "structure_version": "learner",
            "observation": "observer",
            "prediction_commit": "learner",
            "evidence_reveal": "evaluator",
            "revision": "learner",
        }
        for event in events:
            self.assertEqual(event["actor_role"], expected_roles[event["event_type"]])
            identity = event["integrity_metadata"]["authenticated_workload"]
            self.assertTrue(identity["workload_id"].startswith("spiffe://test/"))
            self.assertEqual(event["payload"]["world_family"], "family-e09")
        reveal = next(event for event in events if event["event_type"] == "evidence_reveal")
        self.assertEqual(reveal["event_id"], reveal_event_id)
        observation = next(event for event in events if event["event_type"] == "observation")
        self.assertEqual(observation["payload"]["learner_workload_id"], "spiffe://test/learner")

    def test_secure_resume_preserves_authority_routing(self):
        adapter = E09SharedProtocolAdapter(
            make_runner(), self.store,
            episode_id=EPISODE, scope=SCOPE,
            authority=self.authority,
            observer_credential="observer",
            learner_credential="learner",
            evaluator_credential="evaluator",
        )
        commit = adapter.predict_and_commit("obs-before-restart", (0, 0, 2))
        adapter.reveal(commit["prediction_id"], "no")
        adapter.revise(commit["prediction_id"])

        self.store.close()
        self.store = SQLiteEvidenceStore(self.database)
        resumed_authority = make_authority(self.store)

        def restore_incremental(snapshot):
            restored = IncrementalConjunctionLearner(
                DOMAINS, min_support=snapshot["min_support"]
            )
            for record in snapshot["observations"]:
                for label in record["labels"]:
                    restored.observe(tuple(record["inputs"]), label)
            return restored

        resumed = E09SharedProtocolAdapter.resume_srok(
            self.store,
            episode_id=EPISODE,
            scope=SCOPE,
            split="SUPPORT",
            learner_track=TRACK,
            version_prefix="e09",
            learner_factory=restore_incremental,
            authority=resumed_authority,
            observer_credential="observer",
            learner_credential="learner",
            evaluator_credential="evaluator",
        )
        self.assertEqual(resumed._version_id, "e09-v2")
        resumed.predict_and_commit("obs-after-restart", (0, 0, 2))
        self.assertEqual(resumed.replay()[-1]["event_type"], "prediction_commit")
        self.assertEqual(resumed.replay()[-1]["actor_role"], "learner")

    def test_secure_resume_ignores_cross_track_observation_id_collision(self):
        authority = make_authority(
            self.store,
            additional_assignments={
                (EPISODE, SCOPE, "other-track"): "spiffe://test/other-learner",
            },
        )
        adapter = E09SharedProtocolAdapter(
            make_runner(), self.store,
            episode_id=EPISODE, scope=SCOPE,
            authority=authority,
            observer_credential="observer",
            learner_credential="learner",
            evaluator_credential="evaluator",
        )
        commit = adapter.predict_and_commit("obs-shared-id", (0, 0, 2))
        original = next(
            event["payload"] for event in adapter.replay()
            if event["event_type"] == "observation"
        )
        from prototype.shared_evidence_protocol import digest_payload
        foreign_inputs = {"inputs": [1, 1, 2]}
        foreign_ref = digest_payload(foreign_inputs)
        self.store.put_payload(foreign_ref, foreign_inputs)
        foreign_event_id = f"{EPISODE}:foreign-track-observation"
        authority.append_observation(
            "observer", episode_id=EPISODE,
            event_id=foreign_event_id, idempotency_key=foreign_event_id,
            payload={
                "observation_id": "obs-shared-id",
                "query_id": "foreign-query",
                "scope": SCOPE,
                "split": "SUPPORT",
                "learner_track": "other-track",
                "payload_ref": foreign_ref,
                "feature_schema_version": "e09-features-v1",
            },
        )

        self.store.close()
        self.store = SQLiteEvidenceStore(self.database)
        resumed_authority = make_authority(
            self.store,
            additional_assignments={
                (EPISODE, SCOPE, "other-track"): "spiffe://test/other-learner",
            },
        )
        def restore_incremental(snapshot):
            restored = IncrementalConjunctionLearner(
                DOMAINS, min_support=snapshot["min_support"]
            )
            for record in snapshot["observations"]:
                for label in record["labels"]:
                    restored.observe(tuple(record["inputs"]), label)
            return restored

        resumed = E09SharedProtocolAdapter.resume_srok(
            self.store, episode_id=EPISODE, scope=SCOPE, split="SUPPORT",
            learner_track=TRACK, version_prefix="e09",
            learner_factory=restore_incremental,
            authority=resumed_authority,
            observer_credential="observer", learner_credential="learner",
            evaluator_credential="evaluator",
        )
        self.assertEqual(
            resumed.runner._predictions[commit["prediction_id"]].inputs,
            tuple(self.store.get_payload(original["payload_ref"])["inputs"]),
        )
        self.assertEqual(
            resumed.runner._predictions[commit["prediction_id"]].inputs,
            (0, 0, 2),
        )

    def test_secure_mode_fails_closed_without_assigned_learner_or_correct_roles(self):
        with self.assertRaises(E09ProtocolAdapterError):
            E09SharedProtocolAdapter(
                make_runner(), self.store,
                episode_id=EPISODE, scope=SCOPE,
                authority=make_authority(self.store, assigned=False),
                observer_credential="observer",
                learner_credential="learner",
                evaluator_credential="evaluator",
            )
        with self.assertRaises(E09ProtocolAdapterError):
            E09SharedProtocolAdapter(
                make_runner(), self.store,
                episode_id=EPISODE, scope=SCOPE,
                authority=self.authority,
                observer_credential="observer",
                learner_credential="observer",
                evaluator_credential="evaluator",
            )


if __name__ == "__main__":
    unittest.main()
