import base64
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation, canonical_hash, validate_merge_authorization
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


def add_authorization(store, private_key, *, episode, scope, evidence_ref):
    authorization_ref = f"{episode}:authorization:grant-1"
    sequence = store.replay_episode(episode)[-1]["sequence_no"] + 1
    payload = {
        "authorization_id": authorization_ref,
        "issuer_id": "issuer-production-test",
        "scope": scope,
        "parent_state_ref": "parent-1",
        "branch_ids": ["left", "right"],
        "evidence_refs": [evidence_ref],
        "issued_at": "2026-11-11T00:00:00+00:00",
        "expires_at": "2026-11-12T00:00:00+00:00",
        "signature_algorithm": "Ed25519",
        "signature_version": AUTHORIZATION_SIGNATURE_VERSION,
        "audience": AUTHORIZATION_AUDIENCE,
        "authorization_sequence": sequence,
    }
    envelope = {
        "episode_id": episode, "event_id": authorization_ref,
        "event_type": "branch_merge_authorization",
        "protocol_version": STRICT_PROTOCOL_VERSION,
        "payload_schema": "branch_merge_authorization@2",
        "actor_role": "authorizer", "causation_refs": [evidence_ref],
        "integrity_metadata": {}, "payload": payload,
    }
    payload["signature"] = base64.b64encode(
        private_key.sign(branch_merge_authorization_signing_bytes(envelope))
    ).decode("ascii")
    store.append_event(
        episode_id=episode, event_id=authorization_ref,
        event_type="branch_merge_authorization", idempotency_key=authorization_ref,
        actor_role="authorizer", causation_refs=[evidence_ref], payload=payload,
        payload_schema="branch_merge_authorization@2", integrity_metadata={},
        expected_sequence=sequence - 1, protocol_version=STRICT_PROTOCOL_VERSION,
    )
    return authorization_ref


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

    def test_legacy_ed25519_grant_cannot_authorize_domain_sensitive_merge(self):
        grant_evidence = add_reveal(
            self.e09, episode=self.episode, scope=self.scope, track=self.track,
            prediction_id="grant", label="PRIVATE_GRANT_SUPPORT",
        )
        authorization_ref = add_authorization(
            self.e09, self.private, episode=self.episode, scope=self.scope,
            evidence_ref=grant_evidence,
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
        self.assertEqual(permit.issuer_id, "issuer-production-test")
        self.assertFalse(permit.domain_provenance_verified)
        with self.assertRaisesRegex(ValueError, "trusted domain provenance"):
            validate_merge_authorization(permit, "parent-1", ("left", "right"))


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
