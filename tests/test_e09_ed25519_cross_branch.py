import base64
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation, canonical_hash
from prototype.csg_gcr_coordinator import CandidateProposal
from prototype.csg_gcr_e12a6_ingestion import CSGGCRIngestionError, ingest_typed_candidate
from prototype.e09_e12a6_evidence_bridge import (AUTHORIZATION_AUDIENCE, AUTHORIZATION_SIGNATURE_VERSION, branch_merge_authorization_signing_bytes, resolve_branch_merge_authorization)
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.shared_evidence_protocol import (
    STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore, canonical_json,
)
from prototype.typed_csg_gcr import TypedCandidateCoordinator, TypedCandidateProposal
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal, RoleBinding, VariableRef, VariableSpec,
)
from prototype.zpcm_memory import ZPCMMemory


def add_reveal(store, *, episode, scope, track, prediction_id, label):
    observation_id = f"obs-{prediction_id}"
    observation_event = f"{episode}:observation:{observation_id}"
    store.append_event(
        episode_id=episode, event_id=observation_event, event_type="observation",
        idempotency_key=observation_event, actor_role="runner",
        payload={"observation_id": observation_id, "query_id": observation_id,
                 "scope": scope, "split": "SUPPORT"},
        protocol_version=STRICT_PROTOCOL_VERSION,
    )
    commit_event = f"{episode}:prediction:{prediction_id}"
    semantic_digest = hashlib.sha256(prediction_id.encode()).hexdigest()
    commit = store.append_event(
        episode_id=episode, event_id=commit_event, event_type="prediction_commit",
        idempotency_key=commit_event, actor_role="learner",
        causation_refs=[observation_event],
        payload={"prediction_id": prediction_id, "observation_id": observation_id,
                 "query_id": observation_id, "scope": scope, "split": "SUPPORT",
                 "model_version": "model-e2e", "learner_track": track,
                 "decision_status": "PREDICT", "interop_commit_digest": semantic_digest},
        protocol_version=STRICT_PROTOCOL_VERSION,
    )
    reveal_event = f"{episode}:reveal:{prediction_id}"
    store.append_event(
        episode_id=episode, event_id=reveal_event, event_type="evidence_reveal",
        idempotency_key=reveal_event, actor_role="evaluator",
        causation_refs=[commit_event],
        payload={"prediction_id": prediction_id, "query_id": observation_id,
                 "scope": scope, "split": "SUPPORT", "commit_digest": semantic_digest,
                 "event_digest": commit.payload_digest, "learner_track": track,
                 "target_or_feedback": label, "reveal_source": "ed25519-e2e"},
        protocol_version=STRICT_PROTOCOL_VERSION,
    )
    return reveal_event


class E09Ed25519CrossBranchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.episode = "episode-cross-branch"
        self.scope = "world/cross-branch"
        self.track = "csg-e2e"
        self.e09 = SQLiteEvidenceStore(Path(self.tmp.name) / "e09.db")
        self.zpcm = ZPCMMemory(Path(self.tmp.name) / "zpcm.db")
        self.ledger = PersistentLifecycleLedger(self.zpcm, scope="cross-branch/project")
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.keyring = E09Ed25519IssuerKeyring({"issuer-production-test": self.public})

    def tearDown(self):
        self.e09.close()
        self.zpcm.close()
        self.tmp.cleanup()

    def test_real_ed25519_grant_authorizes_typed_candidate_and_persists_atomically(self):
        left_evidence = add_reveal(
            self.e09, episode=self.episode, scope=self.scope, track=self.track,
            prediction_id="left-support", label="PRIVATE_LEFT",
        )
        right_evidence = add_reveal(
            self.e09, episode=self.episode, scope=self.scope, track=self.track,
            prediction_id="right-support", label="PRIVATE_RIGHT",
        )
        grant_evidence = add_reveal(
            self.e09, episode=self.episode, scope=self.scope, track=self.track,
            prediction_id="grant-support", label="PRIVATE_GRANT_SUPPORT",
        )

        authorization_ref = f"{self.episode}:authorization:merge-1"
        unsigned = {
            "authorization_id": authorization_ref,
            "issuer_id": "issuer-production-test",
            "scope": self.scope,
            "parent_state_ref": "parent-1",
            "branch_ids": ["left", "right"],
            "evidence_refs": [grant_evidence],
            "issued_at": "2026-11-11T00:00:00+00:00",
            "expires_at": "2026-11-12T00:00:00+00:00",
            "signature_algorithm": "Ed25519",
            "signature_version": AUTHORIZATION_SIGNATURE_VERSION,
            "audience": AUTHORIZATION_AUDIENCE,
            "authorization_sequence": self.e09.replay_episode(self.episode)[-1]["sequence_no"] + 1,
        }
        signing_event = {
            "episode_id": self.episode, "event_id": authorization_ref,
            "event_type": "branch_merge_authorization",
            "protocol_version": STRICT_PROTOCOL_VERSION,
            "payload_schema": "branch_merge_authorization@2",
            "actor_role": "authorizer",
            "causation_refs": [grant_evidence],
            "integrity_metadata": {"policy": "branch-merge-v2"},
            "payload": unsigned,
        }
        signature = base64.b64encode(
            self.private.sign(branch_merge_authorization_signing_bytes(signing_event))
        ).decode("ascii")
        self.e09.append_event(
            episode_id=self.episode, event_id=authorization_ref,
            event_type="branch_merge_authorization", idempotency_key=authorization_ref,
            actor_role="authorizer", causation_refs=[grant_evidence],
            payload={**unsigned, "signature": signature},
            payload_schema="branch_merge_authorization@2",
            integrity_metadata={"policy": "branch-merge-v2"},
            expected_sequence=unsigned["authorization_sequence"] - 1,
            protocol_version=STRICT_PROTOCOL_VERSION,
        )

        permit = resolve_branch_merge_authorization(
            self.e09, episode_id=self.episode, authorization_ref=authorization_ref,
            parent_state_ref="parent-1", branch_ids=("left", "right"),
            scope=self.scope, learner_track=self.track,
            world_family_by_evidence={grant_evidence: "authorization-world"},
            allow_legacy_migration=True,
            signature_verifier=self.keyring, verifier_id=self.keyring.verifier_id,
            now=datetime(2026, 11, 11, 12, tzinfo=timezone.utc),
        )
        base = {"node:left": {"value": 0}, "node:right": {"value": 0}}
        left_ref, right_ref = VariableRef("world", "left"), VariableRef("world", "right")
        left_edge = HyperedgeProposal(
            "proposal-left", "parent-1", "left", "supports",
            (RoleBinding("subject", left_ref, "entity-left", "Entity"),),
            (left_evidence,),
        )
        right_edge = HyperedgeProposal(
            "proposal-right", "parent-1", "right", "supports",
            (RoleBinding("subject", right_ref, "entity-right", "Entity"),),
            (right_evidence,),
        )
        rows = (
            TypedCandidateProposal(
                CandidateProposal("proposal-left", "parent-1", "left", (), (left_evidence,), score=1.0),
                left_edge, (VariableSpec(left_ref, "Entity"),),
            ),
            TypedCandidateProposal(
                CandidateProposal("proposal-right", "parent-1", "right", (), (right_evidence,), score=1.0),
                right_edge, (VariableSpec(right_ref, "Entity"),),
            ),
        )
        left_delta = BranchDelta(
            "left-delta", DeltaOperation.UPDATE_ATTRIBUTE, "node:left",
            canonical_hash(base["node:left"]), {"value": 1}, ("derivation:left",), None, 1,
        )
        right_delta = BranchDelta(
            "right-delta", DeltaOperation.UPDATE_ATTRIBUTE, "node:right",
            canonical_hash(base["node:right"]), {"value": 2}, ("derivation:right",), None, 1,
        )
        snapshots = (
            BranchSnapshot("parent-1", canonical_hash(base), "left", 0, (left_delta,),
                           (), ("node:left",), ("derivation:left",), ("root", "left")),
            BranchSnapshot("parent-1", canonical_hash(base), "right", 0, (right_delta,),
                           (), ("node:right",), ("derivation:right",), ("root", "right")),
        )
        report = TypedCandidateCoordinator().coordinate(
            rows, base_state=base, branch_snapshots=snapshots,
            branch_merge_authorization=permit,
        )
        combined = next(
            item for item in report.candidates
            if len(item.coordinated.proposal_ids) == 2
        )
        self.assertEqual(combined.branch_merge_authorization_ref, authorization_ref)
        self.assertEqual(combined.branch_merge_authorization_evidence_refs, (grant_evidence,))

        # A valid v0.3 signature does not upgrade caller-labelled legacy evidence
        # into domain-authenticated lifecycle evidence.
        with self.assertRaisesRegex(CSGGCRIngestionError, "trusted domain registry is required"):
            ingest_typed_candidate(
                combined, ledger=self.ledger, e09_store=self.e09,
                episode_id=self.episode, scope=self.scope, learner_track=self.track,
                grammar_version="cross-branch-e2e-v1",
                world_family_by_evidence={
                    left_evidence: "left-world",
                    right_evidence: "right-world",
                },
                branch_merge_authorization=permit,
            )
        self.assertEqual(len(self.ledger.snapshot()["candidates"]), 0)
        self.assertEqual(len(self.ledger.snapshot()["evidence"]), 0)
        self.assertEqual(self.zpcm.replay_lifecycle_events(scope="cross-branch/project"), [])

    def test_unknown_and_revoked_issuers_fail_closed(self):
        message = b"canonical authorization bytes"
        signature = base64.b64encode(self.private.sign(message)).decode("ascii")
        self.assertFalse(self.keyring("unknown", "Ed25519", message, signature))
        revoked = E09Ed25519IssuerKeyring(
            {"issuer-production-test": self.public},
            revoked_issuers=("issuer-production-test",),
        )
        self.assertFalse(revoked("issuer-production-test", "Ed25519", message, signature))
        self.assertNotEqual(self.keyring.verifier_id, revoked.verifier_id)

    def test_key_rotation_changes_verifier_identity_and_invalidates_old_signature(self):
        replacement = Ed25519PrivateKey.generate()
        replacement_public = replacement.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        rotated = E09Ed25519IssuerKeyring({"issuer-production-test": replacement_public})
        message = b"rotation test"
        old_signature = base64.b64encode(self.private.sign(message)).decode("ascii")
        self.assertFalse(rotated("issuer-production-test", "Ed25519", message, old_signature))
        self.assertNotEqual(self.keyring.verifier_id, rotated.verifier_id)


if __name__ == "__main__":
    unittest.main()
