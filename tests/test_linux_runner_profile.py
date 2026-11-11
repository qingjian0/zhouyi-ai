import unittest

from orchestrator.agents.linux_runner_profile import (
    CapabilityReport, LinuxSandboxProfile, evaluate_linux_profile,
)


class LinuxRunnerProfileTests(unittest.TestCase):
    def report(self, **overrides):
        values = {
            "platform": "linux",
            "kernel_release": "6.8.0",
            "namespaces": ("user", "pid", "mount", "network"),
            "cgroup_mode": "v2",
            "seccomp_enforcing": True,
            "lsm_enforcing": True,
            "non_root_identity": True,
            "read_only_root": True,
            "network_isolated": True,
            "resource_limits_enforced": True,
            "process_tree_kill": True,
            "output_quota_enforced": True,
            "immutable_image_digest": "sha256:" + "a" * 64,
            "probe_id": "probe-01",
            "observed_at": "2026-11-11T03:00:00Z",
        }
        values.update(overrides)
        return CapabilityReport(**values)

    def test_complete_fresh_report_is_ready(self):
        result = evaluate_linux_profile(
            self.report(), now="2026-11-11T03:01:00Z"
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.missing_capabilities, ())

    def test_missing_capabilities_fail_closed(self):
        result = evaluate_linux_profile(
            self.report(seccomp_enforcing=False, network_isolated=False,
                        namespaces=("user", "pid")),
            now="2026-11-11T03:01:00Z",
        )
        self.assertFalse(result.ready)
        self.assertEqual(
            result.missing_capabilities,
            ("namespace:mount", "namespace:network", "seccomp", "network_isolated"),
        )

    def test_stale_and_future_reports_are_blocked(self):
        stale = evaluate_linux_profile(
            self.report(), now="2026-11-11T04:00:00Z"
        )
        future = evaluate_linux_profile(
            self.report(), now="2026-11-11T02:00:00Z"
        )
        self.assertIn("fresh_capability_report", stale.missing_capabilities)
        self.assertIn("fresh_capability_report", future.missing_capabilities)

    def test_non_linux_platform_is_blocked(self):
        result = evaluate_linux_profile(
            self.report(platform="darwin"), now="2026-11-11T03:01:00Z"
        )
        self.assertEqual(result.missing_capabilities, ("platform:linux",))

    def test_profile_can_explicitly_relax_controls_for_testing(self):
        profile = LinuxSandboxProfile(
            required_namespaces=(),
            require_cgroup_v2=False,
            require_seccomp=False,
            require_lsm=False,
            require_non_root=False,
            require_read_only_root=False,
            require_network_isolation=False,
            require_resource_limits=False,
            require_process_tree_kill=False,
            require_output_quota=False,
            require_immutable_image=False,
        )
        result = evaluate_linux_profile(
            self.report(platform="linux", cgroup_mode="none"),
            profile, now="2026-11-11T03:01:00Z",
        )
        self.assertTrue(result.ready)

    def test_invalid_report_values_rejected(self):
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.report(seccomp_enforcing=1)
        with self.assertRaisesRegex(ValueError, "digest"):
            self.report(immutable_image_digest="mutable:latest")
        with self.assertRaisesRegex(ValueError, "namespaces"):
            self.report(namespaces=("pid", "pid"))
        with self.assertRaisesRegex(ValueError, "namespaces"):
            self.report(namespaces=([],))

    def test_invalid_profile_and_age_rejected(self):
        with self.assertRaisesRegex(ValueError, "namespaces"):
            LinuxSandboxProfile(required_namespaces=("pid", "pid"))
        with self.assertRaisesRegex(ValueError, "namespaces"):
            LinuxSandboxProfile(required_namespaces=([],))
        with self.assertRaisesRegex(ValueError, "positive integer"):
            evaluate_linux_profile(self.report(), max_report_age_seconds=0)


if __name__ == "__main__":
    unittest.main()
