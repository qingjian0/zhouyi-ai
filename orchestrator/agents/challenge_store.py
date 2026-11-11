"""Durable one-time execution challenges and replay protection.

The store issues unpredictable challenges and atomically consumes them only
after the caller's signed attestation has been cryptographically verified.
"""
from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from orchestrator.agents.execution_attestation import (
    SandboxAttestation, SignedSandboxAttestation, verify_attestation,
)
from orchestrator.agents.execution_contract import ExecutionManifest, manifest_digest


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


@dataclass(frozen=True)
class ExecutionChallenge:
    nonce: str
    execution_id: str
    manifest_digest: str
    patch_digest: str | None
    target_branch: str
    runner_id: str
    image_digest: str
    issued_at: str
    expires_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.nonce, str) or len(self.nonce) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.nonce
        ):
            raise ValueError("nonce must be 64 lowercase hex characters")
        for field in ("execution_id", "target_branch", "runner_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
        for field, value in (("manifest_digest", self.manifest_digest),
                             ("patch_digest", self.patch_digest)):
            if value is None and field == "patch_digest":
                continue
            if not isinstance(value, str) or len(value) != 64 or any(
                ch not in "0123456789abcdef" for ch in value
            ):
                raise ValueError(f"{field} must be a lowercase SHA-256 digest")
        if (not isinstance(self.image_digest, str)
                or not self.image_digest.startswith("sha256:")
                or len(self.image_digest) != 71
                or any(ch not in "0123456789abcdef" for ch in self.image_digest[7:])):
            raise ValueError("image_digest must be sha256:<64 lowercase hex>")
        issued = _aware(self.issued_at, "issued_at")
        expires = _aware(self.expires_at, "expires_at")
        if expires <= issued:
            raise ValueError("expires_at must be later than issued_at")


class ExecutionChallengeStore:
    """SQLite-backed challenge issuer and atomic one-time attestation verifier."""

    def __init__(
        self,
        path: str | Path,
        *,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._nonce_factory = nonce_factory or (lambda: secrets.token_hex(32))
        with self._session() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS execution_challenges (
                    nonce TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL,
                    patch_digest TEXT,
                    target_branch TEXT NOT NULL,
                    runner_id TEXT NOT NULL,
                    image_digest TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0, isolation_level="DEFERRED")
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    @contextmanager
    def _session(self):
        db = self._connect()
        try:
            with db:
                yield db
        finally:
            db.close()

    def issue(
        self,
        manifest: ExecutionManifest,
        *,
        execution_id: str,
        target_branch: str,
        runner_id: str,
        image_digest: str,
        now: str | None = None,
        ttl_seconds: int = 180,
    ) -> ExecutionChallenge:
        if not isinstance(manifest, ExecutionManifest):
            raise TypeError("manifest must be ExecutionManifest")
        for field, value in (
            ("execution_id", execution_id),
            ("target_branch", target_branch),
            ("runner_id", runner_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be non-empty text")
        if (not isinstance(image_digest, str)
                or not image_digest.startswith("sha256:")
                or len(image_digest) != 71
                or any(ch not in "0123456789abcdef" for ch in image_digest[7:])):
            raise ValueError("image_digest must be sha256:<64 lowercase hex>")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 1 <= ttl_seconds <= 300:
            raise ValueError("ttl_seconds must be an integer from 1 through 300")

        issued = _aware(now, "now") if now is not None else datetime.now(timezone.utc)
        expires = issued + timedelta(seconds=ttl_seconds)
        issued_text = issued.isoformat().replace("+00:00", "Z")
        expires_text = expires.isoformat().replace("+00:00", "Z")
        nonce = self._nonce_factory()
        if not isinstance(nonce, str) or len(nonce) != 64 or any(
            ch not in "0123456789abcdef" for ch in nonce
        ):
            raise ValueError("nonce_factory must return 64 lowercase hex characters")

        challenge = ExecutionChallenge(
            nonce=nonce,
            execution_id=execution_id,
            manifest_digest=manifest_digest(manifest),
            patch_digest=manifest.patch_digest,
            target_branch=target_branch,
            runner_id=runner_id,
            image_digest=image_digest,
            issued_at=issued_text,
            expires_at=expires_text,
        )
        try:
            with self._session() as db:
                db.execute(
                    """INSERT INTO execution_challenges
                    (nonce, execution_id, manifest_digest, patch_digest,
                     target_branch, runner_id, image_digest, issued_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        challenge.nonce, challenge.execution_id,
                        challenge.manifest_digest, challenge.patch_digest,
                        challenge.target_branch, challenge.runner_id,
                        challenge.image_digest, challenge.issued_at,
                        challenge.expires_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("challenge nonce collision; issue a fresh challenge") from exc
        return challenge

    def verify_and_consume(
        self,
        signed: SignedSandboxAttestation,
        key: bytes,
        manifest: ExecutionManifest,
        challenge: ExecutionChallenge,
        *,
        now: str | None = None,
        expected_key_id: str | None = None,
    ) -> SandboxAttestation:
        """Verify signed evidence, then consume its challenge exactly once."""
        if not isinstance(challenge, ExecutionChallenge):
            raise TypeError("challenge must be ExecutionChallenge")
        attestation = verify_attestation(
            signed,
            key,
            manifest,
            expected_execution_id=challenge.execution_id,
            expected_target_branch=challenge.target_branch,
            expected_runner_id=challenge.runner_id,
            expected_image_digest=challenge.image_digest,
            expected_challenge_nonce=challenge.nonce,
            now=now,
            expected_key_id=expected_key_id,
            max_lifetime_seconds=300,
        )
        self._consume_verified(challenge, attestation, now=now)
        return attestation

    def _consume_verified(
        self,
        challenge: ExecutionChallenge,
        attestation: SandboxAttestation,
        *,
        now: str | None,
    ) -> None:
        current = _aware(now, "now") if now is not None else datetime.now(timezone.utc)
        issued = _aware(challenge.issued_at, "challenge.issued_at")
        expires = _aware(challenge.expires_at, "challenge.expires_at")
        att_issued = _aware(attestation.issued_at, "attestation.issued_at")
        att_expires = _aware(attestation.expires_at, "attestation.expires_at")
        bindings = (
            (attestation.execution_id, challenge.execution_id, "execution_id"),
            (attestation.manifest_digest, challenge.manifest_digest, "manifest_digest"),
            (attestation.patch_digest, challenge.patch_digest, "patch_digest"),
            (attestation.target_branch, challenge.target_branch, "target_branch"),
            (attestation.runner_id, challenge.runner_id, "runner_id"),
            (attestation.image_digest, challenge.image_digest, "image_digest"),
            (attestation.challenge_nonce, challenge.nonce, "challenge_nonce"),
        )
        for actual, expected, name in bindings:
            if actual != expected:
                raise ValueError(f"attestation {name} does not match durable challenge")
        if current > expires:
            raise ValueError("execution challenge has expired")
        if att_issued < issued or att_issued > expires:
            raise ValueError("attestation was issued outside the challenge window")
        if att_expires > expires:
            raise ValueError("attestation expiry exceeds challenge expiry")

        with self._session() as db:
            # Serialize competing consumers before checking consumed_at.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT execution_id, manifest_digest, patch_digest,
                          target_branch, runner_id, image_digest,
                          issued_at, expires_at, consumed_at
                   FROM execution_challenges WHERE nonce = ?""",
                (challenge.nonce,),
            ).fetchone()
            if row is None:
                raise KeyError("execution challenge is not registered")
            expected = (
                challenge.execution_id, challenge.manifest_digest,
                challenge.patch_digest, challenge.target_branch,
                challenge.runner_id, challenge.image_digest,
                challenge.issued_at, challenge.expires_at,
            )
            if row[:8] != expected:
                raise ValueError("challenge data does not match durable record")
            if row[8] is not None:
                raise ValueError("execution challenge has already been consumed")
            changed = db.execute(
                """UPDATE execution_challenges SET consumed_at = ?
                   WHERE nonce = ? AND consumed_at IS NULL""",
                (current.isoformat().replace("+00:00", "Z"), challenge.nonce),
            ).rowcount
            if changed != 1:
                raise ValueError("execution challenge has already been consumed")
