"""Cross-process E09 Verifier -> E12-A6 Writer UDS integration tests.

The E09 Verifier consumes a separately opened read-only SQLite snapshot.
The only receipt crossing the process boundary is the signed JSON receipt
returned by receipt.issue; the Writer never receives an in-process capability.
"""
import os
import sqlite3
import stat
import unittest
from pathlib import Path

from prototype.e09_authority_services import E09VerifierService
from prototype.e09_verifier_unix_rpc import (
    E09VerifierUnixRPC,
    SQLiteVerifierReceiptLedger,
)
from prototype.shared_evidence_protocol import SQLiteEvidenceReader
from prototype.unix_ipc import StaticUnixPeerResolver, UnixJSONRPCClient
from tests.test_e12a6_writer_unix_rpc import E12A6WriterUnixRPCTests


class E09ToE12A6UnixEndToEndTests(E12A6WriterUnixRPCTests):
    """Exercise receipt issue and receipt consumption through two real UDS servers."""

    def test_read_only_verifier_issues_receipt_consumed_by_writer_rpc(self):
        snapshot_path = self.rpc_root / "verifier-evidence.sqlite3"
        source = sqlite3.connect(self.e09.path)
        snapshot = sqlite3.connect(snapshot_path)
        try:
            source.backup(snapshot)
        finally:
            snapshot.close()
            source.close()
        os.chmod(snapshot_path, 0o600)

        reader = SQLiteEvidenceReader(snapshot_path)
        receipt_ledger = SQLiteVerifierReceiptLedger(
            self.rpc_root / "verifier-receipts.sqlite3"
        )
        verifier = E09VerifierService(
            reader,
            signature_verifier=self.verifier._signature_verifier,
            verifier_id=self.verifier.verifier_id,
            clock=self.verifier._clock,
            receipt_signer=self.verifier._receipt_signer,
            receipt_ttl=self.verifier._receipt_ttl,
        )

        verifier_socket = self.rpc_root / "verifier.sock"
        verifier_resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                self.writer_id, {"e12a6-writer"}, {self.scope},
            ),
        })
        verifier_rpc = E09VerifierUnixRPC(
            verifier,
            peer_resolver=verifier_resolver,
            socket_path=str(verifier_socket),
            receipt_ledger=receipt_ledger,
            allowed_writer_workload_ids={self.writer_id},
        )
        verifier_rpc.start()
        try:
            verifier_client = UnixJSONRPCClient(verifier_socket)
            request = {
                "episode_id": self.episode,
                "authorization_ref": "grant-writer",
                "parent_state_ref": "parent-writer",
                "branch_ids": ["left", "right"],
                "scope": self.scope,
                "learner_track": self.track,
                "world_family_by_evidence": {
                    self.authorization_evidence_ref: "family-a",
                },
                "candidate_evidence_refs": [
                    self.proposal_ref,
                    self.proposal_ref_right,
                    self.branch_ref_left,
                    self.branch_ref_right,
                    self.authorization_evidence_ref,
                ],
                "candidate_evidence_world_family_by_ref": {
                    ref: "family-a" for ref in (
                        self.proposal_ref,
                        self.proposal_ref_right,
                        self.branch_ref_left,
                        self.branch_ref_right,
                        self.authorization_evidence_ref,
                    )
                },
            }
            issued = verifier_client.request(
                "receipt.issue", request, operation_id="e2e-issue-receipt-1"
            )
            self.assertEqual(issued["audience"], "e12a6-lifecycle-writer")
            self.assertEqual(issued["verifier_id"], self.verifier_id)
            self.assertEqual(
                set(issued["evidence_refs"]),
                {
                    self.proposal_ref, self.proposal_ref_right,
                    self.branch_ref_left, self.branch_ref_right,
                    self.authorization_evidence_ref,
                },
            )

            # The read model is genuinely opened in query-only mode and cannot
            # be used by the Verifier to append or mutate Authority evidence.
            with self.assertRaises(sqlite3.OperationalError):
                reader._db.execute("DELETE FROM events")

            body = self._body()
            body["receipt"] = issued
            operation_id = issued["receipt_id"]
            first = self.client.request(
                "candidate.submit_authorized_merge",
                body,
                operation_id=operation_id,
            )
            second = self.client.request(
                "candidate.submit_authorized_merge",
                body,
                operation_id=operation_id,
            )
            self.assertEqual(first["authorization_receipt_id"], operation_id)
            self.assertFalse(first["lifecycle_receipt"]["replayed"])
            self.assertTrue(second["lifecycle_receipt"]["replayed"])
            self.assertEqual(len(self.memory.replay_lifecycle_events(scope=self.scope)), 7)
            self.assertEqual(
                [event["payload"]["kind"] for event in
                 self.memory.replay_lifecycle_events(scope=self.scope)][-2:],
                ["candidate_registered", "authorization_consumed"],
            )
            self.assertNotIn("PRIVATE-proposal-left", str(first))
            self.assertNotIn("PRIVATE-branch-left", str(first))
        finally:
            verifier_rpc.close()
            receipt_ledger.close()
            reader.close()


if __name__ == "__main__":
    unittest.main()
