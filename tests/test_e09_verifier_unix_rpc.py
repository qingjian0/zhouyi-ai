import json
import multiprocessing
import os
import sqlite3
import socket
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from prototype.e09_verifier_unix_rpc import (
    E09VerifierUnixRPC,
    SQLiteVerifierReceiptLedger,
    VerifierReceiptIdempotencyConflict,
)
from prototype.shared_evidence_protocol import digest_payload
from prototype.unix_ipc import (
    IPCRemoteError,
    StaticUnixPeerResolver,
    UnixJSONRPCClient,
)


class _FakeVerifier:
    def __init__(self):
        self.calls = []

    def receipt_issued_at(self):
        return datetime.now(timezone.utc).isoformat()

    def issue_verification_receipt_with_identity(
        self, *, _receipt_id, _nonce, _issued_at, **request
    ):
        self.calls.append(dict(request))
        return {
            "receipt_id": _receipt_id,
            "nonce": _nonce,
            "issued_at": _issued_at,
            "signature": "test-signature",
        }




def _crash_during_receipt_signing(ledger_path, started_sender, release):
    """Child process blocks in the issuer after the durable reservation commit."""
    ledger = SQLiteVerifierReceiptLedger(ledger_path)
    try:
        def blocked_issuer(identity):
            started_sender.send(dict(identity))
            release.wait(30)
            return {
                "receipt_id": identity["receipt_id"],
                "nonce": identity["nonce"],
                "issued_at": identity["issued_at"],
                "signature": "must-not-be-persisted",
            }
        ledger.issue_once(
            "operation-process-crash", {"scope": "scope/process-crash"},
            blocked_issuer,
            issued_at_provider=lambda: "2026-11-12T03:00:00+00:00",
        )
    finally:
        ledger.close()


class VerifierReceiptLedgerTests(unittest.TestCase):
    def test_same_operation_and_request_returns_original_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.sqlite"
            ledger = SQLiteVerifierReceiptLedger(path)
            calls = []

            def issue(identity):
                calls.append(dict(identity))
                return {
                    "receipt_id": identity["receipt_id"],
                    "nonce": identity["nonce"],
                    "issued_at": identity["issued_at"],
                }

            first = ledger.issue_once("operation-1", {"scope": "scope/a"}, issue)
            ledger.close()
            restarted = SQLiteVerifierReceiptLedger(path)
            try:
                second = restarted.issue_once(
                    "operation-1", {"scope": "scope/a"},
                    lambda identity: self.fail("durable retry must not issue a second receipt"),
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
                    lambda identity: {
                        "receipt_id": identity["receipt_id"], "nonce": identity["nonce"],
                    },
                )
                with self.assertRaises(VerifierReceiptIdempotencyConflict):
                    ledger.issue_once(
                        "operation-1", {"scope": "scope/b"},
                        lambda identity: {
                            "receipt_id": identity["receipt_id"], "nonce": identity["nonce"],
                        },
                    )
            finally:
                ledger.close()

    def test_legacy_non_nullable_receipt_ledger_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.sqlite"
            request = {"scope": "scope/legacy"}
            receipt = {"receipt_id": "legacy-id", "nonce": "legacy-nonce"}
            db = sqlite3.connect(path)
            db.execute(
                "CREATE TABLE issued_receipts ("
                "operation_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, "
                "receipt_id TEXT NOT NULL UNIQUE, nonce TEXT NOT NULL UNIQUE, "
                "receipt_json TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
            db.execute(
                "INSERT INTO issued_receipts VALUES(?,?,?,?,?,?)",
                ("legacy-operation", digest_payload(request), "legacy-id", "legacy-nonce",
                 json.dumps(receipt), "2026-11-12T00:00:00+00:00"),
            )
            db.commit()
            db.close()
            os.chmod(path, 0o600)
            # Some CI runners execute tests as root while SQLite creates the
            # fixture under a mapped service UID; normalize ownership to the
            # identity that opens the ledger in this test.
            if os.geteuid() == 0:
                os.chown(path, os.geteuid(), -1)

            ledger = SQLiteVerifierReceiptLedger(path)
            try:
                result = ledger.issue_once(
                    "legacy-operation", request,
                    lambda identity: self.fail("legacy committed receipt must be preserved"),
                )
                self.assertEqual(result, receipt)
            finally:
                ledger.close()

    def test_pending_reservation_survives_crash_and_reuses_same_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.sqlite"
            first = SQLiteVerifierReceiptLedger(path)
            seen = []

            def crash_after_reservation(identity):
                seen.append(dict(identity))
                raise RuntimeError("simulated crash before receipt persistence")

            with self.assertRaises(RuntimeError):
                first.issue_once("operation-crash", {"scope": "scope/a"}, crash_after_reservation)
            first.close()

            restarted = SQLiteVerifierReceiptLedger(path)
            try:
                def retry(identity):
                    seen.append(dict(identity))
                    return {
                        "receipt_id": identity["receipt_id"],
                        "nonce": identity["nonce"],
                        "issued_at": identity["issued_at"],
                        "signature": "deterministic-test-signature",
                    }

                receipt = restarted.issue_once("operation-crash", {"scope": "scope/a"}, retry)
                self.assertEqual(seen[0], seen[1])
                self.assertEqual(receipt["receipt_id"], seen[0]["receipt_id"])
                self.assertEqual(receipt["nonce"], seen[0]["nonce"])
            finally:
                restarted.close()


    def test_real_process_kill_after_reservation_reuses_identity_after_restart(self):
        if not hasattr(os, "fork"):
            self.skipTest("fork-based crash test requires Linux")
        context = multiprocessing.get_context("fork")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.sqlite"
            started_receiver, started_sender = context.Pipe(duplex=False)
            release = context.Event()
            child = context.Process(
                target=_crash_during_receipt_signing,
                args=(str(path), started_sender, release),
            )
            child.start()
            started_sender.close()
            try:
                self.assertTrue(started_receiver.poll(5), "child did not publish reservation identity")
                identity_before_kill = started_receiver.recv()
                child.kill()
                child.join(timeout=5)
                self.assertFalse(child.is_alive())
                self.assertNotEqual(child.exitcode, 0)

                restarted = SQLiteVerifierReceiptLedger(path)
                try:
                    observed = []
                    receipt = restarted.issue_once(
                        "operation-process-crash",
                        {"scope": "scope/process-crash"},
                        lambda identity: observed.append(dict(identity)) or {
                            "receipt_id": identity["receipt_id"],
                            "nonce": identity["nonce"],
                            "issued_at": identity["issued_at"],
                            "signature": "recovered-deterministic-signature",
                        },
                        issued_at_provider=lambda: "2026-11-12T04:00:00+00:00",
                    )
                    self.assertEqual(observed, [identity_before_kill])
                    self.assertEqual(receipt["receipt_id"], identity_before_kill["receipt_id"])
                    self.assertEqual(receipt["nonce"], identity_before_kill["nonce"])
                    self.assertEqual(receipt["issued_at"], identity_before_kill["issued_at"])
                    self.assertEqual(
                        restarted._db.execute(
                            "SELECT COUNT(*) FROM issued_receipts WHERE receipt_json IS NOT NULL"
                        ).fetchone()[0],
                        1,
                    )
                finally:
                    restarted.close()
            finally:
                if child.is_alive():
                    child.kill()
                    child.join(timeout=5)
                release.set()
                started_receiver.close()

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
        self.assertRegex(first["receipt_id"], r"^[0-9a-f]{32}$")
        self.assertGreaterEqual(len(first["nonce"]), 32)

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

    def test_idempotency_namespace_is_bound_to_authenticated_writer(self):
        operation_id = "shared-operation-id"
        self.client.request("receipt.issue", self._request(), operation_id=operation_id)
        other_writer = "spiffe://zhouyi/e12a6-writer/other"
        other_path = self.root / "other-writer.sock"
        resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                other_writer, {"e12a6-writer"}, {self.scope},
            ),
        })
        other_server = E09VerifierUnixRPC(
            self.verifier,
            peer_resolver=resolver,
            socket_path=str(other_path),
            receipt_ledger=self.ledger,
            allowed_writer_workload_ids={other_writer},
        )
        other_server.start()
        try:
            deadline = time.monotonic() + 2
            while not other_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            other_client = UnixJSONRPCClient(other_path)
            with self.assertRaises(IPCRemoteError) as caught:
                other_client.request(
                    "receipt.issue", self._request(), operation_id=operation_id
                )
            self.assertEqual(caught.exception.code, "idempotency_conflict")
            self.assertEqual(len(self.verifier.calls), 1)
        finally:
            other_server.close()

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
