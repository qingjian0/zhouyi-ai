"""Read-only Linux host capability observations for P1.6.2.

This probe never launches subprocesses, changes namespaces, mounts filesystems,
writes cgroups, or changes security policy. Host observations are NOT a sandbox
attestation and must never authorize execution of untrusted experiments.
"""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ProbeFact:
    state: str
    evidence: str

    def __post_init__(self) -> None:
        if self.state not in {"available", "unavailable", "unknown"}:
            raise ValueError("probe fact state must be available, unavailable, or unknown")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("probe fact evidence must be non-empty text")


@dataclass(frozen=True)
class HostProbeSnapshot:
    platform: str
    kernel_release: str
    facts: tuple[tuple[str, ProbeFact], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.platform, str) or not self.platform:
            raise ValueError("platform must be non-empty text")
        if not isinstance(self.kernel_release, str) or not self.kernel_release:
            raise ValueError("kernel_release must be non-empty text")
        if not isinstance(self.facts, tuple):
            raise ValueError("facts must be a tuple")
        names = [name for name, _ in self.facts]
        if len(set(names)) != len(names):
            raise ValueError("fact names must be unique")
        for name, fact in self.facts:
            if not isinstance(name, str) or not name:
                raise ValueError("fact names must be non-empty text")
            if not isinstance(fact, ProbeFact):
                raise ValueError("facts must contain ProbeFact values")

    def fact(self, name: str) -> ProbeFact:
        for key, value in self.facts:
            if key == name:
                return value
        raise KeyError(name)

    @property
    def unknown_facts(self) -> tuple[str, ...]:
        return tuple(name for name, fact in self.facts if fact.state == "unknown")

    @property
    def unavailable_facts(self) -> tuple[str, ...]:
        return tuple(name for name, fact in self.facts if fact.state == "unavailable")


class LinuxHostProbe:
    """Collect conservative, read-only facts about the current host process."""

    _NAMESPACE_PATHS = {
        "user": "/proc/self/ns/user",
        "pid": "/proc/self/ns/pid",
        "mount": "/proc/self/ns/mnt",
        "network": "/proc/self/ns/net",
    }

    def __init__(
        self,
        *,
        platform_name: str | None = None,
        kernel_release: str | None = None,
        read_text: Callable[[str], str | None] | None = None,
        path_exists: Callable[[str], bool] | None = None,
        effective_uid: Callable[[], int] | None = None,
    ) -> None:
        self._platform = platform_name if platform_name is not None else sys.platform
        self._kernel = kernel_release if kernel_release is not None else platform.release()
        self._read_text = read_text or self._read_file
        self._exists = path_exists or (lambda path: Path(path).exists())
        self._euid = effective_uid or self._effective_uid

    @staticmethod
    def _read_file(path: str) -> str | None:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            return None

    @staticmethod
    def _effective_uid() -> int:
        getter = getattr(os, "geteuid", None)
        if getter is None:
            return -1
        return getter()

    def collect(self) -> HostProbeSnapshot:
        if self._platform != "linux":
            facts = (
                ("namespace_handles", ProbeFact("unknown", "Linux-only probe not run")),
                ("cgroup_v2_mount", ProbeFact("unknown", "Linux-only probe not run")),
                ("current_process_seccomp_filter", ProbeFact("unknown", "Linux-only probe not run")),
                ("active_lsm_list", ProbeFact("unknown", "Linux-only probe not run")),
                ("current_process_non_root", ProbeFact("unknown", "Linux-only probe not run")),
                ("target_read_only_root", ProbeFact("unknown", "not established by host probe")),
                ("target_network_isolation", ProbeFact("unknown", "not established by host probe")),
                ("target_resource_limits", ProbeFact("unknown", "not established by host probe")),
                ("target_process_tree_kill", ProbeFact("unknown", "not established by host probe")),
                ("target_output_quota", ProbeFact("unknown", "not established by host probe")),
                ("immutable_execution_image", ProbeFact("unknown", "not established by host probe")),
            )
            return HostProbeSnapshot(self._platform, self._kernel, facts)

        namespace_present = [name for name, path in self._NAMESPACE_PATHS.items()
                             if self._exists(path)]
        if len(namespace_present) == len(self._NAMESPACE_PATHS):
            namespace_fact = ProbeFact(
                "available",
                "namespace handles exist for the current process; creation of new namespaces is not proven",
            )
        else:
            missing = sorted(set(self._NAMESPACE_PATHS) - set(namespace_present))
            namespace_fact = ProbeFact(
                "unavailable",
                "current-process namespace handles missing: " + ",".join(missing),
            )

        cgroup_path = "/sys/fs/cgroup/cgroup.controllers"
        cgroup_fact = (
            ProbeFact("available", "cgroup v2 controller file is mounted")
            if self._exists(cgroup_path)
            else ProbeFact("unavailable", "cgroup v2 controller file is not visible")
        )

        status = self._read_text("/proc/self/status")
        seccomp_fact = ProbeFact("unknown", "Seccomp field unavailable or malformed")
        if status is not None:
            for line in status.splitlines():
                if line.startswith("Seccomp:"):
                    value = line.split(":", 1)[1].strip()
                    if value in {"1", "2"}:
                        seccomp_fact = ProbeFact(
                            "available",
                            f"current process Seccomp mode is {value}; this does not prove child sandbox policy",
                        )
                    elif value == "0":
                        seccomp_fact = ProbeFact(
                            "unavailable",
                            "current process reports Seccomp mode 0; child enforcement remains unverified",
                        )
                    break

        lsm_text = self._read_text("/sys/kernel/security/lsm")
        if lsm_text is None:
            lsm_fact = ProbeFact("unknown", "kernel LSM list is not readable")
        elif lsm_text.strip():
            lsm_fact = ProbeFact(
                "available",
                "kernel reports active LSM names: " + ",".join(lsm_text.split()),
            )
        else:
            lsm_fact = ProbeFact("unavailable", "kernel LSM list is empty")

        uid = self._euid()
        if isinstance(uid, int) and uid >= 0:
            identity_fact = (
                ProbeFact("available", f"current process effective UID is {uid}")
                if uid != 0 else
                ProbeFact("unavailable", "current process is running as effective UID 0")
            )
        else:
            identity_fact = ProbeFact("unknown", "effective UID cannot be determined")

        facts = (
            ("namespace_handles", namespace_fact),
            ("cgroup_v2_mount", cgroup_fact),
            ("current_process_seccomp_filter", seccomp_fact),
            ("active_lsm_list", lsm_fact),
            ("current_process_non_root", identity_fact),
            ("target_read_only_root", ProbeFact("unknown", "target mount configuration requires supervisor attestation")),
            ("target_network_isolation", ProbeFact("unknown", "target network namespace and policy require supervisor attestation")),
            ("target_resource_limits", ProbeFact("unknown", "configured cgroup limits require supervisor attestation")),
            ("target_process_tree_kill", ProbeFact("unknown", "supervisor watchdog behavior requires runtime verification")),
            ("target_output_quota", ProbeFact("unknown", "target filesystem/output quota requires supervisor attestation")),
            ("immutable_execution_image", ProbeFact("unknown", "image identity requires supervisor-provided immutable digest")),
        )
        return HostProbeSnapshot(self._platform, self._kernel, facts)
