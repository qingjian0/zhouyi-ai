import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.shared_evidence_protocol import (
    IdempotencyConflict, MissingReference, SequenceConflict, SQLiteEvidenceStore,
)


class SharedEvidenceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "events.sqlite3"
        self.store = SQLiteEvidenceStore(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def commit(self, obs="o1", event="pc1", key="k1"):
        self.store.append_event(
            episode_id="ep1", event_id=f"obs-{obs}", event_type="observation",
            idempotency_key=f"obs-key-{obs}", payload={"observation_id": obs, "payload_ref": f"{obs}-payload"},
        )
        return self.store.commit_prediction(
            episode_id="ep1", event_id=event, idempotency_key=key,
            payload={"prediction_id": "p1", "observation_id": obs,
                     "model_version": "m0", "decision_status": "PREDICT", "prediction": "A"},
        )

    def reveal(self, event="r1", key="rk1", prediction="p1"):
        return self.store.reveal_evidence(
            episode_id="ep1", event_id=event, idempotency_key=key,
            payload={"prediction_id": prediction, "target_or_feedback": "A"},
        )

    def test_prediction_requires_prior_observation_and_commit_precedes_reveal(self):
        with self.assertRaises(MissingReference):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc-before-observation", idempotency_key="k-before-observation",
                payload={"prediction_id": "p-before", "observation_id": "o1", "model_version": "m0", "decision_status": "PREDICT"},
            )
        self.store.append_event(
            episode_id="ep1", event_id="obs-o1", event_type="observation",
            idempotency_key="obs-key-o1", payload={"observation_id": "o1"},
        )
        with self.assertRaises(MissingReference):
            self.reveal()
        self.store.commit_prediction(
            episode_id="ep1", event_id="pc1", idempotency_key="k1",
            payload={"prediction_id": "p1", "observation_id": "o1", "model_version": "m0", "decision_status": "PREDICT"},
        )
        self.assertEqual(self.reveal().sequence_no, 3)

    def test_identical_retry_returns_original_receipt(self):
        first = self.commit()
        retry = self.commit(event="different-event-id")
        self.assertEqual((first.sequence_no, first.event_id), (retry.sequence_no, retry.event_id))
        self.assertTrue(retry.replayed)

    def test_conflicting_retry_rejected(self):
        self.commit()
        with self.assertRaises(IdempotencyConflict):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc2", idempotency_key="k1",
                payload={"prediction_id": "p2", "observation_id": "o2",
                         "model_version": "m0", "decision_status": "PREDICT"},
            )

    def test_idempotency_fingerprint_includes_event_type(self):
        self.commit()
        with self.assertRaises(IdempotencyConflict):
            self.store.append_event(
                episode_id="ep1", event_id="other", event_type="observation",
                payload={"prediction_id": "p1", "observation_id": "o1",
                         "model_version": "m0", "decision_status": "PREDICT", "prediction": "A"},
                idempotency_key="k1",
            )

    def test_idempotency_fingerprint_includes_actor_role(self):
        self.commit()
        with self.assertRaises(IdempotencyConflict):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc-other", idempotency_key="k1",
                actor_role="evaluator",
                payload={"prediction_id": "p1", "observation_id": "o1",
                         "model_version": "m0", "decision_status": "PREDICT", "prediction": "A"},
            )

    def test_one_prediction_per_observation(self):
        self.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc2", idempotency_key="k2",
                payload={"prediction_id": "p2", "observation_id": "o1",
                         "model_version": "m0", "decision_status": "PREDICT"},
            )

    def test_prediction_id_is_unique_within_episode(self):
        self.commit()
        self.store.append_event(
            episode_id="ep1", event_id="obs-o2", event_type="observation",
            idempotency_key="obs-key-o2", payload={"observation_id": "o2"},
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc2", idempotency_key="k2",
                payload={"prediction_id": "p1", "observation_id": "o2", "model_version": "m0", "decision_status": "PREDICT"},
            )

    def test_stale_sequence_rejected(self):
        self.commit()
        with self.assertRaises(SequenceConflict):
            self.store.append_event(
                episode_id="ep1", event_id="o2", event_type="observation",
                payload={"observation_id": "o2"}, idempotency_key="o2", expected_sequence=0,
            )

    def test_one_reveal_per_prediction(self):
        self.commit()
        self.reveal()
        with self.assertRaises(sqlite3.IntegrityError):
            self.reveal(event="r2", key="rk2")

    def test_revision_requires_revealed_evidence_and_known_versions(self):
        self.commit()
        with self.assertRaises(MissingReference):
            self.store.append_revision(
                episode_id="ep1", event_id="rev0", idempotency_key="revk0",
                payload={"revision_id": "rev0", "operation": "keep", "trigger_evidence_ids": ["r1"],
                         "before_version_ids": [], "after_version_ids": []},
            )
        self.reveal()
        self.store.append_event(
            episode_id="ep1", event_id="s1", event_type="structure_version", idempotency_key="s1",
            payload={"structure_id": "s", "version_id": "v1", "kind": "rule", "definition": {"if": "x"},
                     "parent_version_ids": [], "support_evidence_ids": ["r1"]},
        )
        receipt = self.store.append_revision(
            episode_id="ep1", event_id="rev1", idempotency_key="revk1",
            payload={"revision_id": "rev1", "operation": "keep", "trigger_evidence_ids": ["r1"],
                     "before_version_ids": ["v1"], "after_version_ids": ["v1"]},
        )
        self.assertEqual(receipt.sequence_no, 5)

    def test_structure_parent_must_exist(self):
        with self.assertRaises(MissingReference):
            self.store.append_event(
                episode_id="ep1", event_id="s1", event_type="structure_version", idempotency_key="s1",
                payload={"structure_id": "s", "version_id": "v1", "kind": "rule", "definition": {},
                         "parent_version_ids": ["missing"], "support_evidence_ids": []},
            )

    def test_restart_replay_is_deterministic(self):
        self.commit()
        self.reveal()
        before = self.store.replay_episode("ep1")
        self.store.close()
        self.store = SQLiteEvidenceStore(self.db)
        after = self.store.replay_episode("ep1")
        project = lambda rows: [(x["sequence_no"], x["event_id"], x["payload_digest"]) for x in rows]
        self.assertEqual(project(before), project(after))

    def test_structure_snapshot_is_detached(self):
        self.commit()
        self.reveal()
        self.store.append_event(
            episode_id="ep1", event_id="s1", event_type="structure_version", idempotency_key="s1",
            payload={"structure_id": "s", "version_id": "v1", "kind": "rule", "definition": {"x": 1},
                     "parent_version_ids": [], "support_evidence_ids": ["r1"]},
        )
        snapshot = self.store.snapshot_structure("ep1", "v1")
        snapshot["payload"]["definition"]["x"] = 999
        self.assertEqual(self.store.snapshot_structure("ep1", "v1")["payload"]["definition"]["x"], 1)


if __name__ == "__main__":
    unittest.main()
