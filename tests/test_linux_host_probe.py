import unittest

from orchestrator.agents.linux_host_probe import LinuxHostProbe, ProbeFact


class LinuxHostProbeTests(unittest.TestCase):
    def make_probe(self, *, exists=None, files=None, uid=1000, platform_name="linux"):
        files = files or {}
        exists = exists or set()
        return LinuxHostProbe(
            platform_name=platform_name,
            kernel_release="6.8-test",
            read_text=lambda path: files.get(path),
            path_exists=lambda path: path in exists,
            effective_uid=lambda: uid,
        )

    def test_probe_reports_only_observed_host_facts(self):
        paths = {
            "/proc/self/ns/user", "/proc/self/ns/pid",
            "/proc/self/ns/mnt", "/proc/self/ns/net",
            "/sys/fs/cgroup/cgroup.controllers",
        }
        probe = self.make_probe(
            exists=paths,
            files={
                "/proc/self/status": "Name:\tpython\nSeccomp:\t2\n",
                "/sys/kernel/security/lsm": "landlock,lockdown,yama,apparmor,bpf",
            },
        )
        snapshot = probe.collect()
        self.assertEqual(snapshot.platform, "linux")
        self.assertEqual(snapshot.fact("namespace_handles").state, "available")
        self.assertEqual(snapshot.fact("cgroup_v2_mount").state, "available")
        self.assertEqual(snapshot.fact("current_process_seccomp_filter").state, "available")
        self.assertEqual(snapshot.fact("active_lsm_list").state, "available")
        self.assertEqual(snapshot.fact("current_process_non_root").state, "available")
        self.assertEqual(snapshot.fact("target_resource_limits").state, "unknown")
        self.assertEqual(snapshot.fact("target_network_isolation").state, "unknown")
        self.assertIn("target_output_quota", snapshot.unknown_facts)

    def test_missing_host_primitives_are_unavailable(self):
        snapshot = self.make_probe(
            exists=set(),
            files={"/proc/self/status": "Name:\tpython\nSeccomp:\t0\n",
                   "/sys/kernel/security/lsm": ""},
            uid=0,
        ).collect()
        self.assertEqual(snapshot.fact("namespace_handles").state, "unavailable")
        self.assertEqual(snapshot.fact("cgroup_v2_mount").state, "unavailable")
        self.assertEqual(snapshot.fact("current_process_seccomp_filter").state, "unavailable")
        self.assertEqual(snapshot.fact("active_lsm_list").state, "unavailable")
        self.assertEqual(snapshot.fact("current_process_non_root").state, "unavailable")

    def test_unreadable_or_malformed_inputs_are_unknown(self):
        snapshot = self.make_probe(files={}, exists=set(), uid=-1).collect()
        self.assertEqual(snapshot.fact("current_process_seccomp_filter").state, "unknown")
        self.assertEqual(snapshot.fact("active_lsm_list").state, "unknown")
        self.assertEqual(snapshot.fact("current_process_non_root").state, "unknown")

    def test_non_linux_platform_never_claims_linux_features(self):
        snapshot = self.make_probe(platform_name="win32").collect()
        self.assertEqual(snapshot.fact("namespace_handles").state, "unknown")
        self.assertTrue(all(snapshot.fact(name).state == "unknown" for name in (
            "target_read_only_root", "target_network_isolation",
            "target_resource_limits", "target_process_tree_kill",
            "target_output_quota", "immutable_execution_image",
        )))

    def test_unknown_fact_name_rejected(self):
        snapshot = self.make_probe(platform_name="darwin").collect()
        with self.assertRaises(KeyError):
            snapshot.fact("does_not_exist")

    def test_probe_fact_rejects_invalid_state(self):
        with self.assertRaisesRegex(ValueError, "state"):
            ProbeFact("yes", "not a supported state")


if __name__ == "__main__":
    unittest.main()
