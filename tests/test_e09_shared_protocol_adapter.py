import hashlib
import tempfile
import unittest
from pathlib import Path

from prototype.e09_counterexample_learner import CounterexampleRuleLearner, Example
from prototype.e09_incremental_learner import IncrementalConjunctionLearner
from prototype.e09_prequential import PrequentialError, PrequentialRunner
from prototype.e09_shared_protocol_adapter import E09SharedProtocolAdapter, E09ProtocolAdapterError
from prototype.e09_authority_services import (
    E09AuthenticatedWorkload, E09AuthorityService, E09DomainBinding,
)
from prototype.e09_evaluator_projection import E09EvaluatorProjection
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


DOMAINS = ((0, 1), (0, 1), (0, 1, 2))
BOOTSTRAP = [
    ("seed-1", Example((0, 0, 0), "yes")),
    ("seed-2", Example((0, 1, 0), "yes")),
    ("seed-3", Example((1, 0, 0), "no")),
    ("seed-4", Example((1, 1, 0), "no")),
]


class E09SharedProtocolAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "e09.sqlite3"
        self.store = SQLiteEvidenceStore(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def make_adapter(self, mode, split="SUPPORT"):
        if mode == "INCREMENTAL_INDEX":
            learner = IncrementalConjunctionLearner(DOMAINS, min_support=2)
        else:
            learner = CounterexampleRuleLearner(DOMAINS, min_support=2)
        runner = PrequentialRunner(learner, revision_mode=mode)
        runner.bootstrap(BOOTSTRAP)
        return E09SharedProtocolAdapter(
            runner, self.store, episode_id=f"episode-{mode}", scope="e09/test", split=split
        )

    def test_secure_mode_routes_every_event_write_through_authenticated_authority(self):
        class Authenticator:
            identities = {
                "observer": E09AuthenticatedWorkload(
                    "spiffe://test/observer", "issuer-observer", frozenset({"observer"}),
                    frozenset({"e09/test"}), "test-idp", "mTLS",
                    hashlib.sha256(b"observer").hexdigest(),
                ),
                "learner": E09AuthenticatedWorkload(
                    "spiffe://test/learner", "issuer-learner", frozenset({"learner"}),
                    frozenset({"e09/test"}), "test-idp", "mTLS",
                    hashlib.sha256(b"learner").hexdigest(),
                ),
                "evaluator": E09AuthenticatedWorkload(
                    "spiffe://test/evaluator", "issuer-evaluator", frozenset({"evaluator"}),
                    frozenset({"e09/test"}), "test-idp", "mTLS",
                    hashlib.sha256(b"evaluator").hexdigest(),
                ),
            }

            def authenticate(self, credential):
                if credential not in self.identities:
                    raise ValueError("unknown credential")
                return self.identities[credential]

        class Signer:
            def sign(self, issuer_id, message):
                return "unused-test-signature"

        class DomainRegistry:
            def resolve(self, *, episode_id, scope, observation_id):
                return E09DomainBinding("family-e09", "test-registry", "v1")

        authority = E09AuthorityService(
            self.store, authenticator=Authenticator(), signer=Signer(),
            domain_registry=DomainRegistry(),
        )
        learner = CounterexampleRuleLearner(DOMAINS, min_support=2)
        runner = PrequentialRunner(learner, revision_mode="INCREMENTAL_INDEX")
        runner.bootstrap(BOOTSTRAP)
        adapter = E09SharedProtocolAdapter(
            runner, self.store, episode_id="episode-secure", scope="e09/test",
            authority=authority, observer_credential="observer",
            learner_credential="learner", evaluator_credential="evaluator",
        )
        commit = adapter.predict_and_commit("obs-secure", (0, 0, 2))
        reveal_ref = adapter.reveal(commit["prediction_id"], "no")
        adapter.revise(commit["prediction_id"])

        events = adapter.replay()
        self.assertEqual(
            [event["event_type"] for event in events],
            ["structure_version", "observation", "prediction_commit",
             "evidence_reveal", "structure_version", "revision"],
        )
        observation = next(event for event in events if event["event_type"] == "observation")
        prediction = next(event for event in events if event["event_type"] == "prediction_commit")
        reveal = next(event for event in events if event["event_type"] == "evidence_reveal")
        self.assertEqual(observation["actor_role"], "observer")
        self.assertEqual(observation["payload"]["world_family"], "family-e09")
        self.assertEqual(observation["payload"]["domain_registry_id"], "test-registry")
        self.assertEqual(prediction["actor_role"], "learner")
        self.assertEqual(reveal["actor_role"], "evaluator")
        self.assertEqual(reveal["event_id"], reveal_ref)
        for event in events:
            self.assertIn("authenticated_workload", event["integrity_metadata"])

    def test_secure_mode_requires_all_credentials_and_trusted_domain_registry(self):
        learner = CounterexampleRuleLearner(DOMAINS, min_support=2)
        runner = PrequentialRunner(learner, revision_mode="INCREMENTAL_INDEX")
        runner.bootstrap(BOOTSTRAP)
        with self.assertRaises(E09ProtocolAdapterError):
            E09SharedProtocolAdapter(
                runner, self.store, episode_id="episode-incomplete-secure",
                scope="e09/test", authority=object(), observer_credential="observer",
            )

    def test_incremental_arm_persists_full_causal_chain(self):
        adapter = self.make_adapter("INCREMENTAL_INDEX")
        commit = adapter.predict_and_commit("obs-5", (0, 0, 2))
        self.assertEqual(commit["prediction"], "yes")
        events = adapter.replay()
        self.assertEqual(
            [e["event_type"] for e in events],
            ["structure_version", "observation", "prediction_commit"],
        )

        reveal_event_id = adapter.reveal(commit["prediction_id"], "no")
        self.assertEqual(adapter.score()["revealed_observations"], 1)
        revision = adapter.revise(commit["prediction_id"])
        self.assertEqual(revision["operation"], "INCREMENTAL_INDEX")
        self.assertEqual(revision["candidate_evaluations"], 8)

        events = adapter.replay()
        self.assertEqual(
            [e["event_type"] for e in events],
            ["structure_version", "observation", "prediction_commit",
             "evidence_reveal", "structure_version", "revision"],
        )
        reveal = next(e for e in events if e["event_type"] == "evidence_reveal")
        self.assertEqual(reveal["event_id"], reveal_event_id)
        prediction_event = next(e for e in events if e["event_type"] == "prediction_commit")
        self.assertEqual(
            reveal["payload"]["commit_digest"],
            prediction_event["payload"]["interop_commit_digest"],
        )
        self.assertEqual(
            reveal["payload"]["event_digest"],
            prediction_event["payload_digest"],
        )
        self.assertNotEqual(
            reveal["payload"]["commit_digest"],
            reveal["payload"]["event_digest"],
        )
        structure = [e for e in events if e["event_type"] == "structure_version"][-1]
        self.assertEqual(structure["payload"]["parent_version_ids"], ["e09-v1"])
        self.assertEqual(structure["payload"]["support_evidence_ids"], [reveal_event_id])
        revision_event = events[-1]
        self.assertEqual(revision_event["payload"]["before_version_ids"], ["e09-v1"])
        self.assertEqual(revision_event["payload"]["after_version_ids"], ["e09-v2"])

    def test_batch_refit_is_recorded_as_batch_refit_not_incremental(self):
        adapter = self.make_adapter("BATCH_REFIT")
        commit = adapter.predict_and_commit("obs-5", (0, 0, 2))
        adapter.reveal(commit["prediction_id"], "no")
        result = adapter.revise(commit["prediction_id"])
        self.assertEqual(result["operation"], "BATCH_REFIT")
        events = adapter.replay()
        self.assertEqual(events[-1]["payload"]["operation"], "BATCH_REFIT")
        self.assertGreater(events[-1]["payload"]["candidate_evaluations"], 0)

    def test_prediction_is_durable_before_reveal(self):
        adapter = self.make_adapter("INCREMENTAL_INDEX")
        commit = adapter.predict_and_commit("obs-5", (0, 0, 2))
        events = adapter.replay()
        self.assertEqual(events[-1]["event_type"], "prediction_commit")
        self.assertEqual(events[-1]["payload"]["learner_track"], "e09")
        self.assertEqual(adapter.score()["revealed_observations"], 0)
        self.assertEqual(commit["decision_status"], "PREDICT")
 
    def test_locked_gate_reveal_is_not_delivered_to_learner(self):
        adapter = self.make_adapter("INCREMENTAL_INDEX", split="LOCKED_TEST")
        commit = adapter.predict_and_commit("obs-locked", (0, 0, 2))
        adapter.reveal(commit["prediction_id"], "no")
        self.assertEqual(adapter.score()["revealed_observations"], 0)
        with self.assertRaises(PrequentialError):
            adapter.revise(commit["prediction_id"])
        reveal = next(
            e for e in adapter.replay() if e["event_type"] == "evidence_reveal"
        )
        self.assertEqual(reveal["protocol_version"], "0.3")
        self.assertEqual(reveal["payload"]["split"], "LOCKED_TEST")

    def test_locked_test_is_scored_by_evaluator_projection_only(self):
        adapter = self.make_adapter("INCREMENTAL_INDEX", split="LOCKED_TEST")
        commit = adapter.predict_and_commit("obs-locked-score", (0, 0, 2))
        adapter.reveal(commit["prediction_id"], "yes")

        # The learner's own prequential ledger remains blind to LOCKED_TEST.
        self.assertEqual(adapter.score()["revealed_observations"], 0)
        metrics = E09EvaluatorProjection(
            self.store, "episode-INCREMENTAL_INDEX"
        ).score()
        locked = metrics["by_split"]["LOCKED_TEST"]
        self.assertEqual(locked["prediction_commits"], 1)
        self.assertEqual(locked["revealed_observations"], 1)
        self.assertEqual(locked["scored_predictions"], 1)
        self.assertEqual(locked["correct_predictions"], 1)
        self.assertEqual(locked["selective_accuracy"], 1.0)
        self.assertEqual(metrics["overall"]["selective_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
