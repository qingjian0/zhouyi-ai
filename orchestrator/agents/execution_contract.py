"""Non-executing contracts for safely governed experiment execution.

This module validates and fingerprints declarations. It does NOT create a
sandbox, launch processes, enforce resource limits, or attest that a runner
actually honored a declaration.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _aware(value: str, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")


def _positive_number(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be a positive finite number")


def _digest(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("contract contains non-JSON or non-finite values") from exc


@dataclass(frozen=True)
class ResourceLimits:
    cpu_cores: float
    memory_mb: int
    process_count: int
    wall_time_seconds: int
    disk_mb: int
    max_output_bytes: int
    network_policy: str = "disabled"
    allowed_hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive_number(self.cpu_cores, "cpu_cores")
        for field in ("memory_mb", "process_count", "wall_time_seconds",
                      "disk_mb", "max_output_bytes"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field} must be a positive integer")
        if self.network_policy not in {"disabled", "allowlist"}:
            raise ValueError("network_policy must be disabled or allowlist")
        if not isinstance(self.allowed_hosts, tuple):
            raise ValueError("allowed_hosts must be a tuple")
        if self.network_policy == "disabled" and self.allowed_hosts:
            raise ValueError("allowed_hosts must be empty when network is disabled")
        if self.network_policy == "allowlist":
            if not self.allowed_hosts or len(set(self.allowed_hosts)) != len(self.allowed_hosts):
                raise ValueError("allowlist network policy requires unique allowed_hosts")
            for host in self.allowed_hosts:
                if (not isinstance(host, str) or not host or "/" in host
                        or ":" in host or any(ch.isspace() for ch in host)):
                    raise ValueError("allowed_hosts must contain hostnames only")


@dataclass(frozen=True)
class ExecutionManifest:
    experiment_id: str
    code_revision: str
    dataset_digest: str
    model_id: str
    model_version: str
    seed: int
    command_id: str
    argv: tuple[str, ...]
    limits: ResourceLimits
    created_at: str
    patch_digest: str | None = None

    def __post_init__(self) -> None:
        for field in ("experiment_id", "model_id", "model_version", "command_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
        if not _COMMIT.fullmatch(self.code_revision):
            raise ValueError("code_revision must be a full 40-64 character commit SHA")
        _digest(self.dataset_digest, "dataset_digest")
        if self.patch_digest is not None:
            _digest(self.patch_digest, "patch_digest")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not _IDENTIFIER.fullmatch(self.command_id):
            raise ValueError("command_id must be a safe allowlist identifier")
        if not isinstance(self.argv, tuple) or not self.argv:
            raise ValueError("argv must be a non-empty tuple of argument strings")
        for arg in self.argv:
            if not isinstance(arg, str) or "\x00" in arg or any(ord(ch) < 32 for ch in arg):
                raise ValueError("argv must contain plain strings without control characters")
        if not isinstance(self.limits, ResourceLimits):
            raise ValueError("limits must be ResourceLimits")
        _aware(self.created_at, "created_at")


def manifest_digest(manifest: ExecutionManifest) -> str:
    if not isinstance(manifest, ExecutionManifest):
        raise TypeError("manifest must be ExecutionManifest")
    payload = asdict(manifest)
    return hashlib.sha256(_canonical(payload)).hexdigest()


@dataclass(frozen=True)
class ApprovalBinding:
    manifest_digest: str
    patch_digest: str
    target_branch: str
    approved_by: str
    approved_at: str

    def __post_init__(self) -> None:
        _digest(self.manifest_digest, "manifest_digest")
        _digest(self.patch_digest, "patch_digest")
        if not isinstance(self.target_branch, str) or not self.target_branch.strip():
            raise ValueError("target_branch must be non-empty text")
        if not isinstance(self.approved_by, str) or not self.approved_by.strip():
            raise ValueError("approved_by must be non-empty text")
        _aware(self.approved_at, "approved_at")


def validate_approval(
    manifest: ExecutionManifest,
    approval: ApprovalBinding,
    *,
    current_patch_digest: str,
    target_branch: str,
) -> None:
    """Reject stale approvals if manifest, patch bytes, or target branch changed."""
    _digest(current_patch_digest, "current_patch_digest")
    if not isinstance(approval, ApprovalBinding):
        raise TypeError("approval must be ApprovalBinding")
    expected_patch = manifest.patch_digest
    if expected_patch is None:
        raise ValueError("manifest has no patch_digest and cannot be approved for patch execution")
    if approval.manifest_digest != manifest_digest(manifest):
        raise ValueError("approval does not match the current execution manifest")
    if approval.patch_digest != expected_patch or current_patch_digest != expected_patch:
        raise ValueError("approval is stale: patch digest changed")
    if approval.target_branch != target_branch:
        raise ValueError("approval is stale: target branch changed")


@dataclass(frozen=True)
class ExecutionRecord:
    manifest_digest: str
    patch_digest: str | None
    runner_id: str
    status: str
    exit_code: int | None
    started_at: str
    finished_at: str
    cpu_seconds: float
    peak_memory_mb: float
    disk_written_mb: float
    output_bytes: int
    output_artifact_digest: str | None = None

    def __post_init__(self) -> None:
        _digest(self.manifest_digest, "manifest_digest")
        if self.patch_digest is not None:
            _digest(self.patch_digest, "patch_digest")
        if not isinstance(self.runner_id, str) or not self.runner_id.strip():
            raise ValueError("runner_id must be non-empty text")
        if self.status not in {"completed", "failed", "timed_out", "cancelled"}:
            raise ValueError("unsupported execution status")
        if self.exit_code is not None and (
            isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int)
        ):
            raise ValueError("exit_code must be an integer or None")
        _aware(self.started_at, "started_at")
        _aware(self.finished_at, "finished_at")
        for field in ("cpu_seconds", "peak_memory_mb", "disk_written_mb"):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{field} must be a non-negative finite number")
        if isinstance(self.output_bytes, bool) or not isinstance(self.output_bytes, int) or self.output_bytes < 0:
            raise ValueError("output_bytes must be a non-negative integer")
        if self.output_artifact_digest is not None:
            _digest(self.output_artifact_digest, "output_artifact_digest")


def validate_execution_record(
    manifest: ExecutionManifest,
    record: ExecutionRecord,
) -> None:
    """Check that a runner record is linked to and within a manifest budget.

    This validates reported observations; it cannot prove that the runner
    measured them honestly or enforced limits during execution.
    """
    if not isinstance(manifest, ExecutionManifest):
        raise TypeError("manifest must be ExecutionManifest")
    if not isinstance(record, ExecutionRecord):
        raise TypeError("record must be ExecutionRecord")
    if record.manifest_digest != manifest_digest(manifest):
        raise ValueError("execution record belongs to a different manifest")
    if record.patch_digest != manifest.patch_digest:
        raise ValueError("execution record patch digest does not match manifest")
    started = datetime.fromisoformat(record.started_at.replace("Z", "+00:00"))
    finished = datetime.fromisoformat(record.finished_at.replace("Z", "+00:00"))
    if finished < started:
        raise ValueError("finished_at must not precede started_at")
    elapsed = (finished - started).total_seconds()
    limits = manifest.limits
    if elapsed > limits.wall_time_seconds:
        raise ValueError("reported wall time exceeds manifest limit")
    if record.cpu_seconds > limits.cpu_cores * limits.wall_time_seconds:
        raise ValueError("reported CPU time exceeds manifest limit")
    if record.peak_memory_mb > limits.memory_mb:
        raise ValueError("reported peak memory exceeds manifest limit")
    if record.disk_written_mb > limits.disk_mb:
        raise ValueError("reported disk writes exceed manifest limit")
    if record.output_bytes > limits.max_output_bytes:
        raise ValueError("reported output exceeds manifest limit")
    if record.status == "completed" and record.exit_code != 0:
        raise ValueError("completed execution must have exit_code 0")
