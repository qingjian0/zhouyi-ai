import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

from prototype.e12a6_unix_socket import (
    E12A6IPCError, E12A6UnixSocketServer,
)


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "SO_PEERCRED"),
                     "Linux SO_PEERCRED is required")
class TestE12A6UnixSocketServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.chmod(self.root, 0o700)
        self.path = self.root / "writer.sock"

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, payload, *, raw=None):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(self.path))
            client.sendall(raw if raw is not None else json.dumps(payload).encode() + b"\n")
            data = bytearray()
            while b"\n" not in data:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data.extend(chunk)
        return json.loads(bytes(data).split(b"\n", 1)[0])

    def test_dispatcher_receives_kernel_peer_credentials_not_json_claims(self):
        observed = []
        def dispatch(peer, request):
            observed.append((peer, request))
            return {"peer_uid": peer.uid, "peer_pid": peer.pid, "value": request["value"]}
        with E12A6UnixSocketServer(self.path, dispatch, allowed_uids={os.getuid()}) as server:
            result = self.request({"value": 7, "uid": 0, "pid": 1, "gid": 0})
            self.assertTrue(result["ok"])
            self.assertEqual(result["result"]["peer_uid"], os.getuid())
            self.assertEqual(result["result"]["peer_pid"], os.getpid())
            self.assertEqual(observed[0][1]["uid"], 0)
            self.assertNotEqual(observed[0][0].uid, observed[0][1]["uid"])
            self.assertEqual(Path(self.path).stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.path.exists())

    def test_rejects_non_allowlisted_uid_before_dispatch(self):
        calls = []
        with E12A6UnixSocketServer(self.path, lambda peer, req: calls.append(req) or {},
                                   allowed_uids={os.getuid() + 1}) as server:
            result = self.request({"operation": "submit"})
            self.assertFalse(result["ok"])
            self.assertEqual(calls, [])
            self.assertTrue(any("allowlisted" in item for item in server.errors))

    def test_rejects_duplicate_json_keys(self):
        with E12A6UnixSocketServer(self.path, lambda peer, req: {}, allowed_uids={os.getuid()}):
            result = self.request({}, raw=b'{"scope":"a","scope":"b"}\n')
            self.assertFalse(result["ok"])

    def test_rejects_malformed_json(self):
        with E12A6UnixSocketServer(self.path, lambda peer, req: {}, allowed_uids={os.getuid()}):
            result = self.request({}, raw=b'{"broken":}\n')
            self.assertFalse(result["ok"])

    def test_rejects_oversized_frame(self):
        with E12A6UnixSocketServer(self.path, lambda peer, req: {}, allowed_uids={os.getuid()},
                                   max_frame_bytes=64):
            result = self.request({}, raw=b'{"payload":"' + b"x" * 64 + b'"}\n')
            self.assertFalse(result["ok"])

    def test_rejects_non_object_root(self):
        with E12A6UnixSocketServer(self.path, lambda peer, req: {}, allowed_uids={os.getuid()}):
            result = self.request({}, raw=b'[]\n')
            self.assertFalse(result["ok"])

    def test_refuses_preexisting_socket_or_symlink_without_unlinking(self):
        self.path.write_text("sentinel")
        with self.assertRaises(E12A6IPCError):
            E12A6UnixSocketServer(self.path, lambda peer, req: {}, allowed_uids={os.getuid()}).start()
        self.assertEqual(self.path.read_text(), "sentinel")

    def test_refuses_insecure_parent_directory(self):
        os.chmod(self.root, 0o755)
        server = E12A6UnixSocketServer(self.path, lambda peer, req: {}, allowed_uids={os.getuid()})
        with self.assertRaises(E12A6IPCError):
            server.start()

    def test_response_must_be_json_object(self):
        with E12A6UnixSocketServer(self.path, lambda peer, req: "not-an-object",
                                   allowed_uids={os.getuid()}):
            result = self.request({})
            self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
