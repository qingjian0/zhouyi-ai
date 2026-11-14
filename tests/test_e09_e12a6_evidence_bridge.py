import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from prototype.e12a6_lifecycle_contract import SplitRole
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.e09_e12a6_evidence_bridge import (
    AUTHORIZATION_AUDIENCE, AUTHORIZATION_SIGNATURE_VERSION,
    E09EvidenceBindingError, register_e09_reveal, resolve_e09_reveal,
    branch_merge_authorization_signing_bytes, resolve_branch_merge_authorization,
)
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
          scope=self.scope,learner_track=self.track,world_family=self.world,allow_legacy_migration=True)
        self.assertEqual(evidence.split_role,SplitRole.TRAIN)
        self.assertEqual(evidence.model_version,"model-7")
        self.assertEqual(evidence.prediction_commit_step,2)
        self.assertEqual(evidence.label_visibility_step,3)
        self.assertNotIn("TOP_SECRET_TARGET",str(evidence))
        ledger=PersistentLifecycleLedger(self.zpcm,scope="project-1")
        with self.assertRaises(E09EvidenceBindingError):
            register_e09_reveal(ledger,self.e09,episode_id=self.episode,evidence_ref=ref,
              scope=self.scope,learner_track=self.track,world_family=self.world,
              allow_legacy_migration=True)
        self.assertEqual(self.zpcm.replay_lifecycle_events(scope="project-1"), [])

    def test_locked_test_role_is_never_mapped_to_train(self):
        ref=self.add_reveal(split="LOCKED_TEST",label="LOCKED_LABEL")
        evidence=resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
          scope=self.scope,learner_track=self.track,world_family=self.world,allow_legacy_migration=True)
        self.assertEqual(evidence.split_role,SplitRole.LOCKED_TEST)
        self.assertNotEqual(evidence.split_role,SplitRole.TRAIN)
        self.assertNotIn("LOCKED_LABEL",str(evidence))

    def test_scope_and_track_mismatch_are_rejected(self):
        ref=self.add_reveal()
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
              scope="other-scope",learner_track=self.track,world_family=self.world,allow_legacy_migration=True)
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,evidence_ref=ref,
              scope=self.scope,learner_track="other-track",world_family=self.world,allow_legacy_migration=True)

    def test_non_reveal_reference_is_rejected(self):
        self.add_reveal()
        with self.assertRaises(E09EvidenceBindingError):
            resolve_e09_reveal(self.e09,episode_id=self.episode,
              evidence_ref=f"{self.episode}:observation:obs-support",
              scope=self.scope,learner_track=self.track,world_family=self.world,allow_legacy_migration=True)

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
              scope=self.scope,learner_track=self.track,world_family=self.world,allow_legacy_migration=True)


    def add_branch_authorization(self, evidence_ref, *, signature="sig-ok", branches=None):
        branches = ["left", "right"] if branches is None else branches
        event_id = "authorization-1"
        sequence = self.e09.replay_episode(self.episode)[-1]["sequence_no"] + 1
        payload = {
            "authorization_id": event_id,
            "issuer_id": "issuer-1",
            "scope": self.scope,
            "parent_state_ref": "parent-1",
            "branch_ids": branches,
            "evidence_refs": [evidence_ref],
            "issued_at": "2026-11-11T00:00:00+00:00",
            "expires_at": "2026-11-12T00:00:00+00:00",
            "signature_algorithm": "Ed25519",
            "signature_version": AUTHORIZATION_SIGNATURE_VERSION,
            "audience": AUTHORIZATION_AUDIENCE,
            "authorization_sequence": sequence,
            "signature": signature,
        }
        signing_event = {
            "episode_id": self.episode,
            "event_id": event_id,
            "event_type": "branch_merge_authorization",
            "protocol_version": STRICT_PROTOCOL_VERSION,
            "payload_schema": "branch_merge_authorization@2",
            "actor_role": "authorizer",
            "causation_refs": [evidence_ref],
            "integrity_metadata": {},
            "payload": payload,
        }
        self.e09.append_event(
            episode_id=self.episode, event_id=event_id,
            event_type="branch_merge_authorization", idempotency_key=event_id,
            actor_role="authorizer", causation_refs=[evidence_ref],
            payload=payload, payload_schema="branch_merge_authorization@2",
            integrity_metadata={}, expected_sequence=sequence - 1,
            protocol_version=STRICT_PROTOCOL_VERSION,
        )
        return event_id

    def test_branch_merge_authorization_requires_trusted_signature_and_exact_scope(self):
        evidence_ref = self.add_reveal()
        authorization_ref = self.add_branch_authorization(evidence_ref)
        calls = []
        def verifier(issuer_id, algorithm, message, signature):
            calls.append((issuer_id, algorithm, message, signature))
            return issuer_id == "issuer-1" and algorithm == "Ed25519" and signature == "sig-ok"
        permit = resolve_branch_merge_authorization(
            self.e09, episode_id=self.episode, authorization_ref=authorization_ref,
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
            world_family_by_evidence={evidence_ref: self.world},
            allow_legacy_migration=True,
            signature_verifier=verifier, verifier_id="pinned-ed25519-keyring-v1",
            now=datetime(2026, 11, 11, 12, tzinfo=timezone.utc),
        )
        self.assertEqual(permit.issuer_id, "issuer-1")
        self.assertEqual(permit.branch_ids, ("left", "right"))
        self.assertEqual(permit.evidence_refs, (evidence_ref,))
        self.assertEqual(permit.verifier_id, "pinned-ed25519-keyring-v1")
        self.assertEqual(len(calls), 1)
        self.assertIn(b"parent_state_ref", calls[0][2])
        self.assertIn(b"zhouyi:e09:branch-merge:v2", calls[0][2])

    def test_branch_merge_authorization_rejects_bad_signature_and_wrong_scope(self):
        evidence_ref = self.add_reveal()
        authorization_ref = self.add_branch_authorization(evidence_ref)
        common = dict(
            episode_id=self.episode, authorization_ref=authorization_ref,
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
            world_family_by_evidence={evidence_ref: self.world},
            allow_legacy_migration=True,
            verifier_id="pinned-keyring-v1",
            now=datetime(2026, 11, 11, 12, tzinfo=timezone.utc),
        )
        with self.assertRaisesRegex(E09EvidenceBindingError, "signature"):
            resolve_branch_merge_authorization(
                self.e09, **common,
                signature_verifier=lambda issuer, alg, message, signature: False,
            )
        with self.assertRaisesRegex(E09EvidenceBindingError, "parent state"):
            resolve_branch_merge_authorization(
                self.e09, **{**common, "parent_state_ref": "wrong-parent"},
                signature_verifier=lambda *args: True,
            )

    def test_expired_branch_merge_authorization_is_rejected(self):
        evidence_ref = self.add_reveal()
        authorization_ref = self.add_branch_authorization(evidence_ref)
        with self.assertRaisesRegex(E09EvidenceBindingError, "not currently valid"):
            resolve_branch_merge_authorization(
                self.e09, episode_id=self.episode, authorization_ref=authorization_ref,
                parent_state_ref="parent-1", branch_ids=("left", "right"),
                scope=self.scope, learner_track=self.track,
                world_family_by_evidence={evidence_ref: self.world},
                allow_legacy_migration=True,
                signature_verifier=lambda *args: True, verifier_id="test-keyring",
                now=datetime(2026, 11, 13, tzinfo=timezone.utc),
            )

if __name__ == "__main__":
    unittest.main()
