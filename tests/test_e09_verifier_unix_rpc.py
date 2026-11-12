import os
import socket
import tempfile
import time
import unittest
from pathlib import Path

from prototype.e09_verifier_unix_rpc import (
    E09VerifierUnixRPC,
    SQLiteVerifierReceiptLedger,
    VerifierReceiptIdempotencyConflict,
)
from prototype.unix_ipc import (
    IPCRemoteError,
    StaticUnixPeerResolver,
    UnixJSONRPCClient,
)


class _FakeVerifier:
    def __init__(self):
        self.calls = []

    def issue_verification_receipt(self, **request):
        self.calls.append(dict(request))
        return {
            "receipt_id": f"receipt-{len(self.calls)}",
            "nonce": f"nonce-{len(self.calls)}",
            "signature": "test-signature",
        }


class VerifierReceiptLedgerTests(unittest.TestCase):
    def test_same_operation_and_request_returns_original_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.sqlite"
            ledger = SQLiteVerifierReceiptLedger(path)
            calls = []

            def issue():
                calls.append(True)
                return {"receipt_id": "receipt-1", "nonce": "nonce-1"}

            first = ledger.issue_once("operation-1", {"scope": "scope/a"}, issue)
            ledger.close()
            restarted = SQLiteVerifierReceiptLedger(path)
            try:
                second = restarted.issue_once(
                    "operation-1", {"scope": "scope/a"},
                    lambda: self.fail("durable retry must not issue a second receipt"),
                )
                self.assertEqual(first, second)
                self.assertEqual(len(calls), 1)
            finally:
                restarted.close()

    def test_same_operation_with_different_request_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = SQLiteVerifierReceiptLedger(Path(directory) / "receipts.sqlite")
            try:
                ledger.issue_once(
                    "operation-1", {"scope": "scope/a"},
                    lambda: {"receipt_id": "receipt-1", "nonce": "nonce-1"},
                )
                with self.assertRaises(VerifierReceiptIdempotencyConflict):
                    ledger.issue_once(
                        "operation-1", {"scope": "scope/b"},
                        lambda: {"receipt_id": "receipt-2", "nonce": "nonce-2"},
                    )
            finally:
                ledger.close()

    def test_ledger_rejects_world_accessible_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.sqlite"
            path.touch(mode=0o666)
            os.chmod(path, 0o666)
            with self.assertRaises(ValueError):
                SQLiteVerifierReceiptLedger(path)


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED"), "Linux SO_PEERCRED is required")
class E09VerifierUnixRPCTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scope = "scope/verifier-rpc"
        self.writer_id = "spiffe://zhouyi/e12a6-writer"
        self.verifier = _FakeVerifier()
        self.ledger = SQLiteVerifierReceiptLedger(self.root / "receipt-ledger.sqlite")
        self.socket_path = self.root / "verifier.sock"
        resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                self.writer_id, {"e12a6-writer"}, {self.scope},
            ),
        })
        self.server = E09VerifierUnixRPC(
            self.verifier,
            peer_resolver=resolver,
            socket_path=str(self.socket_path),
            receipt_ledger=self.ledger,
            allowed_writer_workload_ids={self.writer_id},
        )
        self.server.start()
        deadline = time.monotonic() + 2
        while not self.socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.socket_path.exists())
        self.client = UnixJSONRPCClient(self.socket_path)

    def tearDown(self):
        self.server.close()
        self.ledger.close()
        self.tmp.cleanup()

    def _request(self):
        return {
            "episode_id": "episode-1",
            "authorization_ref": "grant-1",
            "parent_state_ref": "parent-1",
            "branch_ids": ["branch-a", "branch-b"],
            "scope": self.scope,
            "learner_track": "track-a",
            "candidate_evidence_refs": ["evidence-1"],
        }

    def test_health_reports_ready_for_provisioned_writer(self):
        result = self.client.request("health", {}, operation_id="health-check-1")
        self.assertEqual(result, {
            "service": "e09-verifier", "protocol": "zhouyi-ipc/1", "ready": True,
        })

    def test_receipt_issuance_is_writer_only_and_durable_idempotent(self):
        first = self.client.request(
            "receipt.issue", self._request(), operation_id="issue-receipt-1"
        )
        second = self.client.request(
            "receipt.issue", self._request(), operation_id="issue-receipt-1"
        )
        self.assertEqual(first, second)
        self.assertEqual(len(self.verifier.calls), 1)
        self.assertEqual(first["receipt_id"], "receipt-1")

    def test_operation_id_cannot_be_reused_for_different_receipt_request(self):
        self.client.request(
            "receipt.issue", self._request(), operation_id="issue-receipt-2"
        )
        changed = self._request()
        changed["parent_state_ref"] = "attacker-parent"
        with self.assertRaises(IPCRemoteError) as caught:
            self.client.request(
                "receipt.issue", changed, operation_id="issue-receipt-2"
            )
        self.assertEqual(caught.exception.code, "idempotency_conflict")

    def test_non_writer_peer_cannot_request_receipt(self):
        learner_path = self.root / "learner.sock"
        resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                "spiffe://zhouyi/learner", {"learner"}, {self.scope},
            ),
        })
        denied_server = E09VerifierUnixRPC(
            self.verifier,
            peer_resolver=resolver,
            socket_path=str(learner_path),
            receipt_ledger=self.ledger,
            allowed_writer_workload_ids={self.writer_id},
        )
        denied_server.start()
        try:
            deadline = time.monotonic() + 2
            while not learner_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            client = UnixJSONRPCClient(learner_path)
            with self.assertRaises(IPCRemoteError) as caught:
                client.request("receipt.issue", self._request(), operation_id="learner-denied")
            self.assertEqual(caught.exception.code, "permission_denied")
            self.assertEqual(self.verifier.calls, [])
        finally:
            denied_server.close()

    def test_receipt_request_rejects_caller_selected_audience_or_issuer(self):
        body = self._request()
        body["audience"] = "attacker"
        with self.assertRaises(IPCRemoteError) as caught:
            self.client.request("receipt.issue", body, operation_id="bad-fields")
        self.assertEqual(caught.exception.code, "invalid_body")


if __name__ == "__main__":
    unittest.main()
