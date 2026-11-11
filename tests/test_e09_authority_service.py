from datetime import datetime, timedelta, timezone

import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.e09_authority_service import (
    AuthenticatedPrincipal,
    E09BranchMergeAuthority,
    E09AuthorityError,
)
from prototype.e09_ed25519_keyring import E09Ed25519IssuerKeyring
from prototype.e09_e12a6_evidence_bridge import branch_merge_authorization_signing_bytes
from prototype.shared_evidence_protocol import SQLiteEvidenceStore


def _principal(roles=frozenset({"branch_merge_authorizer"})):
    return AuthenticatedPrincipal("workload://authority-1", "issuer-A", roles, "credential-7")


class E09AuthorityServiceTests(unittest.TestCase):
    def test_authority_authenticates_principal_and_signs_complete_v2_event(self):
        import tempfile\n        from pathlib import Path\n        with tempfile.TemporaryDirectory() as tmp:\n            store = SQLiteEvidenceStore(Path(tmp) / "authority.db")
    key = Ed25519PrivateKey.generate()
    now = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
    authority = E09BranchMergeAuthority(
        store, issuer_id="issuer-A", signing_key=key,
        authenticator=lambda credential: _principal() if credential == "valid" else None,
        clock=lambda: now,
    )
    receipt = authority.issue(
        "valid", episode_id="episode-1", scope="research",
        parent_state_ref="state-10", branch_ids=["b-2", "b-1"],
        evidence_refs=["reveal-1"], ttl=timedelta(minutes=1),
        authorization_id="auth-1",
    )
    event = store.replay_episode("episode-1")[0]
    assert receipt.sequence_no == 1
    assert event["payload"]["authorization_sequence"] == event["sequence_no"]
    assert event["payload"]["branch_ids"] == ["b-1", "b-2"]
    assert event["integrity_metadata"]["authority_subject"] == "workload://authority-1"
    keyring = E09Ed25519IssuerKeyring({"issuer-A": authority.signing_public_key})
    assert keyring.verify(
        "issuer-A", "Ed25519",
        branch_merge_authorization_signing_bytes(event),
        event["payload"]["signature"],
    )
    store.close()


    def test_authority_rejects_missing_role_and_untrusted_principal(self):
    store = SQLiteEvidenceStore(tmp_path / "denied.db")
    key = Ed25519PrivateKey.generate()
    authority = E09BranchMergeAuthority(
        store, issuer_id="issuer-A", signing_key=key,
        authenticator=lambda _: _principal(frozenset({"reader"})),
    )
    with pytest.raises(E09AuthorityError):
        authority.issue(
            "credential", episode_id="episode-2", scope="s",
            parent_state_ref="p", branch_ids=["b"], evidence_refs=["r"],
        )
    assert store.replay_episode("episode-2") == []
    store.close()


    def test_authority_rejects_bad_clock_and_excessive_ttl(self):
    store = SQLiteEvidenceStore(tmp_path / "clock.db")
    key = Ed25519PrivateKey.generate()
    authority = E09BranchMergeAuthority(
        store, issuer_id="issuer-A", signing_key=key,
        authenticator=lambda _: _principal(), clock=lambda: datetime.now(),
    )
    with pytest.raises(E09AuthorityError):
        authority.issue(
            "credential", episode_id="episode-3", scope="s",
            parent_state_ref="p", branch_ids=["b"], evidence_refs=["r"],
        )
    store.close()
