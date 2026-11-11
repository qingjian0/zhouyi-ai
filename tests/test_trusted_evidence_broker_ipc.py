import os
import tempfile
import threading
import unittest
from pathlib import Path

from prototype.trusted_evidence_broker_ipc import (
    BrokerIPCError,
    BrokerUnixServer,
    PrincipalPolicy,
    TrustedEvidenceBroker,
    request_snapshot,
)


@unittest.skipUnless(os.name == "posix" and Path("/proc/sys/kernel/ostype").exists(), "Linux SO_PEERCRED required")
class TrustedEvidenceBrokerIPCTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.socket_path = self.root / "run" / "broker.sock"
        self.database_path = self.root / "private" / "evidence.sqlite3"
        self.uid = os.getuid()
        self.broker = TrustedEvidenceBroker(
            self.database_path,
            principals_by_uid={
                self.uid: PrincipalPolicy(
                    principal_id="test-learner",
                    role="learner",
                    learner_track="track-a",
                    allowed_episodes=frozenset({"episode-a"}),
                )
            },
            cursor_secret=b"x" * 32,
        )
        self.server = BrokerUnixServer(self.socket_path, self.broker)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.broker.close()
        self.temp.cleanup()

    def test_kernel_peer_uid_authorizes_learner_snapshot(self):
        response = request_snapshot(self.socket_path, "episode-a")
        self.assertEqual(response["result"]["learner_track"], "track-a")
        self.assertEqual(response["result"]["episode_id"], "episode-a")
        self.assertTrue(response["result"]["cursor"])
        self.assertEqual(self.database_path.stat().st_mode & 0o777, 0o600)

    def test_episode_outside_capability_scope_fails_closed(self):
        with self.assertRaises(BrokerIPCError):
            request_snapshot(self.socket_path, "other-episode")

    def test_actor_role_and_track_are_not_client_authority(self):
        with self.assertRaises(BrokerIPCError):
            self.broker.dispatch(
                self.broker.principal_for_uid(self.uid),
                {
                    "protocol_version": "0.1",
                    "request_id": "forged",
                    "operation": "get_snapshot",
                    "payload": {"episode_id": "episode-a", "actor_role": "evaluator", "learner_track": "other"},
                },
            )

    def test_unknown_operation_is_denied(self):
        with self.assertRaises(BrokerIPCError):
            self.broker.dispatch(
                self.broker.principal_for_uid(self.uid),
                {
                    "protocol_version": "0.1",
                    "request_id": "raw",
                    "operation": "raw_events",
                    "payload": {"episode_id": "episode-a"},
                },
            )

    def test_unmapped_uid_is_denied(self):
        with self.assertRaises(BrokerIPCError):
            self.broker.principal_for_uid(self.uid + 100000)


if __name__ == "__main__":
    unittest.main()
