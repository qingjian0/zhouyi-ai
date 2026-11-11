import tempfile
import unittest
from pathlib import Path

from prototype.shared_evidence_protocol import MissingReference, ProtocolError, SQLiteEvidenceStore
from prototype.shared_evidence_protocol_v03 import (
    BatchConflict, SQLiteEvidenceStoreV03,
)


class SharedEvidenceProtocolV03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "v03.sqlite3"
        self.store = SQLiteEvidenceStoreV03(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def ingest(self, *, evidence_id="train-1", role="train"):
        return {
            "event_id": f"ingest-event-{evidence_id}",
            "event_type": "evidence_ingest",
            "idempotency_key": f"ingest-key-{evidence_id}",
            "payload": {
                "evidence_id": evidence_id,
                "split_role": role,
                "outcome_ref": f"sha256:{evidence_id}",
                "source_provenance": {"source_kind": "dataset", "source_id": "fixture-1"},
                "learner_track": "e12",
            },
        }

    def test_train_ingest_supports_structure_without_fake_prediction_reveal(self):
        receipts = self.store.append_events(
            episode_id="ep", idempotency_key="batch-1",
            events=[
                self.ingest(),
                {
                    "event_id": "structure-1", "event_type": "structure_version",
                    "idempotency_key": "structure-key",
                    "payload": {
                        "structure_id": "primitive-set", "version_id": "v1",
                        "kind": "primitive", "definition": {"predicate": "x>y"},
                        "parent_version_ids": [],
                        "support_evidence_ids": [{"kind": "ingested", "id": "train-1"}],
                    },
                },
            ],
        )
        self.assertEqual([r.sequence_no for r in receipts], [1, 2])
        events = self.store.replay_episode("ep")
        self.assertEqual([e["event_type"] for e in events], ["evidence_ingest", "structure_version"])

    def test_ingest_rejects_locked_test_and_gate_final(self):
        for role in ("locked_test", "post_deploy", "gate_final", "gate_dev"):
            with self.subTest(role=role):
                with self.assertRaises(ProtocolError):
                    self.store.append_event(
                        episode_id=f"ep-{role}", event_id="ingest", event_type="evidence_ingest",
                        idempotency_key="ingest",
                        payload=self.ingest(role=role)["payload"],
                    )

    def test_forward_reference_rejected_and_whole_batch_rolled_back(self):
        with self.assertRaises(MissingReference):
            self.store.append_events(
                episode_id="ep", idempotency_key="bad-batch",
                events=[
                    {
                        "event_id": "structure-first", "event_type": "structure_version",
                        "payload": {
                            "structure_id": "s", "version_id": "v1", "kind": "rule",
                            "definition": {}, "parent_version_ids": [],
                            "support_evidence_ids": [{"kind": "ingested", "id": "late"}],
                        },
                    },
                    self.ingest(evidence_id="late"),
                ],
            )
        self.assertEqual(self.store.replay_episode("ep"), [])
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM idempotency WHERE episode_id='ep'").fetchone()[0],
            0,
        )

    def test_batch_retry_returns_same_receipts_and_conflicting_retry_fails(self):
        events = [self.ingest(), {
            "event_id": "obs", "event_type": "observation",
            "payload": {"observation_id": "obs-1"},
        }]
        first = self.store.append_events(episode_id="ep", events=events, idempotency_key="batch")
        retry = self.store.append_events(episode_id="ep", events=events, idempotency_key="batch")
        self.assertEqual([r.sequence_no for r in first], [1, 2])
        self.assertTrue(all(r.replayed for r in retry))
        changed = list(reversed(events))
        with self.assertRaises(BatchConflict):
            self.store.append_events(episode_id="ep", events=changed, idempotency_key="batch")
        self.assertEqual(len(self.store.replay_episode("ep")), 2)

    def test_lifecycle_action_uses_e12_transition_contract(self):
        self.store.append_event(
            episode_id="ep", event_id="candidate-v1", event_type="structure_version",
            idempotency_key="candidate-v1",
            payload={
                "structure_id": "candidate", "version_id": "candidate@1",
                "kind": "candidate", "definition": {"expression": "x>y"},
                "parent_version_ids": [], "support_evidence_ids": [],
            },
        )
        action = {
            "action_id": "propose-1", "action_type": "propose",
            "candidate_id": "candidate", "candidate_version": 1,
            "from_state": "observed", "to_state": "proposed",
            "evidence_refs": [], "cost": 0.1, "note": "proposal",
            "candidate_lineage_refs": [], "learner_track": "e12",
        }
        receipt = self.store.append_event(
            episode_id="ep", event_id="action-1", event_type="lifecycle_action",
            idempotency_key="action-1", payload=action,
        )
        self.assertEqual(receipt.sequence_no, 2)
        illegal = dict(action, action_id="illegal", action_type="gate_validate",
                       from_state="proposed", to_state="gate_validated")
        with self.assertRaises(ProtocolError):
            self.store.append_event(
                episode_id="ep", event_id="action-illegal", event_type="lifecycle_action",
                idempotency_key="action-illegal", payload=illegal,
            )

    def test_restart_replay_keeps_v03_events(self):
        self.store.append_events(
            episode_id="ep", idempotency_key="batch",
            events=[self.ingest(), {
                "event_id": "obs", "event_type": "observation",
                "payload": {"observation_id": "obs"},
            }],
        )
        before = [(x["event_id"], x["payload_digest"]) for x in self.store.replay_episode("ep")]
        self.store.close()
        self.store = SQLiteEvidenceStoreV03(self.db)
        after = [(x["event_id"], x["payload_digest"]) for x in self.store.replay_episode("ep")]
        self.assertEqual(before, after)


    def test_non_transition_e12_action_can_be_recorded_without_candidate_state(self):
        receipt = self.store.append_event(
            episode_id="ep", event_id="measure-1", event_type="lifecycle_action",
            idempotency_key="measure-1",
            payload={
                "action_id": "measure-1", "action_type": "measure",
                "candidate_id": None, "candidate_version": None,
                "from_state": None, "to_state": None,
                "evidence_refs": [], "cost": 0.5, "note": "active measurement",
                "candidate_lineage_refs": [], "learner_track": "e12",
            },
        )
        self.assertEqual(receipt.sequence_no, 1)



    def test_single_event_retry_preserves_v02_idempotency_behavior(self):
        first = self.store.append_event(
            episode_id="ep", event_id="first-event", event_type="observation",
            idempotency_key="same-key", payload={"observation_id": "obs-1"},
        )
        retry = self.store.append_event(
            episode_id="ep", event_id="different-event-id", event_type="observation",
            idempotency_key="same-key", payload={"observation_id": "obs-1"},
        )
        self.assertTrue(retry.replayed)
        self.assertEqual((retry.event_id, retry.sequence_no), (first.event_id, first.sequence_no))



if __name__ == "__main__":
    unittest.main()
