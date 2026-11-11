"""Authenticated E09 branch-merge authorization issuance service.

This is an in-process service boundary contract. Production deployments must
supply an authenticator backed by their identity provider and isolate this
service from learner/evaluator processes over authenticated IPC.
"""
from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from prototype.e09_e12a6_evidence_bridge import (
    AUTHORIZATION_AUDIENCE,
    AUTHORIZATION_PAYLOAD_SCHEMA,
    AUTHORIZATION_SIGNATURE_VERSION,
    branch_merge_authorization_signing_bytes,
)
from prototype.shared_evidence_protocol import STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore


class E09AuthorityError(PermissionError):
    """An authorization request is not authenticated or violates policy."""


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject_id: str
    issuer_id: str
    roles: frozenset[str]
    credential_id: str


class E09BranchMergeAuthority:
    """Issue signed, short-lived grants only for authenticated authorizer principals.

    The authenticator must validate credentials cryptographically (for example,
    mTLS workload identity or a signed access token) and return a principal.
    A caller-supplied role string is never accepted as identity evidence.
    """

    REQUIRED_ROLE = "branch_merge_authorizer"

    def __init__(
        self,
        store: SQLiteEvidenceStore,
        *,
        issuer_id: str,
        signing_key: Ed25519PrivateKey,
        authenticator: Callable[[Any], AuthenticatedPrincipal],
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        max_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not isinstance(store, SQLiteEvidenceStore):
            raise TypeError("store must be SQLiteEvidenceStore")
        if not isinstance(issuer_id, str) or not issuer_id.strip():
            raise ValueError("issuer_id is required")
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError("signing_key must be an Ed25519PrivateKey")
        if not callable(authenticator) or not callable(clock):
            raise TypeError("authenticator and clock must be callable")
        if not isinstance(max_ttl, timedelta) or max_ttl <= timedelta(0):
            raise ValueError("max_ttl must be positive")
        self._store = store
        self._issuer_id = issuer_id
        self._signing_key = signing_key
        self._authenticator = authenticator
        self._clock = clock
        self._max_ttl = max_ttl
        self.signing_public_key = signing_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def issue(
        self,
        credential: Any,
        *,
        episode_id: str,
        scope: str,
        parent_state_ref: str,
        branch_ids: Iterable[str],
        evidence_refs: Iterable[str],
        ttl: timedelta = timedelta(minutes=2),
        authorization_id: str | None = None,
    ):
        try:
            principal = self._authenticator(credential)
        except Exception as exc:
            raise E09AuthorityError("caller authentication failed") from exc
        if not isinstance(principal, AuthenticatedPrincipal):
            raise E09AuthorityError("authenticator returned no authenticated principal")
        if (not principal.subject_id.strip() or not principal.credential_id.strip()
                or principal.issuer_id != self._issuer_id
                or self.REQUIRED_ROLE not in principal.roles):
            raise E09AuthorityError("principal is not authorized to issue branch-merge grants")
        if not isinstance(ttl, timedelta) or ttl <= timedelta(0) or ttl > self._max_ttl:
            raise E09AuthorityError("grant TTL is outside authority policy")
        for name, value in (("episode_id", episode_id), ("scope", scope),
                            ("parent_state_ref", parent_state_ref)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        branches = list(branch_ids)
        evidence = list(evidence_refs)
        for name, values in (("branch_ids", branches), ("evidence_refs", evidence)):
            if not values or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"{name} must contain non-empty strings")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must be unique")
        if not evidence:
            raise ValueError("evidence_refs cannot be empty")

        current = self._clock()
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise E09AuthorityError("authority clock must return timezone-aware datetime")
        current = current.astimezone(timezone.utc)
        expires = current + ttl
        auth_id = authorization_id or "e09-authz-" + secrets.token_hex(16)
        if not isinstance(auth_id, str) or not auth_id.strip():
            raise ValueError("authorization_id must be non-empty")

        prior_events = self._store.replay_episode(episode_id)
        next_sequence = (prior_events[-1]["sequence_no"] if prior_events else 0) + 1
        payload = {
            "authorization_id": auth_id,
            "issuer_id": self._issuer_id,
            "scope": scope,
            "parent_state_ref": parent_state_ref,
            "branch_ids": sorted(branches),
            "evidence_refs": sorted(evidence),
            "issued_at": current.isoformat(),
            "expires_at": expires.isoformat(),
            "signature_algorithm": "Ed25519",
            "signature_version": AUTHORIZATION_SIGNATURE_VERSION,
            "audience": AUTHORIZATION_AUDIENCE,
            "authorization_sequence": next_sequence,
            "signature": "",
        }
        event = {
            "episode_id": episode_id,
            "event_id": auth_id,
            "event_type": "branch_merge_authorization",
            "protocol_version": STRICT_PROTOCOL_VERSION,
            "payload_schema": AUTHORIZATION_PAYLOAD_SCHEMA,
            "actor_role": "authorizer",
            "causation_refs": sorted(evidence),
            "integrity_metadata": {
                "authority_subject": principal.subject_id,
                "authority_credential_id": principal.credential_id,
            },
            "payload": payload,
        }
        signature = self._signing_key.sign(branch_merge_authorization_signing_bytes(event))
        payload["signature"] = base64.b64encode(signature).decode("ascii")
        receipt = self._store.append_event(
            episode_id=episode_id,
            event_id=auth_id,
            event_type="branch_merge_authorization",
            payload=payload,
            idempotency_key=f"e09-authority:{auth_id}",
            expected_sequence=next_sequence - 1,
            actor_role="authorizer",
            causation_refs=sorted(evidence),
            payload_schema=AUTHORIZATION_PAYLOAD_SCHEMA,
            integrity_metadata=event["integrity_metadata"],
            protocol_version=STRICT_PROTOCOL_VERSION,
        )
        if receipt.sequence_no != next_sequence:
            raise E09AuthorityError("durable sequence differs from signed authorization sequence")
        return receipt
