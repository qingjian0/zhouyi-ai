import sqlite3
import tempfile
import unittest
from pathlib import Path

from prototype.shared_evidence_protocol import (
    IdempotencyConflict, MissingReference, SequenceConflict, SQLiteEvidenceStore, digest_payload,
)


class SharedEvidenceProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "events.sqlite3"
        self.store = SQLiteEvidenceStore(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def commit(self, obs="o1", event="pc1", key="k1", learner_track="e09"):
        self.store.append_event(
            episode_id="ep1", event_id=f"obs-{obs}", event_type="observation",
            idempotency_key=f"obs-key-{obs}", payload={"observation_id": obs, "payload_ref": f"{obs}-payload"},
        )
        return self.store.commit_prediction(
            episode_id="ep1", event_id=event, idempotency_key=key,
            payload={"prediction_id": "p1", "observation_id": obs,
                     "model_version": "m0", "learner_track": learner_track, "decision_status": "PREDICT", "prediction": "A"},
        )

    def reveal(self, event="r1", key="rk1", prediction="p1"):
        return self.store.reveal_evidence(
            episode_id="ep1", event_id=event, idempotency_key=key,
            payload={"prediction_id": prediction, "learner_track": "e09", "target_or_feedback": "A"},
        )


    def test_journal_mode_avoids_known_pre_3513_wal_bug(self):
        if sqlite3.sqlite_version_info < (3, 51, 3):
            self.assertEqual(self.store.journal_mode, "DELETE")
        else:
            self.assertEqual(self.store.journal_mode, "WAL")

    def test_prediction_requires_prior_observation_and_commit_precedes_reveal(self):
        with self.assertRaises(MissingReference):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc-before-observation", idempotency_key="k-before-observation",
                payload={"prediction_id": "p-before", "observation_id": "o1", "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT"},
            )
        self.store.append_event(
            episode_id="ep1", event_id="obs-o1", event_type="observation",
            idempotency_key="obs-key-o1", payload={"observation_id": "o1"},
        )
        with self.assertRaises(MissingReference):
            self.reveal()
        self.store.commit_prediction(
            episode_id="ep1", event_id="pc1", idempotency_key="k1",
            payload={"prediction_id": "p1", "observation_id": "o1", "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT"},
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
                         "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT"},
            )

    def test_idempotency_fingerprint_includes_event_type(self):
        self.commit()
        with self.assertRaises(IdempotencyConflict):
            self.store.append_event(
                episode_id="ep1", event_id="other", event_type="observation",
                payload={"prediction_id": "p1", "observation_id": "o1",
                         "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT", "prediction": "A"},
                idempotency_key="k1",
            )

    def test_idempotency_fingerprint_includes_actor_role(self):
        self.commit()
        with self.assertRaises(IdempotencyConflict):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc-other", idempotency_key="k1",
                actor_role="evaluator",
                payload={"prediction_id": "p1", "observation_id": "o1",
                         "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT", "prediction": "A"},
            )


    def test_reveal_cannot_cross_learner_tracks(self):
        self.commit(learner_track="e09")
        with self.assertRaises(MissingReference):
            self.store.reveal_evidence(
                episode_id="ep1", event_id="cross-track-reveal", idempotency_key="cross-track-reveal",
                payload={"prediction_id": "p1", "learner_track": "e10", "target_or_feedback": "A"},
            )

    def test_prediction_rejects_empty_learner_track(self):
        self.store.append_event(
            episode_id="ep1", event_id="obs-o1", event_type="observation",
            idempotency_key="obs-key-o1", payload={"observation_id": "o1"},
        )
        with self.assertRaises(ValueError):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc-empty-track", idempotency_key="pc-empty-track",
                payload={"prediction_id": "p-empty", "observation_id": "o1", "model_version": "m0",
                         "learner_track": "  ", "decision_status": "PREDICT"},
            )

    def test_one_prediction_per_observation_per_track(self):
        self.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc2", idempotency_key="k2",
                payload={"prediction_id": "p2", "observation_id": "o1",
                         "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT"},
            )


    def test_independent_tracks_can_commit_for_same_observation(self):
        self.commit()
        receipt = self.store.commit_prediction(
            episode_id="ep1", event_id="pc-e10", idempotency_key="k-e10",
            payload={"prediction_id": "p-e10", "observation_id": "o1",
                     "model_version": "m0", "learner_track": "e10",
                     "decision_status": "PREDICT", "prediction": "B"},
        )
        self.assertEqual(receipt.sequence_no, 3)

    def test_prediction_id_is_unique_within_episode(self):
        self.commit()
        self.store.append_event(
            episode_id="ep1", event_id="obs-o2", event_type="observation",
            idempotency_key="obs-key-o2", payload={"observation_id": "o2"},
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.commit_prediction(
                episode_id="ep1", event_id="pc2", idempotency_key="k2",
                payload={"prediction_id": "p1", "observation_id": "o2", "model_version": "m0", "learner_track": "e09", "decision_status": "PREDICT"},
            )



    def test_v01_prediction_is_upcast_to_legacy_track_after_reopen(self):
        import json

        self.commit(learner_track="e09")
        row = self.store._db.execute(
            "SELECT sequence_no, payload_json FROM events WHERE episode_id='ep1' AND event_type='prediction_commit'"
        ).fetchone()
        old_payload = json.loads(row["payload_json"])
        old_payload.pop("learner_track")
        self.store._db.execute(
            "UPDATE events SET protocol_version='0.1', payload_json=?, payload_digest=? WHERE episode_id='ep1' AND sequence_no=?",
            (json.dumps(old_payload, sort_keys=True, separators=(",", ":")), digest_payload({
                "event_type": "prediction_commit", "payload_schema": "prediction_commit@1",
                "payload": old_payload, "actor_role": "runner", "causation_refs": [],
                "integrity_metadata": {},
            }), row["sequence_no"]),
        )
        self.store._db.executescript("""
            DROP INDEX IF EXISTS one_prediction_per_observation_track_v2;
            CREATE UNIQUE INDEX one_prediction_per_observation_track
              ON events(episode_id, json_extract(payload_json, '$.observation_id'),
                        json_extract(payload_json, '$.learner_track'))
              WHERE event_type='prediction_commit';
        """)
        self.store.close()
        self.store = SQLiteEvidenceStore(self.db)

        migrated_index = self.store._db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='one_prediction_per_observation_track_v2'"
        ).fetchone()
        self.assertIn("COALESCE", migrated_index["sql"].upper())

        replayed = self.store.replay_episode("ep1")
        prediction = next(item for item in replayed if item["event_type"] == "prediction_commit")
        self.assertEqual(prediction["payload"]["learner_track"], "legacy")
        self.assertEqual(prediction["payload_digest"], digest_payload({
            "event_type": "prediction_commit", "payload_schema": "prediction_commit@1",
            "payload": {k: v for k, v in prediction["payload"].items() if k != "learner_track"},
            "actor_role": "runner", "causation_refs": [], "integrity_metadata": {},
        }))

        receipt = self.store.reveal_evidence(
            episode_id="ep1", event_id="legacy-reveal", idempotency_key="legacy-reveal",
            payload={"prediction_id": "p1", "learner_track": "legacy", "target_or_feedback": "A"},
        )
        self.assertEqual(receipt.sequence_no, 3)

    def test_independent_connections_serialize_concurrent_writers(self):
        import concurrent.futures

        stores = [SQLiteEvidenceStore(self.db) for _ in range(6)]
        try:
            def write_one(index):
                return stores[index].append_event(
                    episode_id="concurrent-episode", event_id=f"obs-{index}",
                    event_type="observation", idempotency_key=f"obs-key-{index}",
                    payload={"observation_id": f"o-{index}"},
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                receipts = list(pool.map(write_one, range(6)))
            self.assertEqual(sorted(r.sequence_no for r in receipts), [1, 2, 3, 4, 5, 6])
            self.assertEqual(len(self.store.replay_episode("concurrent-episode")), 6)
        finally:
            for store in stores:
                store.close()


    def test_duplicate_event_id_is_rejected_without_sequence_gap(self):
        self.store.append_event(
            episode_id="ep1", event_id="stable-event", event_type="observation",
            idempotency_key="first-key", payload={"observation_id": "o1"},
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.append_event(
                episode_id="ep1", event_id="stable-event", event_type="observation",
                idempotency_key="second-key", payload={"observation_id": "o2"},
            )
        receipt = self.store.append_event(
            episode_id="ep1", event_id="next-event", event_type="observation",
            idempotency_key="next-key", payload={"observation_id": "o2"},
        )
        self.assertEqual(receipt.sequence_no, 2)

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
