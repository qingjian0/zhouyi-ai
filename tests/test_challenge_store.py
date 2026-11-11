import tempfile
import unittest
from pathlib import Path

from orchestrator.agents.execution_attestation import SandboxAttestation, sign_attestation
from orchestrator.agents.execution_contract import ExecutionManifest, ResourceLimits, manifest_digest
from orchestrator.agents.challenge_store import ExecutionChallengeStore


class ExecutionChallengeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "challenges.sqlite"
        self.key = b"challenge-store-test-key-material-32-bytes"
        self.manifest = ExecutionManifest(
            "exp-001", "a" * 40, "b" * 64, "candidate", "v1", 7,
            "python-unittest", ("python", "-m", "unittest"),
            ResourceLimits(2, 2048, 32, 600, 4096, 1_000_000),
            "2026-11-11T03:00:00Z", "c" * 64,
        )
        self.store = ExecutionChallengeStore(self.path, nonce_factory=lambda: "e" * 64)
        self.challenge = self.store.issue(
            self.manifest, execution_id="run-001",
            target_branch="feature/test", runner_id="runner-01",
            image_digest="sha256:" + "d" * 64,
            now="2026-11-11T03:00:00Z", ttl_seconds=180,
        )

    def tearDown(self):
        self.temp.cleanup()

    def make_signed(self, **overrides):
        values = {
            "schema_version": 1,
            "key_id": "supervisor-v1",
            "execution_id": self.challenge.execution_id,
            "manifest_digest": manifest_digest(self.manifest),
            "patch_digest": self.manifest.patch_digest,
            "target_branch": self.challenge.target_branch,
            "runner_id": self.challenge.runner_id,
            "supervisor_id": "supervisor-01",
            "image_digest": self.challenge.image_digest,
            "challenge_nonce": self.challenge.nonce,
            "verified_controls": (
                "namespace:user", "namespace:pid", "namespace:mount",
                "namespace:network", "cgroup:v2", "seccomp:enforcing",
                "lsm:enforcing", "identity:non-root", "filesystem:root-read-only",
                "network:isolated", "resources:enforced", "process-tree:kill",
                "output:quota", "image:immutable",
            ),
            "issued_at": "2026-11-11T03:00:30Z",
            "expires_at": "2026-11-11T03:02:30Z",
        }
        values.update(overrides)
        return sign_attestation(SandboxAttestation(**values), self.key)

    def verify(self, store=None, signed=None, challenge=None, **kwargs):
        return (store or self.store).verify_and_consume(
            signed or self.make_signed(), self.key, self.manifest,
            challenge or self.challenge, now="2026-11-11T03:01:00Z",
            expected_key_id="supervisor-v1", **kwargs,
        )

    def test_valid_attestation_consumes_challenge(self):
        self.assertEqual(self.verify().execution_id, "run-001")
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            self.verify()

    def test_consumption_survives_store_reopen(self):
        self.verify()
        reopened = ExecutionChallengeStore(self.path)
        with self.assertRaisesRegex(ValueError, "already been consumed"):
            self.verify(store=reopened)

    def test_invalid_signature_does_not_consume_challenge(self):
        signed = self.make_signed()
        from orchestrator.agents.execution_attestation import SignedSandboxAttestation
        tampered = SignedSandboxAttestation(signed.attestation, "f" * 64)
        with self.assertRaisesRegex(ValueError, "signature"):
            self.verify(signed=tampered)
        self.assertEqual(self.verify().execution_id, "run-001")

    def test_manifest_or_challenge_binding_mismatch_is_rejected(self):
        from dataclasses import replace
        changed = replace(self.challenge, target_branch="main")
        with self.assertRaisesRegex(ValueError, "target branch"):
            self.verify(challenge=changed)
        changed_manifest = ExecutionManifest(
            **{**self.manifest.__dict__, "seed": 8}
        )
        with self.assertRaisesRegex(ValueError, "manifest"):
            self.store.verify_and_consume(
                self.make_signed(), self.key, changed_manifest,
                self.challenge, now="2026-11-11T03:01:00Z",
            )

    def test_expired_challenge_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            self.store.verify_and_consume(
                self.make_signed(), self.key, self.manifest, self.challenge,
                now="2026-11-11T03:04:00Z",
            )

    def test_attestation_must_fit_challenge_window(self):
        signed = self.make_signed(expires_at="2026-11-11T03:04:00Z")
        with self.assertRaisesRegex(ValueError, "challenge expiry"):
            self.verify(signed=signed)

    def test_duplicate_nonce_issue_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "collision"):
            self.store.issue(
                self.manifest, execution_id="run-002",
                target_branch="feature/test", runner_id="runner-01",
                image_digest="sha256:" + "d" * 64,
                now="2026-11-11T03:00:00Z",
            )

    def test_invalid_ttl_and_nonce_factory_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "ttl_seconds"):
            self.store.issue(
                self.manifest, execution_id="run-002",
                target_branch="feature/test", runner_id="runner-01",
                image_digest="sha256:" + "d" * 64, ttl_seconds=301,
            )
        bad = ExecutionChallengeStore(
            Path(self.temp.name) / "bad.sqlite", nonce_factory=lambda: "bad"
        )
        with self.assertRaisesRegex(ValueError, "nonce_factory"):
            bad.issue(
                self.manifest, execution_id="run-003",
                target_branch="feature/test", runner_id="runner-01",
                image_digest="sha256:" + "d" * 64,
            )


if __name__ == "__main__":
    unittest.main()
