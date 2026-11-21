import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import socket
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.csg_branch_delta import BranchDelta, BranchSnapshot, DeltaOperation, canonical_hash
from prototype.csg_gcr_coordinator import CandidateProposal
from prototype.e09_authority_services import (
    E09AuthenticatedWorkload, E09AuthorityService, E09VerifierService,
)
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_verification_receipt import verification_receipt_signing_bytes
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e12a6_lifecycle_contract import CandidateState
from prototype.e12a6_uds_writer_application import (
    E12A6PeerWorkloadBinding, E12A6UDSWriterApplication,
)
from prototype.e12a6_writer_service import (
    E12A6AuthenticatedWorkload, E12A6AuthorizationError, E12A6WriterService,
)
from prototype.e12a6_zpcm_persistence import PersistentLifecycleLedger
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore
from prototype.typed_csg_gcr import TypedCandidateProposal
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal, RoleBinding, VariableRef, VariableSpec,
)
from prototype.zpcm_memory import ZPCMMemory


class _FixedClock:
    def __init__(self, current):
        self.current = current

    def now(self):
        return self.current


class _E09Authenticator:
    def __init__(self, identities):
        self.identities = identities

    def authenticate(self, credential):
        if credential not in self.identities:
            raise ValueError("unknown E09 credential")
        return self.identities[credential]


class _E12Authenticator:
    def __init__(self, identities):
        self.identities = identities

    def authenticate(self, credential):
        if credential not in self.identities:
            raise ValueError("unknown E12 credential")
        return self.identities[credential]


class _NamedSigner:
    def __init__(self, private_key, key_id):
        self.private_key = private_key
        self.key_id = key_id

    def sign(self, issuer_id, message):
        if issuer_id != self.key_id:
            raise ValueError("unexpected signer identity")
        return base64.b64encode(self.private_key.sign(message)).decode("ascii")


def _public_bytes(private_key):
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


class E12A6WriterServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.episode = "episode-writer"
        self.scope = "world/writer"
        self.track = "track-writer"
        self.now = datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc)
        self.e09 = SQLiteEvidenceStore(Path(self.tmp.name) / "e09.db")
        self.memory = ZPCMMemory(Path(self.tmp.name) / "zpcm.db")
        self.ledger = PersistentLifecycleLedger(self.memory, scope=self.scope)

        issuer_private = Ed25519PrivateKey.generate()
        issuer_keyring = E09Ed25519IssuerKeyring({"issuer-authority": _public_bytes(issuer_private)})
        self.verifier_id = issuer_keyring.verifier_id
        observer = E09AuthenticatedWorkload(
            workload_id="spiffe://zhouyi/observer", issuer_id="issuer-observer",
            roles=frozenset({"observer"}), scopes=frozenset({self.scope}),
            identity_provider="test-spiffe", authentication_method="mTLS",
            credential_fingerprint="o" * 64,
        )
        learner = E09AuthenticatedWorkload(
            workload_id="spiffe://zhouyi/learner", issuer_id="issuer-learner",
            roles=frozenset({"learner"}), scopes=frozenset({self.scope}),
            identity_provider="test-spiffe", authentication_method="mTLS",
            credential_fingerprint="l" * 64,
        )
        evaluator = E09AuthenticatedWorkload(
            workload_id="spiffe://zhouyi/evaluator", issuer_id="issuer-evaluator",
            roles=frozenset({"evaluator"}), scopes=frozenset({self.scope}),
            identity_provider="test-spiffe", authentication_method="mTLS",
            credential_fingerprint="e" * 64,
        )
        authorizer = E09AuthenticatedWorkload(
            workload_id="spiffe://zhouyi/authorizer", issuer_id="issuer-authority",
            roles=frozenset({"authorizer"}), scopes=frozenset({self.scope}),
            identity_provider="test-spiffe", authentication_method="mTLS",
            credential_fingerprint="a" * 64,
        )
        self.domain_registry = StaticE09DomainRegistry({
            self.scope: E09DomainBinding(
                domain_id="domain:writer", world_family="family-a",
                registry_id="registry:writer", registry_version="v1",
            ),
        })
        self.e09_authority = E09AuthorityService(
            self.e09,
            authenticator=_E09Authenticator({
                "observer-cert": observer, "learner-cert": learner,
                "evaluator-cert": evaluator, "authorizer-cert": authorizer,
            }),
            signer=_NamedSigner(issuer_private, "issuer-authority"),
            clock=_FixedClock(datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)),
            max_grant_ttl=timedelta(hours=1),
            domain_registry=self.domain_registry,
        )

        self.proposal_ref = self._add_reveal("proposal-left")
        self.proposal_ref_right = self._add_reveal("proposal-right")
        self.branch_ref_left = self._add_reveal("branch-left")
        self.branch_ref_right = self._add_reveal("branch-right")
        self.authorization_evidence_ref = self._add_reveal("authorization")
        self.e09_authority.issue_branch_merge_authorization(
            "authorizer-cert",
            episode_id=self.episode,
            authorization_id="grant-writer",
            scope=self.scope,
            parent_state_ref="parent-writer",
            branch_ids=["left", "right"],
            evidence_refs=[self.authorization_evidence_ref],
            ttl=timedelta(minutes=45),
        )

        self.receipt_signer_private = Ed25519PrivateKey.generate()
        self.verifier = E09VerifierService(
            self.e09,
            signature_verifier=issuer_keyring.verify,
            verifier_id=self.verifier_id,
            clock=_FixedClock(self.now),
            receipt_signer=_NamedSigner(self.receipt_signer_private, self.verifier_id),
            receipt_ttl=timedelta(minutes=1),
            domain_registry=self.domain_registry,
        )
        self.receipt = self.verifier.issue_verification_receipt(
            episode_id=self.episode,
            authorization_ref="grant-writer",
            parent_state_ref="parent-writer",
            branch_ids=("left", "right"),
            scope=self.scope,
            learner_track=self.track,
            candidate_evidence_refs=(
                self.proposal_ref, self.proposal_ref_right, self.branch_ref_left, self.branch_ref_right, self.authorization_evidence_ref,
            ),
        )
        receipt_keyring = E09Ed25519IssuerKeyring({
            self.verifier_id: _public_bytes(self.receipt_signer_private),
        })
        submitter = E12A6AuthenticatedWorkload(
            workload_id="spiffe://zhouyi/candidate-submitter",
            roles=frozenset({"candidate_submitter"}),
            scopes=frozenset({self.scope}),
            identity_provider="test-spiffe",
            authentication_method="mTLS",
            credential_fingerprint="c" * 64,
        )
        denied = E12A6AuthenticatedWorkload(
            workload_id="spiffe://zhouyi/read-only",
            roles=frozenset({"reader"}),
            scopes=frozenset({self.scope}),
            identity_provider="test-spiffe",
            authentication_method="mTLS",
            credential_fingerprint="d" * 64,
        )
        self.writer_clock = _FixedClock(self.now)
        self.writer = E12A6WriterService(
            self.ledger,
            authenticator=_E12Authenticator({
                "submitter-cert": submitter, "reader-cert": denied,
            }),
            receipt_signature_verifier=receipt_keyring.verify,
            trusted_verifier_id=self.verifier_id,
            clock=self.writer_clock,
        )
        self.proposals, self.base_state, self.snapshots = self._make_proposals_and_snapshots()

    def tearDown(self):
        self.e09.close()
        self.memory.close()
        self.tmp.cleanup()

    def _add_reveal(self, name):
        observation_id = f"obs-{name}"
        observation_event = f"{self.episode}:observation:{observation_id}"
        self.e09_authority.append_observation(
            "observer-cert", episode_id=self.episode, event_id=observation_event,
            idempotency_key=observation_event,
            payload={"observation_id": observation_id, "query_id": observation_id,
                     "scope": self.scope, "split": "SUPPORT"},
        )
        prediction_id = f"prediction-{name}"
        commit_digest = hashlib.sha256(prediction_id.encode()).hexdigest()
        commit_event = f"{self.episode}:prediction:{prediction_id}"
        commit = self.e09_authority.append_prediction_commit(
            "learner-cert", episode_id=self.episode, event_id=commit_event,
            idempotency_key=commit_event, causation_refs=[observation_event],
            payload={"prediction_id": prediction_id, "observation_id": observation_id,
                     "query_id": observation_id, "scope": self.scope, "split": "SUPPORT",
                     "model_version": "model-writer", "learner_track": self.track,
                     "decision_status": "PREDICT", "interop_commit_digest": commit_digest},
        )
        reveal_ref = f"{self.episode}:reveal:{prediction_id}"
        self.e09_authority.append_evidence_reveal(
            "evaluator-cert", episode_id=self.episode, event_id=reveal_ref,
            idempotency_key=reveal_ref,
            payload={"prediction_id": prediction_id, "query_id": observation_id,
                     "scope": self.scope, "split": "SUPPORT",
                     "commit_digest": commit_digest, "event_digest": commit.payload_digest,
                     "learner_track": self.track, "target_or_feedback": f"PRIVATE-{name}"},
            causation_refs=[commit_event],
        )
        return reveal_ref

    def _make_proposals_and_snapshots(self):
        x, y, z = (
            VariableRef("world", "left-entity"),
            VariableRef("world", "shared-entity"),
            VariableRef("world", "right-entity"),
        )
        left_edge = HyperedgeProposal(
            "edge-left", "parent-writer", "left", "supports",
            (
                RoleBinding("source", x, "entity-left", "Entity"),
                RoleBinding("target", y, "entity-shared", "Entity"),
            ),
            (self.proposal_ref,),
        )
        right_edge = HyperedgeProposal(
            "edge-right", "parent-writer", "right", "amplifies",
            (
                RoleBinding("source", y, "entity-shared", "Entity"),
                RoleBinding("target", z, "entity-right", "Entity"),
            ),
            (self.proposal_ref_right,),
        )
        left = TypedCandidateProposal(
            CandidateProposal("edge-left", "parent-writer", "left", (), (self.proposal_ref,),
                              score=2.0, candidate_kind="supports"),
            left_edge, (VariableSpec(x, "Entity"), VariableSpec(y, "Entity")),
        )
        right = TypedCandidateProposal(
            CandidateProposal("edge-right", "parent-writer", "right", (), (self.proposal_ref_right,),
                              score=1.0, candidate_kind="amplifies"),
            right_edge, (VariableSpec(y, "Entity"), VariableSpec(z, "Entity")),
        )
        base = {"node:left": {"value": 0}, "node:right": {"value": 0}}
        left_delta = BranchDelta(
            "delta-left", DeltaOperation.UPDATE_ATTRIBUTE, "node:left",
            canonical_hash(base["node:left"]), {"value": 1},
            (self.branch_ref_left,), None, 1,
        )
        right_delta = BranchDelta(
            "delta-right", DeltaOperation.UPDATE_ATTRIBUTE, "node:right",
            canonical_hash(base["node:right"]), {"value": 2},
            (self.branch_ref_right,), None, 1,
        )
        snapshots = (
            BranchSnapshot(
                "parent-writer", canonical_hash(base), "left", 0, (left_delta,),
                (), ("node:left",), (self.branch_ref_left,), ("root", "left"),
            ),
            BranchSnapshot(
                "parent-writer", canonical_hash(base), "right", 0, (right_delta,),
                (), ("node:right",), (self.branch_ref_right,), ("root", "right"),
            ),
        )
        return (left, right), base, snapshots

    def _submit(self, receipt=None, credential="submitter-cert"):
        return self.writer.submit_authorized_merge_candidate(
            credential,
            proposals=self.proposals,
            base_state=self.base_state,
            branch_snapshots=self.snapshots,
            receipt=self.receipt if receipt is None else receipt,
            scope=self.scope,
            grammar_version="csg-gcr-writer-v1",
            selected_proposal_ids=("edge-left", "edge-right"),
        )

    def test_writer_recomputes_merge_and_atomically_consumes_signed_receipt(self):
        result = self._submit()
        self.assertEqual(result.projection.native_candidate.state, CandidateState.OBSERVED)
        self.assertIsNotNone(result.lifecycle_receipt.authorization)
        self.assertEqual(result.authorization_receipt_id, self.receipt["receipt_id"])
        events = self.memory.replay_lifecycle_events(scope=self.scope)
        self.assertEqual(
            [event["payload"]["kind"] for event in events],
            ["evidence_registered", "evidence_registered", "evidence_registered",
             "evidence_registered", "evidence_registered", "candidate_registered",
             "authorization_consumed"],
        )
        self.assertNotIn("PRIVATE-proposal-left", str(events))
        self.assertNotIn("PRIVATE-proposal-right", str(events))
        self.assertNotIn("PRIVATE-branch-left", str(events))
        self.assertNotIn("PRIVATE-branch-right", str(events))
        self.assertNotIn("PRIVATE-authorization", str(events))

    def test_same_signed_receipt_retry_is_idempotent_within_ttl(self):
        first = self._submit()
        self.writer_clock.current = self.now + timedelta(seconds=10)
        second = self._submit()
        self.assertFalse(first.lifecycle_receipt.replayed)
        self.assertTrue(second.lifecycle_receipt.replayed)
        self.assertTrue(second.lifecycle_receipt.authorization.replayed)
        self.assertEqual(len(self.memory.replay_lifecycle_events(scope=self.scope)), 7)

    def test_reader_role_cannot_write_candidates(self):
        with self.assertRaises(E12A6AuthorizationError):
            self._submit(credential="reader-cert")
        self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])

    def test_receipt_scope_tampering_fails_before_any_write(self):
        altered = dict(self.receipt)
        altered["scope"] = "world/other"
        with self.assertRaises(ValueError):
            self._submit(receipt=altered)
        self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])

    def test_valid_signature_cannot_omit_evidence_from_recomputed_candidate(self):
        altered = dict(self.receipt)
        omitted = self.proposal_ref_right
        altered["evidence_refs"] = [
            ref for ref in altered["evidence_refs"] if ref != omitted
        ]
        altered["evidence"] = [
            item for item in altered["evidence"] if item["evidence_id"] != omitted
        ]
        altered["signature"] = ""
        altered["signature"] = base64.b64encode(
            self.receipt_signer_private.sign(verification_receipt_signing_bytes(altered))
        ).decode("ascii")
        with self.assertRaises(E12A6AuthorizationError):
            self._submit(receipt=altered)
        self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])

    def test_candidate_evidence_set_must_match_signed_receipt(self):
        altered = dict(self.receipt)
        altered["evidence_refs"] = [self.proposal_ref]
        with self.assertRaises(ValueError):
            self._submit(receipt=altered)
        self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])


    def test_real_uds_submit_receipt_consumption_and_restart_replay(self):
        database_path = Path(self.tmp.name) / "uds-runtime.db"
        socket_path = Path(self.tmp.name) / "uds-runtime.sock"

        def wire_request():
            proposal_rows = []
            for item in self.proposals:
                p, edge = item.proposal, item.hyperedge
                proposal_rows.append({
                    "proposal": {
                        "proposal_id": p.proposal_id, "parent_state_ref": p.parent_state_ref,
                        "branch_id": p.branch_id, "bindings": [list(pair) for pair in p.bindings],
                        "evidence_refs": list(p.evidence_refs), "requires": list(p.requires),
                        "excludes": list(p.excludes), "score": p.score, "cost": p.cost,
                        "candidate_kind": p.candidate_kind,
                    },
                    "hyperedge": {
                        "edge_id": edge.edge_id, "parent_state_ref": edge.parent_state_ref,
                        "branch_id": edge.branch_id, "relation_type": edge.relation_type,
                        "roles": [{
                            "role": role.role,
                            "variable": {"namespace": role.variable.namespace, "name": role.variable.name},
                            "member_id": role.member_id, "member_type": role.member_type,
                        } for role in edge.roles],
                        "evidence_refs": list(edge.evidence_refs),
                        "active_from": edge.active_from, "active_until": edge.active_until,
                    },
                    "variables": [{
                        "ref": {"namespace": spec.ref.namespace, "name": spec.ref.name},
                        "value_type": spec.value_type, "required": spec.required,
                    } for spec in item.variables],
                    "constraints": {"equal": [], "not_equal": [], "role_requirements": [], "subtype_of": []},
                    "semantic_status": item.semantic_status,
                })
            snapshot_rows = []
            for snapshot in self.snapshots:
                snapshot_rows.append({
                    "parent_state_ref": snapshot.parent_state_ref,
                    "parent_state_hash": snapshot.parent_state_hash,
                    "branch_id": snapshot.branch_id, "base_version": snapshot.base_version,
                    "delta_events": [{
                        "event_id": delta.event_id, "operation": delta.operation.value,
                        "target_ref": delta.target_ref, "before_hash": delta.before_hash,
                        "after_value": delta.after_value, "evidence_refs": list(delta.evidence_refs),
                        "causal_parent": delta.causal_parent, "version": delta.version,
                    } for delta in snapshot.delta_events],
                    "read_set": list(snapshot.read_set), "write_set": list(snapshot.write_set),
                    "evidence_refs": list(snapshot.evidence_refs), "lineage": list(snapshot.lineage),
                })
            return {
                "version": 1, "operation": "submit_authorized_merge_candidate",
                "scope": self.scope, "grammar_version": "csg-gcr-writer-v1",
                "proposals": proposal_rows, "base_state": self.base_state,
                "branch_snapshots": snapshot_rows, "receipt": self.receipt,
                "selected_proposal_ids": ["edge-left", "edge-right"],
            }

        def submit(payload):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(5)
                client.connect(str(socket_path))
                client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
                data = bytearray()
                while b"\n" not in data:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    data.extend(chunk)
            return json.loads(bytes(data).split(b"\n", 1)[0])

        def new_application():
            uid, gid = os.getuid(), os.getgid()
            return E12A6UDSWriterApplication(
                database_path, socket_path, scope=self.scope,
                peer_bindings=(E12A6PeerWorkloadBinding(uid, gid, "submitter-cert"),),
                authenticator=self.writer._authenticator,
                receipt_signature_verifier=self.writer._receipt_signature_verifier,
                trusted_verifier_id=self.verifier_id, allowed_uids={uid},
                clock=self.writer_clock,
            )

        payload = wire_request()
        app = new_application().start()
        try:
            wrong_scope = dict(payload)
            wrong_scope["scope"] = "world/attacker"
            rejected_scope = submit(wrong_scope)
            self.assertFalse(rejected_scope["ok"])

            forged = dict(payload)
            forged["workload_id"] = "spiffe://attacker/admin"
            rejected_identity = submit(forged)
            self.assertFalse(rejected_identity["ok"])

            expired = dict(payload)
            expired["receipt"] = dict(payload["receipt"])
            expired["receipt"]["expires_at"] = (self.now - timedelta(seconds=1)).isoformat()
            expired["receipt"]["signature"] = base64.b64encode(
                self.receipt_signer_private.sign(
                    verification_receipt_signing_bytes(expired["receipt"])
                )
            ).decode("ascii")
            rejected_expired = submit(expired)
            self.assertFalse(rejected_expired["ok"])
            self.assertEqual(app._runtime.ledger._memory.replay_lifecycle_events(scope=self.scope), [])

            with ThreadPoolExecutor(max_workers=4) as pool:
                concurrent = list(pool.map(submit, [payload] * 4))
            self.assertTrue(all(item["ok"] for item in concurrent), concurrent)
            self.assertEqual(sum(not item["result"]["replayed"] for item in concurrent), 1)
            self.assertEqual(sum(item["result"]["replayed"] for item in concurrent), 3)
            self.assertTrue(all(
                item["result"]["submitter_workload_id"] == "spiffe://zhouyi/candidate-submitter"
                for item in concurrent
            ))
        finally:
            app.close()

        restarted = new_application().start()
        try:
            second = submit(payload)
            self.assertTrue(second["ok"])
            self.assertTrue(second["result"]["replayed"])
            self.assertEqual(second["result"]["authorization_receipt_id"], self.receipt["receipt_id"])
        finally:
            restarted.close()

        reopened = ZPCMMemory(database_path)
        try:
            events = reopened.replay_lifecycle_events(scope=self.scope)
            self.assertEqual(len(events), 7)
            self.assertEqual(events[-1]["payload"]["kind"], "authorization_consumed")
            self.assertNotIn("PRIVATE-proposal-left", str(events))
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
