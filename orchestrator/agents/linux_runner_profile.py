"""Fail-closed policy evaluation for a Linux sandbox capability report.

This module does not probe the host or enforce isolation. A trusted external
supervisor must produce CapabilityReport from actual checks; callers must not
construct a report from user-controlled manifest fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


_ALLOWED_NAMESPACES = frozenset({"user", "pid", "mount", "network", "ipc", "uts"})


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class CapabilityReport:
    """Facts reported by an independently trusted Linux supervisor."""

    platform: str
    kernel_release: str
    namespaces: tuple[str, ...]
    cgroup_mode: str
    seccomp_enforcing: bool
    lsm_enforcing: bool
    non_root_identity: bool
    read_only_root: bool
    network_isolated: bool
    resource_limits_enforced: bool
    process_tree_kill: bool
    output_quota_enforced: bool
    immutable_image_digest: str | None
    probe_id: str
    observed_at: str

    def __post_init__(self) -> None:
        for field in ("platform", "kernel_release", "cgroup_mode", "probe_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
        if not isinstance(self.namespaces, tuple):
            raise ValueError("namespaces must be a tuple")
        if len(set(self.namespaces)) != len(self.namespaces):
            raise ValueError("namespaces must not contain duplicates")
        if any(not isinstance(item, str) or item not in _ALLOWED_NAMESPACES
               for item in self.namespaces):
            raise ValueError("namespaces contains an unsupported namespace")
        for field in (
            "seccomp_enforcing", "lsm_enforcing", "non_root_identity",
            "read_only_root", "network_isolated", "resource_limits_enforced",
            "process_tree_kill", "output_quota_enforced",
        ):
            if type(getattr(self, field)) is not bool:
                raise ValueError(f"{field} must be boolean")
        if self.immutable_image_digest is not None:
            digest = self.immutable_image_digest
            if (not isinstance(digest, str) or len(digest) != 71
                    or not digest.startswith("sha256:")
                    or any(ch not in "0123456789abcdef" for ch in digest[7:])):
                raise ValueError("immutable_image_digest must be sha256:<64 lowercase hex>")
        _timestamp(self.observed_at, "observed_at")


@dataclass(frozen=True)
class LinuxSandboxProfile:
    """Minimum controls required before an untrusted experiment may start."""

    required_namespaces: tuple[str, ...] = ("user", "pid", "mount", "network")
    require_cgroup_v2: bool = True
    require_seccomp: bool = True
    require_lsm: bool = True
    require_non_root: bool = True
    require_read_only_root: bool = True
    require_network_isolation: bool = True
    require_resource_limits: bool = True
    require_process_tree_kill: bool = True
    require_output_quota: bool = True
    require_immutable_image: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.required_namespaces, tuple):
            raise ValueError("required_namespaces must be a tuple")
        if len(set(self.required_namespaces)) != len(self.required_namespaces):
            raise ValueError("required_namespaces must not contain duplicates")
        if any(not isinstance(item, str) or item not in _ALLOWED_NAMESPACES
               for item in self.required_namespaces):
            raise ValueError("required_namespaces contains an unsupported namespace")
        for field in (
            "require_cgroup_v2", "require_seccomp", "require_lsm",
            "require_non_root", "require_read_only_root",
            "require_network_isolation", "require_resource_limits",
            "require_process_tree_kill", "require_output_quota",
            "require_immutable_image",
        ):
            if type(getattr(self, field)) is not bool:
                raise ValueError(f"{field} must be boolean")


@dataclass(frozen=True)
class PreflightDecision:
    status: str
    missing_capabilities: tuple[str, ...]
    probe_id: str

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def evaluate_linux_profile(
    report: CapabilityReport,
    profile: LinuxSandboxProfile = LinuxSandboxProfile(),
    *,
    now: str | None = None,
    max_report_age_seconds: int = 300,
) -> PreflightDecision:
    """Evaluate a supervisor report; any missing/stale fact blocks execution.

    A ready decision means only that the supplied report satisfies the profile.
    It is not proof that the report is truthful or that controls remain active.
    """
    if not isinstance(report, CapabilityReport):
        raise TypeError("report must be CapabilityReport")
    if not isinstance(profile, LinuxSandboxProfile):
        raise TypeError("profile must be LinuxSandboxProfile")
    if (isinstance(max_report_age_seconds, bool)
            or not isinstance(max_report_age_seconds, int)
            or max_report_age_seconds <= 0):
        raise ValueError("max_report_age_seconds must be a positive integer")

    current = _timestamp(now, "now") if now is not None else datetime.now(timezone.utc)
    observed = _timestamp(report.observed_at, "observed_at")
    age = (current - observed).total_seconds()
    missing: list[str] = []

    if report.platform.lower() != "linux":
        missing.append("platform:linux")
    if age < -30 or age > max_report_age_seconds:
        missing.append("fresh_capability_report")
    if profile.require_cgroup_v2 and report.cgroup_mode != "v2":
        missing.append("cgroup_v2")
    missing.extend(
        f"namespace:{name}"
        for name in profile.required_namespaces
        if name not in report.namespaces
    )
    requirements = (
        ("seccomp", profile.require_seccomp, report.seccomp_enforcing),
        ("lsm_enforcing", profile.require_lsm, report.lsm_enforcing),
        ("non_root_identity", profile.require_non_root, report.non_root_identity),
        ("read_only_root", profile.require_read_only_root, report.read_only_root),
        ("network_isolated", profile.require_network_isolation, report.network_isolated),
        ("resource_limits_enforced", profile.require_resource_limits, report.resource_limits_enforced),
        ("process_tree_kill", profile.require_process_tree_kill, report.process_tree_kill),
        ("output_quota_enforced", profile.require_output_quota, report.output_quota_enforced),
        ("immutable_image_digest", profile.require_immutable_image,
         report.immutable_image_digest is not None),
    )
    missing.extend(name for name, required, available in requirements
                   if required and not available)

    return PreflightDecision(
        status="ready" if not missing else "blocked",
        missing_capabilities=tuple(missing),
        probe_id=report.probe_id,
    )
