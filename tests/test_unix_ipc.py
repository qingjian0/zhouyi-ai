import json
import os
import socket
import struct
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from prototype.unix_ipc import (
    IPCRemoteError,
    IPCTransportError,
    IPC_PROTOCOL,
    StaticUnixPeerResolver,
    UnixJSONRPCClient,
    UnixJSONRPCServer,
    _recv_frame,
)


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED"), "Linux SO_PEERCRED is required")
class UnixJSONRPCTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.socket_path = Path(self.tmp.name) / "service.sock"
        self.resolver = StaticUnixPeerResolver({
            (os.getuid(), os.getgid()): (
                "spiffe://zhouyi/test-client", {"learner"}, {"scope/test"},
            ),
        })
        self.server = UnixJSONRPCServer(
            self.socket_path,
            peer_resolver=self.resolver,
            handlers={
                "test.echo": self._echo,
                "test.slow": self._slow,
            },
        )
        self.server.start()
        deadline = time.monotonic() + 2
        while not self.socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.socket_path.exists())
        self.client = UnixJSONRPCClient(self.socket_path)

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    @staticmethod
    def _echo(context, body):
        context.remaining_seconds()
        return {
            "workload_id": context.peer.workload_id,
            "roles": sorted(context.peer.roles),
            "scopes": sorted(context.peer.scopes),
            "uid": context.peer.uid,
            "pid": context.peer.pid,
            "body": body,
        }

    @staticmethod
    def _slow(context, body):
        time.sleep(0.05)
        context.remaining_seconds()
        return {"ok": True}

    def test_server_uses_kernel_peer_identity_not_json_claims(self):
        result = self.client.request(
            "test.echo",
            {"workload_id": "attacker-controlled", "roles": ["authorizer"]},
            operation_id="echo-1",
        )
        self.assertEqual(result["workload_id"], "spiffe://zhouyi/test-client")
        self.assertEqual(result["roles"], ["learner"])
        self.assertEqual(result["uid"], os.getuid())
        self.assertGreater(result["pid"], 0)
        self.assertEqual(result["body"]["workload_id"], "attacker-controlled")

    def test_unknown_operation_is_rejected_by_allowlist(self):
        with self.assertRaises(IPCRemoteError) as caught:
            self.client.request("database.execute_sql", {}, operation_id="unknown-1")
        self.assertEqual(caught.exception.code, "unknown_operation")

    def test_server_enforces_deadline_before_handler(self):
        with self.assertRaises(IPCRemoteError) as caught:
            self.client.request(
                "test.echo", {}, operation_id="deadline-1", deadline_ms=30_001,
            )
        self.assertEqual(caught.exception.code, "invalid_deadline")

    def test_duplicate_json_keys_are_rejected(self):
        request_id = str(uuid.uuid4())
        raw = (
            '{"protocol":"' + IPC_PROTOCOL + '","request_id":"' + request_id
            + '","operation_id":"dup-1","operation":"test.echo",'
            + '"operation":"database.execute_sql","deadline_ms":1000,"body":{}}'
        ).encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(2)
            conn.connect(str(self.socket_path))
            conn.sendall(struct.pack("!I", len(raw)) + raw)
            response = _recv_frame(conn, 4 * 1024 * 1024)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["body"]["code"], "invalid_request")

    def test_oversized_frame_is_rejected_before_body_read(self):
        small_path = Path(self.tmp.name) / "small.sock"
        server = UnixJSONRPCServer(
            small_path,
            peer_resolver=self.resolver,
            handlers={"test.echo": self._echo},
            max_frame_bytes=128,
        )
        server.start()
        try:
            deadline = time.monotonic() + 2
            while not small_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(2)
                conn.connect(str(small_path))
                conn.sendall(struct.pack("!I", 129))
                # Invalid oversized frames are closed without allocating or
                # attempting to return an error frame that may exceed the cap.
                with self.assertRaises(IPCTransportError):
                    _recv_frame(conn, 128)
        finally:
            server.close()

    def test_socket_mode_cannot_grant_world_access(self):
        with self.assertRaises(ValueError):
            UnixJSONRPCServer(
                Path(self.tmp.name) / "world.sock",
                peer_resolver=self.resolver,
                handlers={"test.echo": self._echo},
                socket_mode=0o666,
            )

    def test_server_refuses_group_or_world_writable_socket_directory(self):
        private_dir = Path(self.tmp.name) / "unsafe"
        private_dir.mkdir(mode=0o700)
        os.chmod(private_dir, 0o770)
        server = UnixJSONRPCServer(
            private_dir / "service.sock",
            peer_resolver=self.resolver,
            handlers={"test.echo": self._echo},
        )
        try:
            with self.assertRaises(IPCTransportError):
                server.start()
        finally:
            os.chmod(private_dir, 0o700)

    def test_unmapped_kernel_peer_is_denied(self):
        denied_path = Path(self.tmp.name) / "denied.sock"
        denied = UnixJSONRPCServer(
            denied_path,
            peer_resolver=StaticUnixPeerResolver({
                (os.getuid() + 1, os.getgid()): (
                    "spiffe://zhouyi/other", {"learner"}, {"scope/test"},
                ),
            }),
            handlers={"test.echo": self._echo},
        )
        denied.start()
        try:
            deadline = time.monotonic() + 2
            while not denied_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            client = UnixJSONRPCClient(denied_path)
            with self.assertRaises(IPCRemoteError) as caught:
                client.request("test.echo", {}, operation_id="denied-1")
            self.assertEqual(caught.exception.code, "peer_unauthorized")
        finally:
            denied.close()


if __name__ == "__main__":
    unittest.main()
