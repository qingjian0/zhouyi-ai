import hashlib
import json
import os
import socket
import stat
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from prototype.e09_authority_runtime import E09AuthorityRuntime, E09AuthorityRuntimeError
from prototype.e09_authority_services import E09AuthenticatedWorkload, StaticE09LearnerBindingResolver
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

    def runtime(self, uid=None, learner_binding_resolver=None, authenticator=None, uid_to_credential=None):
        uid = os.getuid() if uid is None else uid
        # Simulate a distinct service UID only for constructor policy validation.
        # The UDS tests still run as this process UID and do not claim OS isolation.
        with patch("prototype.e09_authority_runtime.os.geteuid", return_value=uid + 1):
            return E09AuthorityRuntime(
                database_path=self.db_path,
                socket_path=self.socket_path,
                authenticator=self.authenticator if authenticator is None else authenticator,
                signer=Signer(),
                domain_registry=self.registry,
                uid_to_credential={uid: "observer-cert"} if uid_to_credential is None else uid_to_credential,
                socket_gid=os.getgid(),
                learner_binding_resolver=learner_binding_resolver,
            )

    def test_same_uid_client_is_rejected_without_runtime_bypass(self):
        with self.assertRaisesRegex(
            E09AuthorityRuntimeError, "client UIDs must be distinct"
        ):
            E09AuthorityRuntime(
                database_path=self.db_path,
                socket_path=self.socket_path,
                authenticator=self.authenticator,
                signer=Signer(),
                domain_registry=self.registry,
                uid_to_credential={os.getuid(): "observer-cert"},
                socket_gid=os.getgid(),
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

    def test_uds_dispatches_authenticated_structure_and_revision_lineage(self):
        identities = {
            "observer-cert": E09AuthenticatedWorkload(
                workload_id="spiffe://runtime/observer", issuer_id="issuer:observer",
                roles=frozenset({"observer"}), scopes=frozenset({self.scope}),
                identity_provider="test-spiffe", authentication_method="mTLS",
                credential_fingerprint="1" * 64,
            ),
            "learner-cert": E09AuthenticatedWorkload(
                workload_id="spiffe://runtime/learner", issuer_id="issuer:learner",
                roles=frozenset({"learner"}), scopes=frozenset({self.scope}),
                identity_provider="test-spiffe", authentication_method="mTLS",
                credential_fingerprint="2" * 64,
            ),
            "evaluator-cert": E09AuthenticatedWorkload(
                workload_id="spiffe://runtime/evaluator", issuer_id="issuer:evaluator",
                roles=frozenset({"evaluator"}), scopes=frozenset({self.scope}),
                identity_provider="test-spiffe", authentication_method="mTLS",
                credential_fingerprint="3" * 64,
            ),
        }

        class MultiAuthenticator:
            def authenticate(self, credential):
                if credential not in identities:
                    raise ValueError("unknown credential")
                return identities[credential]

        runtime = self.runtime(
            uid=os.getuid(), authenticator=MultiAuthenticator(),
            uid_to_credential={os.getuid(): "learner-cert"},
        )
        with runtime:
            authority = runtime._authority
            episode = "ipc-structure-revision"
            observation_id = "obs-lineage"
            observation_event_id = f"{episode}:observation:{observation_id}"
            authority.append_observation(
                "observer-cert", episode_id=episode, event_id=observation_event_id,
                idempotency_key=observation_event_id,
                payload={"observation_id": observation_id, "query_id": observation_id,
                         "scope": self.scope, "split": "SUPPORT"},
            )
            prediction_id = "prediction-lineage"
            commit_event_id = f"{episode}:prediction:{prediction_id}"
            semantic_digest = hashlib.sha256(prediction_id.encode()).hexdigest()
            commit_receipt = authority.append_prediction_commit(
                "learner-cert", episode_id=episode, event_id=commit_event_id,
                idempotency_key=commit_event_id, causation_refs=[observation_event_id],
                payload={"prediction_id": prediction_id, "observation_id": observation_id,
                         "model_version": "model-v1", "learner_track": "track-a",
                         "decision_status": "PREDICT", "query_id": observation_id,
                         "scope": self.scope, "split": "SUPPORT",
                         "interop_commit_digest": semantic_digest},
            )
            reveal_event_id = f"{episode}:reveal:{prediction_id}"
            authority.append_evidence_reveal(
                "evaluator-cert", episode_id=episode, event_id=reveal_event_id,
                idempotency_key=reveal_event_id, causation_refs=[commit_event_id],
                payload={"prediction_id": prediction_id, "learner_track": "track-a",
                         "target_or_feedback": "yes", "query_id": observation_id,
                         "scope": self.scope, "split": "SUPPORT",
                         "commit_digest": semantic_digest,
                         "event_digest": commit_receipt.payload_digest},
            )

            def request(operation, event_id, payload, causation_refs=None):
                body = {
                    "operation": operation, "episode_id": episode, "event_id": event_id,
                    "idempotency_key": event_id, "payload": payload,
                }
                if causation_refs is not None:
                    body["causation_refs"] = causation_refs
                response = send_request(self.socket_path, body)
                self.assertTrue(response["ok"], response)
                self.assertEqual(response["result"]["event_id"], event_id)

            initial_id = f"{episode}:structure:v1"
            initial_payload = {
                "structure_id": "rules", "version_id": "v1", "kind": "rule_set",
                "definition": {}, "parent_version_ids": [], "support_evidence_ids": [],
                "learner_track": "track-a", "scope": self.scope,
            }
            request("append_structure_version", initial_id, initial_payload, [])

            next_id = f"{episode}:structure:v2"
            next_payload = {
                **initial_payload, "version_id": "v2",
                "parent_version_ids": ["v1"], "support_evidence_ids": [reveal_event_id],
            }
            request("append_structure_version", next_id, next_payload, [initial_id, reveal_event_id])

            revision_id = f"{episode}:revision:r1"
            request("append_revision", revision_id, {
                "revision_id": "r1", "operation": "INCREMENTAL_INDEX",
                "trigger_evidence_ids": [reveal_event_id], "before_version_ids": ["v1"],
                "after_version_ids": ["v2"], "learner_track": "track-a",
                "training_example_count": 1, "candidate_evaluations": 8,
                "scope": self.scope,
            }, [reveal_event_id, initial_id, next_id])
            events = runtime._store.replay_episode(episode)
            self.assertEqual(events[-1]["event_type"], "revision")
            self.assertEqual(events[-1]["payload"]["domain_id"], "domain:runtime")

    def test_uds_observation_uses_server_resolved_learner_assignment(self):
        resolver = StaticE09LearnerBindingResolver({
            ("ipc-episode", self.scope, "learner-track-a"): "spiffe://runtime/learner-a",
        })
        request = self.observation_request()
        request["payload"]["learner_track"] = "learner-track-a"
        with self.runtime(learner_binding_resolver=resolver) as runtime:
            response = send_request(self.socket_path, request)
            self.assertTrue(response["ok"])
            event = runtime._store.replay_episode("ipc-episode")[0]
            self.assertEqual(event["payload"]["learner_track"], "learner-track-a")
            self.assertEqual(
                event["payload"]["learner_workload_id"], "spiffe://runtime/learner-a"
            )
            self.assertEqual(event["payload_schema"], "observation@5")

    def test_uds_observation_input_upload_uses_server_side_track_binding(self):
        resolver = StaticE09LearnerBindingResolver({
            ("ipc-episode", self.scope, "learner-track-a"): "spiffe://runtime/learner-a",
        })
        request = {
            "operation": "put_observation_input",
            "episode_id": "ipc-episode",
            "scope": self.scope,
            "learner_track": "learner-track-a",
            "feature_schema_version": "e09-features-v1",
            "payload": {"features": [1, 2, 3]},
        }
        with self.runtime(learner_binding_resolver=resolver) as runtime:
            response = send_request(self.socket_path, request)
            self.assertTrue(response["ok"])
            payload_ref = response["result"]["payload_ref"]
            self.assertEqual(
                runtime._store.get_payload(payload_ref), {"features": [1, 2, 3]}
            )
            forged = {**request, "learner_workload_id": "spiffe://attacker/learner"}
            rejected = send_request(self.socket_path, forged)
            self.assertFalse(rejected["ok"])

    def test_uds_observation_rejects_unassigned_learner_track(self):
        resolver = StaticE09LearnerBindingResolver({})
        request = self.observation_request()
        request["payload"]["learner_track"] = "not-assigned"
        with self.runtime(learner_binding_resolver=resolver) as runtime:
            response = send_request(self.socket_path, request)
            self.assertFalse(response["ok"])
            self.assertEqual(runtime._store.replay_episode("ipc-episode"), [])

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
