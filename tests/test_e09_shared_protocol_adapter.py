import tempfile
import unittest
from pathlib import Path

from prototype.e09_counterexample_learner import CounterexampleRuleLearner, Example
from prototype.e09_incremental_learner import IncrementalConjunctionLearner
from prototype.e09_prequential import PrequentialRunner
from prototype.e09_shared_protocol_adapter import E09SharedProtocolAdapter
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

    def make_adapter(self, mode):
        if mode == "INCREMENTAL_INDEX":
            learner = IncrementalConjunctionLearner(DOMAINS, min_support=2)
        else:
            learner = CounterexampleRuleLearner(DOMAINS, min_support=2)
        runner = PrequentialRunner(learner, revision_mode=mode)
        runner.bootstrap(BOOTSTRAP)
        return E09SharedProtocolAdapter(
            runner, self.store, episode_id=f"episode-{mode}"
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


if __name__ == "__main__":
    unittest.main()
