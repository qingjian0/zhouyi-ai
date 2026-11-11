"""Service-facing E09 authority and verifier contracts.

These classes are policy adapters around the SQLite reference store. They are
not an OS/process security boundary: production must host them in separate
services and expose only authenticated IPC, with database files inaccessible
to learner processes.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from prototype.e09_e12a6_evidence_bridge import resolve_branch_merge_authorization
from prototype.shared_evidence_protocol import (
    STRICT_PROTOCOL_VERSION,
    EventReceipt,
    SQLiteEvidenceStore,
)


class E09ServiceError(PermissionError):
    """An E09 service request lacks an authenticated identity or permission."""


class E09AuthenticationError(E09ServiceError):
    """The configured workload authenticator rejected a credential."""


class E09AuthorizationError(E09ServiceError):
    """An authenticated workload is not permitted to perform the operation."""


@dataclass(frozen=True)
class E09AuthenticatedWorkload:
    """Identity claims emitted only by the configured transport authenticator."""

    workload_id: str
    issuer_id: str
    roles: frozenset[str]
    scopes: frozenset[str]
    identity_provider: str
    authentication_method: str
    credential_fingerprint: str

    def __post_init__(self) -> None:
        for field in (
            "workload_id", "issuer_id", "identity_provider",
            "authentication_method", "credential_fingerprint",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")
        for field in ("roles", "scopes"):
            values = getattr(self, field)
            if not isinstance(values, (set, frozenset, tuple, list)):
                raise TypeError(f"{field} must be a collection of strings")
            if not values or any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError(f"{field} must contain non-empty strings")
            if len(values) != len(set(values)):
                raise ValueError(f"{field} must not contain duplicates")
            object.__setattr__(self, field, frozenset(values))


class E09WorkloadAuthenticator(Protocol):
    """Authenticate transport credentials (e.g. an mTLS peer certificate)."""

    def authenticate(self, credential: object) -> E09AuthenticatedWorkload:
        ...


class E09GrantSigner(Protocol):
    """HSM/KMS-backed issuer signer; private key material stays outside E09."""

    def sign(self, issuer_id: str, message: bytes) -> str:
        """Return a strict Base64 Ed25519 signature."""
        ...


class E09Clock(Protocol):
    """Server-owned clock. Never accept verification time from a remote caller."""

    def now(self) -> datetime:
        ...


class SystemUTCClock:
    """Default host UTC clock; production must harden its time source."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def _identity_metadata(principal: E09AuthenticatedWorkload) -> dict[str, Any]:
    return {
        "authenticated_workload": {
            "workload_id": principal.workload_id,
            "issuer_id": principal.issuer_id,
            "identity_provider": principal.identity_provider,
            "authentication_method": principal.authentication_method,
            "credential_fingerprint": principal.credential_fingerprint,
        }
    }


class E09AuthorityService:
    """Narrow write facade deriving event roles from authenticated workload identity.

    It deliberately has no generic append method and never accepts actor_role
    from a request. This protects callers that use the facade correctly, but
    direct access to the underlying store remains possible in this process.
    """

    def __init__(
        self,
        store: SQLiteEvidenceStore,
        *,
        authenticator: E09WorkloadAuthenticator,
        signer: E09GrantSigner,
        clock: E09Clock | None = None,
        max_grant_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not isinstance(store, SQLiteEvidenceStore):
            raise TypeError("store must be SQLiteEvidenceStore")
        if not callable(getattr(authenticator, "authenticate", None)):
            raise TypeError("authenticator must implement authenticate")
        if not callable(getattr(signer, "sign", None)):
            raise TypeError("signer must implement sign")
        if not isinstance(max_grant_ttl, timedelta) or max_grant_ttl <= timedelta(0):
            raise ValueError("max_grant_ttl must be a positive timedelta")
        self._store = store
        self._authenticator = authenticator
        self._signer = signer
        self._clock = clock or SystemUTCClock()
        self._max_grant_ttl = max_grant_ttl

    def _principal(self, credential: object, *, role: str, scope: str) -> E09AuthenticatedWorkload:
        if not isinstance(scope, str) or not scope.strip():
            raise E09AuthorizationError("scope must be a non-empty string")
        try:
            principal = self._authenticator.authenticate(credential)
        except Exception as exc:
            raise E09AuthenticationError("workload authentication failed") from exc
        if not isinstance(principal, E09AuthenticatedWorkload):
            raise E09AuthenticationError("authenticator returned an invalid workload identity")
        if role not in principal.roles:
            raise E09AuthorizationError(f"workload lacks required role: {role}")
        if scope not in principal.scopes:
            raise E09AuthorizationError("workload is not authorized for the requested scope")
        return principal

    def append_evidence_reveal(
        self,
        credential: object,
        *,
        episode_id: str,
        event_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
        causation_refs: tuple[str, ...] | list[str],
        expected_sequence: int | None = None,
    ) -> EventReceipt:
        """Append an evaluator reveal; the event role is derived, never supplied."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        scope = payload.get("scope")
        principal = self._principal(credential, role="evaluator", scope=scope)
        return self._store.append_event(
            episode_id=episode_id,
            event_id=event_id,
            event_type="evidence_reveal",
            idempotency_key=idempotency_key,
            payload=payload,
            actor_role="evaluator",
            causation_refs=causation_refs,
            integrity_metadata=_identity_metadata(principal),
            expected_sequence=expected_sequence,
            protocol_version=STRICT_PROTOCOL_VERSION,
        )

    def issue_branch_merge_authorization(
        self,
        credential: object,
        *,
        episode_id: str,
        authorization_id: str,
        scope: str,
        parent_state_ref: str,
        branch_ids: tuple[str, ...] | list[str],
        evidence_refs: tuple[str, ...] | list[str],
        ttl: timedelta = timedelta(minutes=2),
        authorization_id: str | None = None,
    ) -> EventReceipt:
        """Authenticate an authorizer, sign the exact next-sequence v2 envelope, append by CAS."""
        principal = self._principal(credential, role="authorizer", scope=scope)
        for name, value in (
            ("episode_id", episode_id), ("parent_state_ref", parent_state_ref),
        ):
            if not isinstance(value, str) or not value.strip():
                raise E09AuthorizationError(f"{name} must be a non-empty string")
        for name, values in (("branch_ids", branch_ids), ("evidence_refs", evidence_refs)):
            if not isinstance(values, (tuple, list)) or not values:
                raise E09AuthorizationError(f"{name} must be a non-empty sequence")
            if any(not isinstance(item, str) or not item.strip() for item in values):
                raise E09AuthorizationError(f"{name} must contain non-empty strings")
            if len(values) != len(set(values)):
                raise E09AuthorizationError(f"{name} must be unique")

        if not isinstance(ttl, timedelta) or ttl <= timedelta(0) or ttl > self._max_grant_ttl:
            raise E09AuthorizationError("grant TTL is outside authority policy")
        current = self._clock.now()
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise E09AuthenticationError("authority clock must return a timezone-aware datetime")
        current = current.astimezone(timezone.utc)
        issued_at = current.isoformat()
        expires_at = (current + ttl).isoformat()
        if authorization_id is None:
            auth_id = "e09-authz-" + secrets.token_hex(16)
        elif isinstance(authorization_id, str) and authorization_id.strip():
            auth_id = authorization_id
        else:
            raise E09AuthorizationError("authorization_id must be a non-empty string")

        prior_events = self._store.replay_episode(episode_id)
        sequence = (prior_events[-1]["sequence_no"] if prior_events else 0) + 1
        event_metadata = _identity_metadata(principal)
        payload = {
            "authorization_id": auth_id,
            "issuer_id": principal.issuer_id,
            "scope": scope,
            "parent_state_ref": parent_state_ref,
            "branch_ids": sorted(branch_ids),
            "evidence_refs": list(evidence_refs),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "signature_algorithm": "Ed25519",
            "signature_version": "E09-AUTHZ-SIG-V2",
            "audience": "e12a6-lifecycle",
            "authorization_sequence": sequence,
        }
        signing_event = {
            "episode_id": episode_id,
            "event_id": auth_id,
            "event_type": "branch_merge_authorization",
            "protocol_version": STRICT_PROTOCOL_VERSION,
            "payload_schema": "branch_merge_authorization@2",
            "actor_role": "authorizer",
            "causation_refs": list(evidence_refs),
            "integrity_metadata": event_metadata,
            "payload": payload,
        }
        from prototype.e09_e12a6_evidence_bridge import branch_merge_authorization_signing_bytes

        signature = self._signer.sign(
            principal.issuer_id, branch_merge_authorization_signing_bytes(signing_event)
        )
        if not isinstance(signature, str) or not signature.strip():
            raise E09AuthenticationError("configured issuer signer returned an invalid signature")
        payload["signature"] = signature
        return self._store.append_event(
            episode_id=episode_id,
            event_id=auth_id,
            event_type="branch_merge_authorization",
            idempotency_key=auth_id,
            payload=payload,
            actor_role="authorizer",
            causation_refs=evidence_refs,
            payload_schema="branch_merge_authorization@2",
            integrity_metadata=event_metadata,
            expected_sequence=sequence - 1,
            protocol_version=STRICT_PROTOCOL_VERSION,
        )


class E09VerifierService:
    """Verifier facade using server-owned time and a pinned issuer trust bundle."""

    def __init__(
        self,
        store: SQLiteEvidenceStore,
        *,
        signature_verifier: Callable[[str, str, bytes, str], bool],
        verifier_id: str,
        clock: E09Clock | None = None,
    ) -> None:
        if not isinstance(store, SQLiteEvidenceStore):
            raise TypeError("store must be SQLiteEvidenceStore")
        if not callable(signature_verifier):
            raise TypeError("signature_verifier must be callable")
        if not isinstance(verifier_id, str) or not verifier_id.strip():
            raise ValueError("verifier_id must be a non-empty string")
        self._store = store
        self._signature_verifier = signature_verifier
        self.verifier_id = verifier_id
        self._clock = clock or SystemUTCClock()

    def verify_branch_merge_authorization(self, **request: Any):
        """Verify with the service clock; caller-supplied now is rejected."""
        if "now" in request:
            raise E09AuthorizationError("verification time is controlled by the verifier service")
        current = self._clock.now()
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise E09AuthenticationError("verifier clock must return a timezone-aware datetime")
        return resolve_branch_merge_authorization(
            self._store,
            signature_verifier=self._signature_verifier,
            verifier_id=self.verifier_id,
            now=current,
            **request,
        )
