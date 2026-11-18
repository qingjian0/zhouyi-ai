import json
import os
import socket
import stat
import tempfile
import unittest
from pathlib import Path

from prototype.e09_authority_runtime import E09AuthorityRuntime, E09AuthorityRuntimeError
from prototype.e09_authority_services import E09AuthenticatedWorkload
from prototype.e09_domain_registry import E09DomainBinding, StaticE09DomainRegistry


class Authenticator:
    def __init__(self, identity):
        self.identity = identity
    def authenticate(self, credential):
        if credential != "observer-cert":
            raise ValueError("unknown credential")
        return self.identity


class Signer:
    def sign(self, issuer_id, message):
        return "unused-test-signature"


def send_request(path, request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(str(path))
        client.sendall(json.dumps(request, separators=(",", ":")).encode() + b"\n")
        data = bytearray()
        while b"\n" not in data:
            data.extend(client.recv(65536))
        return json.loads(bytes(data).split(b"\n", 1)[0])


class E09AuthorityRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db_dir = root / "private-db"
        self.socket_dir = root / "client-ipc"
        self.db_dir.mkdir()
        self.socket_dir.mkdir()
        os.chmod(self.db_dir, 0o700)
        os.chmod(self.socket_dir, 0o710)
        self.scope = "world/runtime"
        identity = E09AuthenticatedWorkload(
            workload_id="spiffe://runtime/observer",
            issuer_id="issuer:runtime-observer",
            roles=frozenset({"observer"}),
            scopes=frozenset({self.scope}),
            identity_provider="test-spiffe",
            authentication_method="mTLS",
            credential_fingerprint="a" * 64,
        )
        self.authenticator = Authenticator(identity)
        self.registry = StaticE09DomainRegistry({
            self.scope: E09DomainBinding("domain:runtime", "family:runtime",
                                         "registry:runtime", "v1"),
        })
        self.db_path = self.db_dir / "e09.sqlite"
        self.socket_path = self.socket_dir / "authority.sock"

    def tearDown(self):
        self.tmp.cleanup()

    def runtime(self, uid=None):
        uid = os.getuid() if uid is None else uid
        return E09AuthorityRuntime(
            database_path=self.db_path,
            socket_path=self.socket_path,
            authenticator=self.authenticator,
            signer=Signer(),
            domain_registry=self.registry,
            uid_to_credential={uid: "observer-cert"},
            socket_gid=os.getgid(),
            test_only_allow_same_uid=(uid == os.getuid()),
        )

    def observation_request(self):
        return {
            "operation": "append_observation",
            "episode_id": "ipc-episode",
            "event_id": "ipc-observation-1",
            "idempotency_key": "ipc-observation-1",
            "payload": {
                "observation_id": "obs-1", "query_id": "query-1",
                "scope": self.scope, "split": "SUPPORT",
            },
        }

    def test_private_database_and_peer_authenticated_socket(self):
        with self.runtime() as runtime:
            db_info = self.db_path.stat()
            socket_info = self.socket_path.stat()
            self.assertEqual(stat.S_IMODE(self.db_dir.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(db_info.st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.socket_dir.stat().st_mode), 0o710)
            self.assertEqual(stat.S_IMODE(socket_info.st_mode), 0o660)
            self.assertEqual(socket_info.st_gid, os.getgid())

            response = send_request(self.socket_path, self.observation_request())
            self.assertTrue(response["ok"])
            self.assertEqual(response["result"]["event_id"], "ipc-observation-1")

            # Caller-supplied identity/role claims are not part of the IPC schema.
            spoofed = {**self.observation_request(), "actor_role": "evaluator",
                       "credential": "evaluator-cert", "uid": 0}
            rejected = send_request(self.socket_path, spoofed)
            self.assertFalse(rejected["ok"])
            events = runtime._store.replay_episode("ipc-episode")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["actor_role"], "observer")
            self.assertEqual(events[0]["payload"]["domain_id"], "domain:runtime")

    def test_unallowlisted_peer_uid_is_rejected(self):
        with self.runtime(uid=os.getuid() + 100000) as runtime:
            response = send_request(self.socket_path, self.observation_request())
            self.assertFalse(response["ok"])
            self.assertEqual(runtime._store.replay_episode("ipc-episode"), [])

    def test_client_cannot_share_database_owner_uid_in_production_mode(self):
        with self.assertRaisesRegex(E09AuthorityRuntimeError, "client UIDs must be distinct"):
            E09AuthorityRuntime(
                database_path=self.db_path, socket_path=self.socket_path,
                authenticator=self.authenticator, signer=Signer(),
                domain_registry=self.registry,
                uid_to_credential={os.getuid(): "observer-cert"},
                socket_gid=os.getgid(),
            )

    def test_database_directory_with_group_or_world_access_is_rejected(self):
        os.chmod(self.db_dir, 0o755)
        with self.assertRaisesRegex(E09AuthorityRuntimeError, "mode 0700"):
            self.runtime().start()


if __name__ == "__main__":
    unittest.main()
