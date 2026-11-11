import unittest

from orchestrator.agents.execution_contract import (
    ApprovalBinding, ExecutionManifest, ExecutionRecord, ResourceLimits,
    manifest_digest, validate_approval,
)


class ExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.limits = ResourceLimits(
            cpu_cores=2, memory_mb=2048, process_count=32,
            wall_time_seconds=600, disk_mb=4096, max_output_bytes=1_000_000,
        )
        self.manifest = ExecutionManifest(
            experiment_id="exp-001", code_revision="a" * 40,
            dataset_digest="b" * 64, model_id="candidate",
            model_version="v1", seed=7, command_id="python-unittest",
            argv=("python", "-m", "unittest", "discover", "-s", "tests"),
            limits=self.limits, created_at="2026-11-11T03:00:00Z",
            patch_digest="c" * 64,
        )

    def test_manifest_digest_is_deterministic(self):
        self.assertEqual(manifest_digest(self.manifest), manifest_digest(self.manifest))

    def test_resource_limits_reject_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            ResourceLimits(1, 0, 2, 10, 10, 100)
        with self.assertRaisesRegex(ValueError, "allowed_hosts"):
            ResourceLimits(1, 512, 2, 10, 10, 100, "disabled", ("example.com",))

    def test_manifest_requires_full_commit_and_argument_array(self):
        with self.assertRaisesRegex(ValueError, "full"):
            ExecutionManifest(
                "exp", "abcdef1", "b" * 64, "m", "v", 0, "python",
                ("python",), self.limits, "2026-11-11T03:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "tuple"):
            ExecutionManifest(
                "exp", "a" * 40, "b" * 64, "m", "v", 0, "python",
                ["python"], self.limits, "2026-11-11T03:00:00Z",
            )

    def test_approval_is_bound_to_manifest_patch_and_branch(self):
        digest = manifest_digest(self.manifest)
        approval = ApprovalBinding(
            digest, "c" * 64, "feature/test", "reviewer",
            "2026-11-11T03:01:00Z",
        )
        validate_approval(self.manifest, approval,
                          current_patch_digest="c" * 64,
                          target_branch="feature/test")
        with self.assertRaisesRegex(ValueError, "target branch"):
            validate_approval(self.manifest, approval,
                              current_patch_digest="c" * 64,
                              target_branch="main")
        with self.assertRaisesRegex(ValueError, "patch digest"):
            validate_approval(self.manifest, approval,
                              current_patch_digest="d" * 64,
                              target_branch="feature/test")

    def test_manifest_change_invalidates_approval(self):
        approval = ApprovalBinding(
            manifest_digest(self.manifest), "c" * 64, "feature/test",
            "reviewer", "2026-11-11T03:01:00Z",
        )
        changed = ExecutionManifest(
            **{**self.manifest.__dict__, "seed": 8}
        )
        with self.assertRaisesRegex(ValueError, "manifest"):
            validate_approval(changed, approval,
                              current_patch_digest="c" * 64,
                              target_branch="feature/test")

    def test_execution_record_validates_observed_usage(self):
        record = ExecutionRecord(
            manifest_digest(self.manifest), "c" * 64, "runner-local",
            "completed", 0, "2026-11-11T03:02:00Z",
            "2026-11-11T03:03:00Z", 4.5, 512, 10, 1024, "d" * 64,
        )
        self.assertEqual(record.status, "completed")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            ExecutionRecord(
                manifest_digest(self.manifest), "c" * 64, "runner-local",
                "completed", 0, "2026-11-11T03:02:00Z",
                "2026-11-11T03:03:00Z", -1, 512, 10, 1024,
            )


if __name__ == "__main__":
    unittest.main()
