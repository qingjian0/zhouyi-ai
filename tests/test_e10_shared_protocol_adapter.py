import tempfile
import unittest
from pathlib import Path

from prototype.e10a_prequential_ledger import PrequentialLedger
from prototype.e10_shared_protocol_adapter import E10SharedProtocolAdapter
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


class E10SharedProtocolAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteEvidenceStore(Path(self.tmp.name) / "e10.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def make_adapter(self, episode="e10-episode"):
        ledger = PrequentialLedger(episode_id=episode)
        adapter = E10SharedProtocolAdapter(
            ledger, self.store, episode_id=episode,
            initial_version_id="e10-v0",
            initial_structure={"relation_schema": "ternary", "operators": ["compose", "invert"]},
        )
        return ledger, adapter

    def test_prediction_reveal_revision_are_mirrored_in_causal_order(self):
        ledger, adapter = self.make_adapter()
        committed = adapter.commit_prediction(
            prediction_id="p1", observation_id="q1",
            observation_payload={"objects": ["a", "b", "c"], "phase": "query"},
            model_version="e10-model-v0", candidate_set_hash="candidate-set-1",
            decision_status="PREDICT", prediction={"relation": "r1"},
            confidence=0.7, compute_cost={"candidate_expansions": 12},
        )
        reveal_event_id = adapter.reveal_evidence(
            reveal_id="r1", prediction_id="p1", target={"relation": "r2"},
            reveal_source="locked-evaluator",
        )
        result = adapter.append_revision(
            revision_id="rev1", operation="modify", evidence_ids=["r1"],
            before_version_ids=["e10-v0"], after_version_id="e10-v1",
            after_structure={"relation_schema": "ternary", "operators": ["compose", "invert", "swap"]},
            rationale_code="counterexample-induced-operator-update",
            actual_compute={"candidate_expansions": 5},
        )
        events = adapter.replay()
        self.assertEqual(
            [event["event_type"] for event in events],
            ["structure_version", "observation", "prediction_commit",
             "evidence_reveal", "structure_version", "revision"],
        )
        self.assertEqual(events[2]["event_id"], committed["event_id"])
        self.assertEqual(events[3]["event_id"], reveal_event_id)
        self.assertEqual(events[4]["payload"]["parent_version_ids"], ["e10-v0"])
        self.assertEqual(events[4]["payload"]["support_evidence_ids"], [reveal_event_id])
        self.assertEqual(events[5]["payload"]["after_version_ids"], ["e10-v1"])
        self.assertEqual(ledger.snapshot()["event_count"], 3)
        self.assertEqual(result["after_version_id"], "e10-v1")

    def test_abstention_is_persisted_as_a_first_class_decision(self):
        _, adapter = self.make_adapter()
        adapter.commit_prediction(
            prediction_id="p-abstain", observation_id="q-abstain",
            observation_payload={"query": "underspecified"},
            model_version="e10-model-v0", candidate_set_hash="candidates",
            decision_status="ABSTAIN_AMBIGUOUS", prediction=None,
        )
        prediction = adapter.replay()[-1]
        self.assertEqual(prediction["payload"]["decision_status"], "ABSTAIN_AMBIGUOUS")
        self.assertIsNone(prediction["payload"]["prediction"])

    def test_reveal_requires_adapter_committed_prediction(self):
        _, adapter = self.make_adapter()
        with self.assertRaisesRegex(ValueError, "committed by this adapter"):
            adapter.reveal_evidence(
                reveal_id="r1", prediction_id="unknown", target=False
            )

    def test_learner_track_is_explicit_on_prediction_and_reveal(self):
        _, adapter = self.make_adapter()
        adapter.commit_prediction(
            prediction_id="track-p", observation_id="track-q",
            observation_payload={"q": [1, 2]}, model_version="e10-model-v0",
            candidate_set_hash="track-candidates", decision_status="PREDICT",
            prediction="A",
        )
        adapter.reveal_evidence(
            reveal_id="track-r", prediction_id="track-p", target="B"
        )
        events = adapter.replay()
        self.assertEqual(events[-2]["payload"]["learner_track"], "e10")
        self.assertEqual(events[-1]["payload"]["learner_track"], "e10")

    def test_partial_cross_store_failure_fails_closed(self):
        _, adapter = self.make_adapter("partial-failure")
        with self.assertRaises(Exception):
            adapter.commit_prediction(
                prediction_id="bad-p", observation_id="bad-q",
                observation_payload={"q": "visible"}, model_version="e10-v0",
                candidate_set_hash="candidate-hash", decision_status="PREDICT",
                prediction="bad", confidence=1.5,
            )
        events = self.store.replay_episode("partial-failure")
        self.assertEqual(
            [event["event_type"] for event in events],
            ["structure_version", "observation"],
        )
        with self.assertRaisesRegex(Exception, "fail-closed"):
            adapter.replay()


if __name__ == "__main__":
    unittest.main()
