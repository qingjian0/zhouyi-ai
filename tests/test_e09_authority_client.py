import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from prototype.e09_authority_client import E09AuthorityRPCClient, E09LearnerMemorySource
from prototype.e09_authority_services import (
    E09AuthenticatedWorkload,
    E09AuthorityService,
    E09DomainBinding,
)
from prototype.e09_unix_rpc import E09AuthorityUnixRPC, UnixPeerWorkloadAuthenticator
from prototype.shared_evidence_protocol import SQLiteEvidenceStore, digest_payload
from prototype.unix_ipc import StaticUnixPeerResolver, UnixJSONRPCClient
from prototype.zpcm_memory import ZPCMMemory


class _Signer:
    def sign(self, issuer_id, message):
        return "test-signature"


class _Registry:
    def resolve(self, *, episode_id, scope, observation_id):
        return E09DomainBinding("family-test", "registry-test", "v1")


def _principal(workload_id, role, scope):
    import hashlib
    return E09AuthenticatedWorkload(
        workload_id=workload_id,
        issuer_id=f"issuer-{role}",
        roles=frozenset({role}),
        scopes=frozenset({scope}),
        identity_provider="test-unix-peer",
        authentication_method="SO_PEERCRED",
        credential_fingerprint=hashlib.sha256(workload_id.encode()).hexdigest(),
    )


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED"), "Linux SO_PEERCRED is required")
class E09RemoteZPCMMemoryTests(unittest.TestCase):
    def test_zpcm_sync_uses_remote_redacted_projection_without_store_handle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scope = "scope/remote-memory"
            episode = "episode-remote-memory"
            observer = _principal("spiffe://zhouyi/observer", "observer", scope)
            learner = _principal("spiffe://zhouyi/learner", "learner", scope)
            evaluator = _principal("spiffe://zhouyi/evaluator", "evaluator", scope)
            authenticator = UnixPeerWorkloadAuthenticator({
                item.workload_id: item for item in (observer, learner, evaluator)
            })
            store = SQLiteEvidenceStore(root / "e09.sqlite")
            authority = E09AuthorityService(
                store, authenticator=authenticator, signer=_Signer(),
                domain_registry=_Registry(),
            )
            socket_path = root / "authority.sock"
            resolver = StaticUnixPeerResolver({
                (os.getuid(), os.getgid()): (
                    learner.workload_id, learner.roles, learner.scopes,
                ),
            })
            server = E09AuthorityUnixRPC(
                authority, peer_resolver=resolver, socket_path=str(socket_path),
            )
            server.start()
            deadline = time.monotonic() + 2
            while not socket_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            transport = UnixJSONRPCClient(socket_path)
            rpc = E09AuthorityRPCClient(transport)
            memory = ZPCMMemory(root / "zpcm.sqlite")
            try:
                # Seed the source episode using authenticated observer/evaluator
                # services; this test's learner process never receives the DB.
                # Use an in-process test-only authority client with role-bound
                # Unix peers to append the Observation and Reveal.
                def call_as(principal, operation, body, operation_id):
                    role_name = sorted(principal.roles)[0]
                    peer_path = root / f"{role_name}.sock"
                    peer_resolver = StaticUnixPeerResolver({
                        (os.getuid(), os.getgid()): (
                            principal.workload_id, principal.roles, principal.scopes,
                        ),
                    })
                    peer_server = E09AuthorityUnixRPC(
                        authority, peer_resolver=peer_resolver, socket_path=str(peer_path),
                    )
                    peer_server.start()
                    try:
                        until = time.monotonic() + 2
                        while not peer_path.exists() and time.monotonic() < until:
                            time.sleep(0.01)
                        return UnixJSONRPCClient(peer_path).request(
                            operation, body, operation_id=operation_id,
                        )
                    finally:
                        peer_server.close()

                observation_event = f"{episode}:observation:obs-1"
                call_as(
                    observer, "observation.append",
                    {
                        "episode_id": episode, "event_id": observation_event,
                        "observation_id": "obs-1", "query_id": "query-1",
                        "scope": scope, "split": "SUPPORT",
                        "learner_workload_id": learner.workload_id,
                    },
                    "append-observation",
                )
                commit_event = f"{episode}:prediction:pred-1"
                digest = "d" * 64
                commit = call_as(
                    learner, "prediction.commit",
                    {
                        "episode_id": episode, "event_id": commit_event,
                        "causation_refs": [observation_event],
                        "payload": {
                            "prediction_id": "pred-1", "observation_id": "obs-1",
                            "query_id": "query-1", "scope": scope, "split": "SUPPORT",
                            "model_version": "model-1", "learner_track": "track-a",
                            "decision_status": "PREDICT", "interop_commit_digest": digest,
                        },
                    },
                    "append-commit",
                )
                call_as(
                    evaluator, "evidence.reveal",
                    {
                        "episode_id": episode, "event_id": f"{episode}:reveal:pred-1",
                        "causation_refs": [commit_event],
                        "payload": {
                            "prediction_id": "pred-1", "query_id": "query-1",
                            "scope": scope, "split": "SUPPORT",
                            "commit_digest": digest, "event_digest": commit["payload_digest"],
                            "learner_track": "track-a", "target_or_feedback": "never-in-zpcm",
                            "reveal_source": "test",
                        },
                    },
                    "append-reveal",
                )

                source = E09LearnerMemorySource(rpc, scope=scope, learner_track="track-a")
                added = memory.sync_episode(
                    source, episode_id=episode, scope=scope, learner_track="track-a"
                )
                self.assertGreater(added, 0)
                retrieved = memory.retrieve(scope=scope)
                self.assertNotIn("never-in-zpcm", str(retrieved))
                self.assertTrue(memory.verify_integrity()["ok"])
                self.assertFalse(hasattr(source, "store"))

                snapshot = {"weights": [0.1, 0.9], "step": 1}
                rpc.append_structure_version(
                    episode_id=episode,
                    event_id=f"{episode}:structure:checkpoint-1",
                    scope=scope,
                    learner_track="track-a",
                    payload={
                        "structure_id": "learner-state",
                        "version_id": "learner-state-v1",
                        "kind": "categorical",
                        "definition": {
                            "snapshot": snapshot,
                            "snapshot_digest": digest_payload(snapshot),
                            "ledger_snapshot": {"records": []},
                        },
                        "parent_version_ids": [],
                        "support_evidence_ids": [f"{episode}:reveal:pred-1"],
                    },
                    operation_id="append-checkpoint",
                )
                checkpoint = rpc.read_learner_checkpoint(
                    episode_id=episode, scope=scope, learner_track="track-a"
                )
                self.assertEqual(
                    checkpoint["payload"]["definition"]["snapshot"], snapshot
                )
            finally:
                memory.close()
                server.close()
                store.close()


if __name__ == "__main__":
    unittest.main()
