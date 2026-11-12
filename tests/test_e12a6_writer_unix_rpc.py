import dataclasses
import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from prototype.e12a6_writer_service import E12A6AuthenticatedWorkload
from prototype.e12a6_writer_unix_rpc import (
    E12A6WriterUnixRPC,
    UnixPeerE12A6Authenticator,
)
from prototype.unix_ipc import IPCRemoteError, StaticUnixPeerResolver, UnixJSONRPCClient
from tests.test_e12a6_writer_service import E12A6WriterServiceTests


def _proposal_wire(item):
    return dataclasses.asdict(item)


def _snapshot_wire(snapshot):
    return {
        "parent_state_ref": snapshot.parent_state_ref,
        "parent_state_hash": snapshot.parent_state_hash,
        "branch_id": snapshot.branch_id,
        "base_version": snapshot.base_version,
        "delta_events": [
            {
                "event_id": delta.event_id,
                "operation": delta.operation.value,
                "target_ref": delta.target_ref,
                "before_hash": delta.before_hash,
                "after_value": delta.after_value,
                "evidence_refs": list(delta.evidence_refs),
                "causal_parent": delta.causal_parent,
                "version": delta.version,
            }
            for delta in snapshot.delta_events
        ],
        "read_set": list(snapshot.read_set),
        "write_set": list(snapshot.write_set),
        "evidence_refs": list(snapshot.evidence_refs),
        "lineage": list(snapshot.lineage),
    }


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED"), "Linux SO_PEERCRED is required")
class E12A6WriterUnixRPCTests(unittest.TestCase):
    _add_reveal = E12A6WriterServiceTests._add_reveal
    _make_proposals_and_snapshots = E12A6WriterServiceTests._make_proposals_and_snapshots

    def setUp(self):
        E12A6WriterServiceTests.setUp(self)
        self.tmp_rpc = tempfile.TemporaryDirectory()
        self.rpc_root = Path(self.tmp_rpc.name)
        self.writer_id = "spiffe://zhouyi/candidate-submitter"
        submitter = E12A6AuthenticatedWorkload(
            workload_id=self.writer_id,
            roles=frozenset({"candidate_submitter"}),
            scopes=frozenset({self.scope}),
            identity_provider="test-unix-peer",
            authentication_method="SO_PEERCRED",
            credential_fingerprint="c" * 64,
        )
        self.writer._authenticator = UnixPeerE12A6Authenticator({
            self.writer_id: submitter,
        })
        self.socket_path = self.rpc_root / "writer.sock"
        resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                self.writer_id, {"candidate_submitter"}, {self.scope},
            ),
        })
        self.server = E12A6WriterUnixRPC(
            self.writer,
            peer_resolver=resolver,
            socket_path=str(self.socket_path),
        )
        self.server.start()
        deadline = time.monotonic() + 2
        while not self.socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.socket_path.exists())
        self.client = UnixJSONRPCClient(self.socket_path)

    def tearDown(self):
        self.server.close()
        self.tmp_rpc.cleanup()
        E12A6WriterServiceTests.tearDown(self)

    def _body(self):
        from prototype.csg_gcr_coordinator import GlobalConstraints
        return {
            "proposals": [_proposal_wire(item) for item in self.proposals],
            "base_state": self.base_state,
            "branch_snapshots": [_snapshot_wire(item) for item in self.snapshots],
            "receipt": self.receipt,
            "scope": self.scope,
            "grammar_version": "csg-gcr-writer-v1",
            "selected_proposal_ids": ["edge-left", "edge-right"],
            "constraints": dataclasses.asdict(GlobalConstraints()),
        }

    def test_rpc_recomputes_and_atomically_consumes_receipt_with_retry(self):
        body = self._body()
        first = self.client.request(
            "candidate.submit_authorized_merge",
            body,
            operation_id=self.receipt["receipt_id"],
        )
        second = self.client.request(
            "candidate.submit_authorized_merge",
            body,
            operation_id=self.receipt["receipt_id"],
        )
        self.assertEqual(first["authorization_receipt_id"], self.receipt["receipt_id"])
        self.assertFalse(first["lifecycle_receipt"]["replayed"])
        self.assertTrue(second["lifecycle_receipt"]["replayed"])
        self.assertEqual(
            len(self.memory.replay_lifecycle_events(scope=self.scope)), 7
        )
        self.assertNotIn("PRIVATE-proposal-left", str(first))
        self.assertNotIn("PRIVATE-branch-left", str(first))

    def test_rpc_rejects_unprovisioned_candidate_submitter(self):
        denied_path = self.rpc_root / "unprovisioned.sock"
        resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                "spiffe://zhouyi/unprovisioned",
                {"candidate_submitter"},
                {self.scope},
            ),
        })
        denied_server = E12A6WriterUnixRPC(
            self.writer,
            peer_resolver=resolver,
            socket_path=str(denied_path),
        )
        denied_server.start()
        try:
            deadline = time.monotonic() + 2
            while not denied_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            client = UnixJSONRPCClient(denied_path)
            with self.assertRaises(IPCRemoteError) as caught:
                client.request(
                    "candidate.submit_authorized_merge",
                    self._body(),
                    operation_id=self.receipt["receipt_id"],
                )
            self.assertEqual(caught.exception.code, "authentication_failed")
            self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])
        finally:
            denied_server.close()

    def test_rpc_rejects_malformed_typed_candidate_schema(self):
        body = self._body()
        body["proposals"][0].pop("hyperedge")
        with self.assertRaises(IPCRemoteError) as caught:
            self.client.request(
                "candidate.submit_authorized_merge",
                body,
                operation_id=self.receipt["receipt_id"],
            )
        self.assertEqual(caught.exception.code, "invalid_body")
        self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])

    def test_operation_id_must_be_the_signed_receipt_id(self):
        with self.assertRaises(IPCRemoteError) as caught:
            self.client.request(
                "candidate.submit_authorized_merge",
                self._body(),
                operation_id="not-the-receipt-id",
            )
        self.assertEqual(caught.exception.code, "invalid_operation_id")
        self.assertEqual(self.memory.replay_lifecycle_events(scope=self.scope), [])


if __name__ == "__main__":
    unittest.main()
