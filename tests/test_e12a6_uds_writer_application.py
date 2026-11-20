import unittest
from types import SimpleNamespace
from unittest.mock import patch

from prototype.e12a6_unix_socket import E12A6IPCError, E12A6PeerCredentials
from prototype.e12a6_uds_writer_application import (
    E12A6UDSProtocolError,
    E12A6UDSWriterApplication,
    decode_submit_request,
)


def _valid_request():
    return {
        "version": 1,
        "operation": "submit_authorized_merge_candidate",
        "scope": "world/test",
        "grammar_version": "csg-gcr-writer-v1",
        "proposals": [{
            "proposal": {
                "proposal_id": "p1", "parent_state_ref": "parent",
                "branch_id": "left", "bindings": [], "evidence_refs": ["ev1"],
            },
            "hyperedge": {
                "edge_id": "p1", "parent_state_ref": "parent",
                "branch_id": "left", "relation_type": "supports",
                "roles": [], "evidence_refs": ["ev1"],
            },
            "variables": [],
        }],
        "base_state": {"node:a": {"value": 1}},
        "branch_snapshots": [],
        "receipt": {"receipt_id": "receipt", "signature": "opaque"},
    }


class _FakeService:
    def __init__(self):
        self.calls = []

    def submit_authorized_merge_candidate(self, credential, **kwargs):
        self.calls.append((credential, kwargs))
        return SimpleNamespace(
            authorization_receipt_id="receipt-id",
            submitter_workload_id="workload-from-authenticator",
            proposal_ids=("p1", "p2"),
            lifecycle_receipt=SimpleNamespace(replayed=False),
        )


class E12A6UDSWriterApplicationTests(unittest.TestCase):
    def test_decodes_versioned_typed_request(self):
        decoded = decode_submit_request(_valid_request())
        self.assertEqual(decoded["scope"], "world/test")
        self.assertEqual(decoded["proposals"][0].proposal.proposal_id, "p1")
        self.assertEqual(decoded["constraints"].max_states, 10_000)
        self.assertEqual(decoded["receipt"]["signature"], "opaque")

    def test_rejects_identity_claims_and_unknown_root_fields(self):
        request = _valid_request()
        request["workload_id"] = "attacker"
        with self.assertRaises(E12A6UDSProtocolError):
            decode_submit_request(request)

    def test_rejects_unknown_nested_proposal_fields(self):
        request = _valid_request()
        request["proposals"][0]["proposal"]["credential_fingerprint"] = "f" * 64
        with self.assertRaises(E12A6UDSProtocolError):
            decode_submit_request(request)

    def test_rejects_unsupported_protocol_version(self):
        request = _valid_request()
        request["version"] = 2
        with self.assertRaises(E12A6UDSProtocolError):
            decode_submit_request(request)

    def test_rejects_duplicate_selected_ids(self):
        request = _valid_request()
        request["selected_proposal_ids"] = ["p1", "p1"]
        with self.assertRaises(E12A6UDSProtocolError):
            decode_submit_request(request)

    def test_enforces_aggregate_json_complexity_budget(self):
        request = _valid_request()
        request["base_state"] = {"bulk": [0] * 50_100}
        with self.assertRaises(E12A6UDSProtocolError):
            decode_submit_request(request)

    def test_dispatch_uses_only_fixed_kernel_uid_gid_binding(self):
        app = E12A6UDSWriterApplication.__new__(E12A6UDSWriterApplication)
        service = _FakeService()
        credential = object()
        app._mapping = {(1201, 1201): credential}
        app._runtime = SimpleNamespace(service=service)
        with patch("prototype.e12a6_uds_writer_application.decode_submit_request",
                   return_value={"scope": "world/test"}):
            response = app._dispatch(
                E12A6PeerCredentials(pid=99, uid=1201, gid=1201),
                {"workload_id": "forged", "roles": ["admin"]},
            )
        self.assertIs(service.calls[0][0], credential)
        self.assertEqual(response["submitter_workload_id"], "workload-from-authenticator")
        self.assertEqual(response["proposal_ids"], ["p1", "p2"])

    def test_unmapped_kernel_peer_is_rejected_before_service_call(self):
        app = E12A6UDSWriterApplication.__new__(E12A6UDSWriterApplication)
        service = _FakeService()
        app._mapping = {(1201, 1201): object()}
        app._runtime = SimpleNamespace(service=service)
        with self.assertRaises(E12A6IPCError):
            app._dispatch(E12A6PeerCredentials(pid=100, uid=1202, gid=1202), {})
        self.assertEqual(service.calls, [])

    def test_shutdown_keeps_writer_runtime_open_until_server_drains(self):
        class Server:
            def __init__(self):
                self.fail = True
                self.calls = 0

            def close(self):
                self.calls += 1
                if self.fail:
                    raise E12A6IPCError("dispatcher still active")

        class Runtime:
            def __init__(self):
                self.closed = 0

            def close(self):
                self.closed += 1

        app = E12A6UDSWriterApplication.__new__(E12A6UDSWriterApplication)
        server, runtime = Server(), Runtime()
        app._server, app._runtime = server, runtime
        with self.assertRaises(E12A6IPCError):
            app.close()
        self.assertIs(app._server, server)
        self.assertIs(app._runtime, runtime)
        self.assertEqual(runtime.closed, 0)
        server.fail = False
        app.close()
        self.assertIsNone(app._server)
        self.assertIsNone(app._runtime)
        self.assertEqual(runtime.closed, 1)


if __name__ == "__main__":
    unittest.main()
