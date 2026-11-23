import json
import os
import socket
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry
from prototype.e09_verifier_runtime import E09VerifierRuntime, E09VerifierRuntimeError
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


class Signer:
    def sign(self, issuer_id, message):
        return "unused-test-signature"


class VerifierRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.snapshot_dir = root / "authority-snapshot"
        self.socket_dir = root / "verifier-ipc"
        self.snapshot_dir.mkdir()
        self.socket_dir.mkdir()
        os.chmod(self.snapshot_dir, 0o750)
        os.chmod(self.socket_dir, 0o710)
        self.snapshot = self.snapshot_dir / "e09-snapshot.sqlite"
        store = SQLiteEvidenceStore(self.snapshot)
        store.close()
        os.chmod(self.snapshot, 0o440)
        self.socket = self.socket_dir / "verifier.sock"
        self.scope = "world/verifier-runtime"
        self.registry = StaticE09DomainRegistry({
            self.scope: E09DomainBinding(
                "domain:verifier", "family:verifier", "registry:verifier", "v1"
            )
        })

    def tearDown(self):
        self.tmp.cleanup()

    def runtime(self, *, uid=None, scopes=None):
        # The fixture models a distinct verifier workload UID. Tests that need
        # same-process UDS clients explicitly isolate the filesystem gate below.
        uid = os.getuid() + 100000 if uid is None else uid
        return E09VerifierRuntime(
            snapshot_database_path=self.snapshot,
            socket_path=self.socket,
            signature_verifier=lambda issuer, algorithm, message, signature: True,
            verifier_id="verifier-test",
            receipt_signer=Signer(),
            domain_registry=self.registry,
            uid_to_scopes={uid: frozenset({self.scope} if scopes is None else scopes)},
            snapshot_gid=os.getegid(),
            socket_gid=os.getgid(),
        )

    def request(self, scope=None):
        return {
            "operation": "issue_verification_receipt@1",
            "episode_id": "episode",
            "authorization_ref": "authorization",
            "parent_state_ref": "parent",
            "branch_ids": ["branch-a"],
            "scope": self.scope if scope is None else scope,
            "learner_track": "learner-a",
        }

    def send(self, request):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(self.socket))
            client.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            data = bytearray()
            while b"\n" not in data:
                data.extend(client.recv(65536))
            return json.loads(bytes(data).split(b"\n", 1)[0])

    def test_snapshot_is_opened_read_only_and_peer_scope_is_enforced(self):
        runtime = self.runtime()
        runtime._uid_to_scopes = {os.getuid(): frozenset({self.scope})}
        # This test isolates SQLite read-only and scope behavior. The dedicated
        # owner-permission tests exercise the real filesystem gate separately.
        with patch.object(runtime, "_check_snapshot_permissions"):
            runtime.start()
        try:
            self.assertIsInstance(runtime._store, SQLiteEvidenceStore)
            with self.assertRaises(Exception):
                runtime._store._db.execute("CREATE TABLE forbidden_write(id INTEGER)")
            denied = self.send(self.request(scope="world/attacker"))
            self.assertFalse(denied["ok"])
            allowed_scope_but_missing_authorization = self.send(self.request())
            self.assertFalse(allowed_scope_but_missing_authorization["ok"])
            self.assertEqual(
                runtime._store._db.execute("PRAGMA query_only").fetchone()[0], 1
            )
        finally:
            runtime.close()

    def test_snapshot_owned_by_verifier_uid_is_rejected(self):
        with self.assertRaisesRegex(
            E09VerifierRuntimeError, "must not be owned by the Verifier UID"
        ):
            self.runtime().start()

    def test_same_uid_client_is_rejected_at_configuration(self):
        with self.assertRaisesRegex(
            E09VerifierRuntimeError, "distinct from the verifier"
        ):
            self.runtime(uid=os.getuid())

    def test_snapshot_with_group_write_permission_is_rejected(self):
        os.chmod(self.snapshot, 0o460)
        with self.assertRaises(E09VerifierRuntimeError):
            self.runtime().start()

    def test_unallowlisted_kernel_uid_is_rejected(self):
        # Isolate the transport test from snapshot ownership validation so the
        # request reaches SO_PEERCRED; the real owner check has its own test above.
        runtime = self.runtime(uid=os.getuid() + 100000)
        with patch.object(runtime, "_check_snapshot_permissions"):
            with runtime:
                denied = self.send(self.request())
                self.assertFalse(denied["ok"])
                self.assertEqual(denied.get("error"), "request_rejected")


if __name__ == "__main__":
    unittest.main()
