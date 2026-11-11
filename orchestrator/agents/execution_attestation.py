"""Signed, per-execution sandbox evidence bound to an exact manifest.

HMAC proves possession of a shared supervisor key, not that the supervisor is
honest or that controls remain active after attestation. Key custody and the
runtime enforcement loop remain outside this module.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from orchestrator.agents.execution_contract import ExecutionManifest, manifest_digest


_REQUIRED_CONTROLS = frozenset({
    "namespace:user",
    "namespace:pid",
    "namespace:mount",
    "namespace:network",
    "cgroup:v2",
    "seccomp:enforcing",
    "lsm:enforcing",
    "identity:non-root",
    "filesystem:root-read-only",
    "network:isolated",
    "resources:enforced",
    "process-tree:kill",
    "output:quota",
    "image:immutable",
})
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _aware(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware ISO-8601 timestamp")
    return parsed.astimezone(timezone.utc)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("attestation contains non-JSON values") from exc


def _digest(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _key(value: bytes) -> None:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ValueError("HMAC key must contain at least 32 bytes")


@dataclass(frozen=True)
class SandboxAttestation:
    schema_version: int
    key_id: str
    execution_id: str
    manifest_digest: str
    patch_digest: str | None
    target_branch: str
    runner_id: str
    supervisor_id: str
    image_digest: str
    challenge_nonce: str
    verified_controls: tuple[str, ...]
    issued_at: str
    expires_at: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported attestation schema_version")
        if not isinstance(self.key_id, str) or not _KEY_ID.fullmatch(self.key_id):
            raise ValueError("key_id must be a safe identifier")
        for field in ("execution_id", "target_branch", "runner_id", "supervisor_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
        _digest(self.manifest_digest, "manifest_digest")
        if self.patch_digest is not None:
            _digest(self.patch_digest, "patch_digest")
        if (not isinstance(self.image_digest, str)
                or not self.image_digest.startswith("sha256:")
                or not _HEX64.fullmatch(self.image_digest[7:])):
            raise ValueError("image_digest must be sha256:<64 lowercase hex>")
        if not isinstance(self.challenge_nonce, str) or not _HEX64.fullmatch(self.challenge_nonce):
            raise ValueError("challenge_nonce must be 64 lowercase hex characters")
        if not isinstance(self.verified_controls, tuple):
            raise ValueError("verified_controls must be a tuple")
        if any(not isinstance(item, str) for item in self.verified_controls):
            raise ValueError("verified_controls must contain strings")
        if len(set(self.verified_controls)) != len(self.verified_controls):
            raise ValueError("verified_controls must not contain duplicates")
        unknown = set(self.verified_controls) - _REQUIRED_CONTROLS
        if unknown:
            raise ValueError("verified_controls contains unknown control names")
        missing = _REQUIRED_CONTROLS - set(self.verified_controls)
        if missing:
            raise ValueError("attestation is missing required controls: " + ",".join(sorted(missing)))
        issued = _aware(self.issued_at, "issued_at")
        expires = _aware(self.expires_at, "expires_at")
        if expires <= issued:
            raise ValueError("expires_at must be later than issued_at")


@dataclass(frozen=True)
class SignedSandboxAttestation:
    attestation: SandboxAttestation
    signature: str

    def __post_init__(self) -> None:
        if not isinstance(self.attestation, SandboxAttestation):
            raise ValueError("attestation must be SandboxAttestation")
        if not isinstance(self.signature, str) or not _HEX64.fullmatch(self.signature):
            raise ValueError("signature must be a lowercase HMAC-SHA256 hex digest")


def sign_attestation(attestation: SandboxAttestation, key: bytes) -> SignedSandboxAttestation:
    """Sign canonical attestation bytes. Call only inside the trusted supervisor."""
    if not isinstance(attestation, SandboxAttestation):
        raise TypeError("attestation must be SandboxAttestation")
    _key(key)
    signature = hmac.new(key, _canonical(asdict(attestation)), hashlib.sha256).hexdigest()
    return SignedSandboxAttestation(attestation, signature)


def verify_attestation(
    signed: SignedSandboxAttestation,
    key: bytes,
    manifest: ExecutionManifest,
    *,
    expected_execution_id: str,
    expected_target_branch: str,
    expected_runner_id: str,
    expected_image_digest: str,
    expected_challenge_nonce: str,
    now: str | None = None,
    expected_key_id: str | None = None,
    max_lifetime_seconds: int = 300,
    clock_skew_seconds: int = 30,
) -> SandboxAttestation:
    """Verify signature, freshness, challenge, and exact execution bindings."""
    if not isinstance(signed, SignedSandboxAttestation):
        raise TypeError("signed must be SignedSandboxAttestation")
    if not isinstance(manifest, ExecutionManifest):
        raise TypeError("manifest must be ExecutionManifest")
    _key(key)
    for field, value in (
        ("expected_execution_id", expected_execution_id),
        ("expected_target_branch", expected_target_branch),
        ("expected_runner_id", expected_runner_id),
        ("expected_image_digest", expected_image_digest),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be non-empty text")
    _digest(expected_image_digest[7:] if expected_image_digest.startswith("sha256:") else "", "expected_image_digest")
    if not isinstance(expected_challenge_nonce, str) or not _HEX64.fullmatch(expected_challenge_nonce):
        raise ValueError("expected_challenge_nonce must be 64 lowercase hex characters")
    if (isinstance(max_lifetime_seconds, bool) or not isinstance(max_lifetime_seconds, int)
            or max_lifetime_seconds <= 0):
        raise ValueError("max_lifetime_seconds must be a positive integer")
    if (isinstance(clock_skew_seconds, bool) or not isinstance(clock_skew_seconds, int)
            or clock_skew_seconds < 0):
        raise ValueError("clock_skew_seconds must be a non-negative integer")

    attestation = signed.attestation
    expected_signature = hmac.new(
        key, _canonical(asdict(attestation)), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signed.signature):
        raise ValueError("attestation signature is invalid")
    if expected_key_id is not None and attestation.key_id != expected_key_id:
        raise ValueError("attestation key_id does not match the trusted key")
    if attestation.manifest_digest != manifest_digest(manifest):
        raise ValueError("attestation is bound to a different manifest")
    if attestation.patch_digest != manifest.patch_digest:
        raise ValueError("attestation patch digest does not match manifest")
    if attestation.execution_id != expected_execution_id:
        raise ValueError("attestation execution_id does not match")
    if attestation.target_branch != expected_target_branch:
        raise ValueError("attestation target branch does not match")
    if attestation.runner_id != expected_runner_id:
        raise ValueError("attestation runner_id does not match")
    if attestation.image_digest != expected_image_digest:
        raise ValueError("attestation image digest does not match")
    if attestation.challenge_nonce != expected_challenge_nonce:
        raise ValueError("attestation challenge nonce does not match")

    issued = _aware(attestation.issued_at, "issued_at")
    expires = _aware(attestation.expires_at, "expires_at")
    if (expires - issued).total_seconds() > max_lifetime_seconds:
        raise ValueError("attestation lifetime exceeds policy")
    current = _aware(now, "now") if now is not None else datetime.now(timezone.utc)
    if current.timestamp() < issued.timestamp() - clock_skew_seconds:
        raise ValueError("attestation is not yet valid")
    if current > expires:
        raise ValueError("attestation has expired")
    return attestation
