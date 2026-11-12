import tempfile
import unittest
from pathlib import Path

from prototype.e09_counterexample_learner import CounterexampleRuleLearner, Example
from prototype.e09_incremental_learner import IncrementalConjunctionLearner
from prototype.e09_prequential import PrequentialError, PrequentialRunner
from prototype.e09_shared_protocol_adapter import E09SharedProtocolAdapter
from prototype.e09_evaluator_projection import E09EvaluatorProjection
from prototype.shared_evidence_protocol import SQLiteEvidenceStore
from prototype.zpcm_memory import ZPCMMemory
from prototype.e09_shared_protocol_adapter import E09ProtocolAdapterError


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

    def make_adapter(self, mode, split="SUPPORT", memory_projection=None):
        if mode == "INCREMENTAL_INDEX":
            learner = IncrementalConjunctionLearner(DOMAINS, min_support=2)
        else:
            learner = CounterexampleRuleLearner(DOMAINS, min_support=2)
        runner = PrequentialRunner(learner, revision_mode=mode)
        runner.bootstrap(BOOTSTRAP)
        return E09SharedProtocolAdapter(
            runner, self.store, episode_id=f"episode-{mode}", scope="e09/test", split=split,
            memory_projection=memory_projection,
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

    def test_projection_commit_then_crash_replays_without_duplicate_items(self):
        projection_path = Path(self.tmp.name) / "zpcm.sqlite3"
        memory = ZPCMMemory(projection_path)
        adapter = self.make_adapter(
            "INCREMENTAL_INDEX", memory_projection=memory
        )
        commit = adapter.predict_and_commit("obs-projection-crash", (0, 0, 2))
        original_sync = memory.sync_episode

        def commit_then_crash(*args, **kwargs):
            original_sync(*args, **kwargs)
            raise RuntimeError("simulated crash after ZPCM commit")

        memory.sync_episode = commit_then_crash
        with self.assertRaises(E09ProtocolAdapterError):
            adapter.reveal(commit["prediction_id"], "no")
        memory.sync_episode = original_sync

        # The adapter intentionally fails closed after projection uncertainty.
        # Read the authoritative E09 event log directly for reconciliation.
        reveal = next(
            event for event in self.store.replay_episode(adapter.episode_id)
            if event["event_type"] == "evidence_reveal"
        )
        item_id = "protocol:" + reveal["event_id"]
        count = memory.db.execute(
            "SELECT COUNT(*) FROM memory_items WHERE item_id=?", (item_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

        # Replaying the authoritative E09 log must be safe after the caller
        # observes an exception even though the ZPCM transaction committed.
        memory.sync_episode(
            self.store, episode_id=adapter.episode_id,
            scope="e09/test", learner_track="e09",
        )
        count = memory.db.execute(
            "SELECT COUNT(*) FROM memory_items WHERE item_id=?", (item_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

        memory.close()
        memory = ZPCMMemory(projection_path)
        memory.sync_episode(
            self.store, episode_id=adapter.episode_id,
            scope="e09/test", learner_track="e09",
        )
        count = memory.db.execute(
            "SELECT COUNT(*) FROM memory_items WHERE item_id=?", (item_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)
        memory.close()

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
