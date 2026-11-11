import tempfile
import unittest
from pathlib import Path

from prototype.e12a6_lifecycle_contract import SplitRole
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.e09_e12a6_evidence_bridge import E09EvidenceBindingError, register_e09_reveal, resolve_e09_reveal
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore
from prototype.zpcm_memory import ZPCMMemory


class E09EvidenceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.e09 = SQLiteEvidenceStore(Path(self.tmp.name) / "e09.db")
        self.zpcm = ZPCMMemory(Path(self.tmp.name) / "zpcm.db")
        self.episode = "episode-1"
        self.scope = "scope-1"
        self.track = "srok-v1"
        self.world = "finite-rule-world"

    def tearDown(self):
        self.e09.close()
        self.zpcm.close()
        self.tmp.cleanup()

    def add_reveal(self, *, split="SUPPORT", label="PRIVATE_LABEL", track=None, scope=None):
        track = track or self.track
        scope = scope or self.scope
        obs_id = "obs-" + split.lower()
        self.e09.append_event(
            episode_id=self.episode, event_id=f"{self.episode}:observation:{obs_id}",
            event_type="observation", idempotency_key=f"obs-key-{split}",
            actor_role="runner",
            payload={"observation_id":obs_id,"query_id":obs_id,"scope":scope,"split":split},
            protocol_version=STRICT_PROTOCOL_VERSION,
        )
        prediction_id = "pred-" + split.lower()
        commit_digest = ("a" if split == "SUPPORT" else "b") * 64
        commit_event = f"{self.episode}:prediction:{prediction_id}"
        commit = self.e09.append_event(
            episode_id=self.episode, event_id=commit_event, event_type="prediction_commit",
            idempotency_key=f"commit-key-{split}", actor_role="learner",
            causation_refs=[f"{self.episode}:observation:{obs_id}"],
            payload={"prediction_id":prediction_id,"observation_id":obs_id,"query_id":obs_id,
              "scope":scope,"split":split,"model_version":"model-7","learner_track":track,
              "decision_status":"PREDICT","interop_commit_digest":commit_digest},
            protocol_version=STRICT_PROTOCOL_VERSION,
        )
        reveal_event = f"{self.episode}:reveal:{prediction_id}"
        self.e09.append_event(
            episode_id=self.episode, event_id=reveal_event, event_type="evidence_reveal",
            idempotency_key=f"reveal-key-{split}", actor_role="evaluator",
            causation_refs=[commit_event],
            payload={"prediction_id":prediction_id,"query_id":obs_id,"scope":scope,"split":split,
              "commit_digest":commit_digest,"event_digest":commit.payload_digest,
              "learner_track":track,"target_or_feedback":label,"reveal_source":"test"},
            protocol_version=STRICT_PROTOCOL_VERSION,
        )
        return reveal_event

    def test_support_reveal_maps_to_train_and_redacts_target(self):
        ref = self.add_reveal(label="TOP_SECRET_TARGET")
        evidence = resolve_e09_reveal(self.e09, episode_id=self.episode,evidence_ref=ref,
          scope=self.scope,learner_track=self.track,world_family=self.world)
        self.assertEqual(evidence.split_role,SplitRole.TRAIN)
        self.assertEqual(evidence.model_version,"model-7")
        self.assertEqual(evidence.prediction_commit_step,2)
        self.assertEqual(evidence.label_visibility_step,3)
        self.assertNotIn("TOP_SECRET_TARGET",str(evidence))
        ledger=PersistentLifecycleLedger(self.zpcm,scope="project-1")
        _,receipt=register_e09_reveal(ledger,self.e09,episode_id=self.episode,evidence_ref=ref,
          scope=self.scope,learner_track=self.track,world_family=self.world)
        self.assertFalse(receipt.replayed)
        self.assertNotIn("TOP_SECRET_TARGET",str(self.zpcm.replay_lifecycle_events(scope="project-1")))

    def test_locked_test_role_is_never_mapped_to_train(self):
        ref=self.add_reveal(split="LOCKED_TEST",label="LOCKED_LABEL")
        evidence=resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
          scope=self.scope,learner_track=self.track,world_family=self.world)
        self.assertEqual(evidence.split_role,SplitRole.LOCKED_TEST)
        self.assertNotEqual(evidence.split_role,SplitRole.TRAIN)
        self.assertNotIn("LOCKED_LABEL",str(evidence))

    def test_scope_and_track_mismatch_are_rejected(self):
        ref=self.add_reveal()
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
              scope="other-scope",learner_track=self.track,world_family=self.world)
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
              scope=self.scope,learner_track="other-track",world_family=self.world)

    def test_non_reveal_reference_is_rejected(self):
        self.add_reveal()
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,
              evidence_ref=f"{self.episode}:observation:obs-support",
              scope=self.scope,learner_track=self.track,world_family=self.world)

    def test_world_family_must_be_explicit(self):
        ref=self.add_reveal()
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
              scope=self.scope,learner_track=self.track,world_family="")

    def test_commit_event_digest_tampering_is_rejected(self):
        ref=self.add_reveal()
        # Alter the reveal's binding to a different durable commit digest.
        self.e09._db.execute(
            "UPDATE events SET payload_json=json_set(payload_json,'$.event_digest',?) WHERE event_id=?",
            ("f"*64,ref),
        )
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
              scope=self.scope,learner_track=self.track,world_family=self.world)


if __name__ == "__main__":
    unittest.main()
