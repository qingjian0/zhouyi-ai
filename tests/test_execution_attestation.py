import unittest

from orchestrator.agents.execution_contract import ExecutionManifest, ResourceLimits
from orchestrator.agents.execution_attestation import (
    SandboxAttestation, SignedSandboxAttestation, sign_attestation,
    verify_attestation,
)


class SandboxAttestationTests(unittest.TestCase):
    def setUp(self):
        self.key = b"supervisor-test-key-material-32-bytes!!"
        self.controls = (
            "namespace:user", "namespace:pid", "namespace:mount",
            "namespace:network", "cgroup:v2", "seccomp:enforcing",
            "lsm:enforcing", "identity:non-root", "filesystem:root-read-only",
            "network:isolated", "resources:enforced", "process-tree:kill",
            "output:quota", "image:immutable",
        )
        limits = ResourceLimits(2, 2048, 32, 600, 4096, 1_000_000)
        self.manifest = ExecutionManifest(
            "exp-001", "a" * 40, "b" * 64, "candidate", "v1", 7,
            "python-unittest", ("python", "-m", "unittest"), limits,
            "2026-11-11T03:00:00Z", "c" * 64,
        )
        self.attestation = SandboxAttestation(
            1, "supervisor-v1", "run-001",
            "0" * 64, "c" * 64, "feature/test", "runner-01",
            "supervisor-01", "sha256:" + "d" * 64, "e" * 64,
            self.controls, "2026-11-11T03:01:00Z", "2026-11-11T03:03:00Z",
        )
        from orchestrator.agents.execution_contract import manifest_digest
        self.attestation = SandboxAttestation(
            **{**self.attestation.__dict__, "manifest_digest": manifest_digest(self.manifest)}
        )
        self.signed = sign_attestation(self.attestation, self.key)

    def verify(self, **overrides):
        args = {
            "expected_execution_id": "run-001",
            "expected_target_branch": "feature/test",
            "expected_runner_id": "runner-01",
            "expected_image_digest": "sha256:" + "d" * 64,
            "expected_challenge_nonce": "e" * 64,
            "now": "2026-11-11T03:02:00Z",
            "expected_key_id": "supervisor-v1",
        }
        args.update(overrides)
        return verify_attestation(self.signed, self.key, self.manifest, **args)

    def test_valid_attestation_is_accepted(self):
        self.assertEqual(self.verify(), self.attestation)

    def test_signature_tampering_is_rejected(self):
        tampered = SignedSandboxAttestation(self.attestation, "f" * 64)
        with self.assertRaisesRegex(ValueError, "signature"):
            verify_attestation(
                tampered, self.key, self.manifest,
                expected_execution_id="run-001",
                expected_target_branch="feature/test",
                expected_runner_id="runner-01",
                expected_image_digest="sha256:" + "d" * 64,
                expected_challenge_nonce="e" * 64,
                now="2026-11-11T03:02:00Z",
            )

    def test_manifest_patch_branch_runner_image_and_nonce_are_bound(self):
        from orchestrator.agents.execution_contract import manifest_digest
        other_manifest = ExecutionManifest(
            **{**self.manifest.__dict__, "seed": 8}
        )
        with self.assertRaisesRegex(ValueError, "manifest"):
            verify_attestation(
                self.signed, self.key, other_manifest,
                expected_execution_id="run-001",
                expected_target_branch="feature/test",
                expected_runner_id="runner-01",
                expected_image_digest="sha256:" + "d" * 64,
                expected_challenge_nonce="e" * 64,
                now="2026-11-11T03:02:00Z",
            )
        for field, value, message in (
            ("expected_target_branch", "main", "target branch"),
            ("expected_runner_id", "runner-02", "runner_id"),
            ("expected_image_digest", "sha256:" + "f" * 64, "image digest"),
            ("expected_challenge_nonce", "a" * 64, "challenge nonce"),
            ("expected_execution_id", "run-002", "execution_id"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, message):
                    self.verify(**{field: value})

    def test_expired_future_and_overlong_attestations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "expired"):
            self.verify(now="2026-11-11T03:04:00Z")
        with self.assertRaisesRegex(ValueError, "not yet valid"):
            self.verify(now="2026-11-11T02:59:00Z", clock_skew_seconds=0)
        with self.assertRaisesRegex(ValueError, "lifetime"):
            self.verify(max_lifetime_seconds=30)

    def test_key_id_and_key_material_are_checked(self):
        with self.assertRaisesRegex(ValueError, "key_id"):
            self.verify(expected_key_id="rotated-key")
        with self.assertRaisesRegex(ValueError, "32 bytes"):
            sign_attestation(self.attestation, b"short")

    def test_missing_or_unknown_controls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing required controls"):
            SandboxAttestation(
                **{**self.attestation.__dict__,
                   "verified_controls": self.controls[:-1]}
            )
        with self.assertRaisesRegex(ValueError, "unknown control"):
            SandboxAttestation(
                **{**self.attestation.__dict__,
                   "verified_controls": self.controls + ("made-up:control",)}
            )

    def test_invalid_time_order_and_nonce_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "later"):
            SandboxAttestation(
                **{**self.attestation.__dict__,
                   "expires_at": self.attestation.issued_at}
            )
        with self.assertRaisesRegex(ValueError, "challenge_nonce"):
            SandboxAttestation(
                **{**self.attestation.__dict__, "challenge_nonce": "short"}
            )

    def test_signed_wrapper_rejects_malformed_signature(self):
        with self.assertRaisesRegex(ValueError, "signature"):
            SignedSandboxAttestation(self.attestation, "not-a-signature")

    def test_schema_version_rejects_boolean(self):
        with self.assertRaisesRegex(ValueError, "schema_version"):
            SandboxAttestation(
                **{**self.attestation.__dict__, "schema_version": True}
            )


if __name__ == "__main__":
    unittest.main()
