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

from prototype.e09_e12a6_evidence_bridge import resolve_branch_merge_authorization, resolve_e09_reveal
from prototype.shared_evidence_protocol import (
    DOMAIN_BOUND_PROTOCOL_VERSION,
    STRICT_PROTOCOL_VERSION,
    EventReceipt,
    SQLiteEvidenceStore,
)
from prototype.e09_domain_registry import (
    E09DomainBinding, E09DomainRegistry, E09DomainRegistryError,
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
        domain_registry: E09DomainRegistry | None = None,
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
        if domain_registry is not None and not callable(getattr(domain_registry, "resolve", None)):
            raise TypeError("domain_registry must implement resolve")
        self._domain_registry = domain_registry

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

    def _trusted_domain(self, scope: str) -> E09DomainBinding:
        if self._domain_registry is None:
            raise E09AuthorizationError("trusted E09 domain registry is not configured")
        try:
            binding = self._domain_registry.resolve(scope)
        except Exception as exc:
            raise E09AuthorizationError("trusted domain registration is missing or revoked") from exc
        if not isinstance(binding, E09DomainBinding) or not binding.active:
            raise E09AuthorizationError("trusted domain registry returned an invalid or revoked binding")
        return binding

    @staticmethod
    def _domain_payload(binding: E09DomainBinding) -> dict[str, str]:
        return {
            "domain_id": binding.domain_id,
            "world_family": binding.world_family,
            "domain_registry_id": binding.registry_id,
            "domain_registry_version": binding.registry_version,
        }

    def append_observation(
        self,
        credential: object,
        *,
        episode_id: str,
        event_id: str,
        idempotency_key: str,
        payload: dict[str, Any],
        expected_sequence: int | None = None,
    ) -> EventReceipt:
        """Append a v0.4 observation with domain provenance derived by E09."""
        required = {"observation_id", "query_id", "scope", "split"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise E09AuthorizationError("observation request must use the exact v0.4 caller schema")
        scope = payload.get("scope")
        principal = self._principal(credential, role="observer", scope=scope)
        binding = self._trusted_domain(scope)
        event_payload = {**payload, **self._domain_payload(binding)}
        return self._store.append_event(
            episode_id=episode_id,
            event_id=event_id,
            event_type="observation",
            idempotency_key=idempotency_key,
            payload=event_payload,
            actor_role="observer",
            integrity_metadata=_identity_metadata(principal),
            payload_schema="observation@4",
            expected_sequence=expected_sequence,
            protocol_version=DOMAIN_BOUND_PROTOCOL_VERSION,
        )

    def append_prediction_commit(
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
        """Append a learner commit while copying domain provenance from its observation."""
        required = {
            "prediction_id", "observation_id", "model_version", "learner_track",
            "decision_status", "query_id", "scope", "split", "interop_commit_digest",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise E09AuthorizationError("prediction commit request must use the exact v0.4 caller schema")
        principal = self._principal(credential, role="learner", scope=payload.get("scope"))
        if not isinstance(causation_refs, (tuple, list)) or not all(
            isinstance(ref, str) and ref.strip() for ref in causation_refs
        ):
            raise E09AuthorizationError("prediction commit causation refs must be non-empty strings")
        events = self._store.replay_episode(episode_id)
        matches = [
            event for event in events
            if event.get("event_type") == "observation"
            and event.get("payload", {}).get("observation_id") == payload["observation_id"]
        ]
        if len(matches) != 1:
            raise E09AuthorizationError("prediction commit requires exactly one prior E09 observation")
        observation = matches[0]
        if observation.get("protocol_version") != DOMAIN_BOUND_PROTOCOL_VERSION:
            raise E09AuthorizationError("legacy v0.3 observations are quarantined from v0.4 commits")
        if observation.get("event_id") not in causation_refs:
            raise E09AuthorizationError("prediction commit must cite its observation event")
        observed = observation["payload"]
        for field in ("query_id", "scope", "split"):
            if payload[field] != observed[field]:
                raise E09AuthorizationError(f"prediction commit {field} differs from observation")
        current_binding = self._trusted_domain(payload["scope"])
        if self._domain_payload(current_binding) != {
            field: observed[field] for field in (
                "domain_id", "world_family", "domain_registry_id", "domain_registry_version",
            )
        }:
            raise E09AuthorizationError("observation domain provenance is no longer trusted")
        event_payload = {**payload, **{field: observed[field] for field in (
            "domain_id", "world_family", "domain_registry_id", "domain_registry_version",
        )}}
        return self._store.append_event(
            episode_id=episode_id,
            event_id=event_id,
            event_type="prediction_commit",
            idempotency_key=idempotency_key,
            payload=event_payload,
            actor_role="learner",
            causation_refs=causation_refs,
            integrity_metadata=_identity_metadata(principal),
            payload_schema="prediction_commit@4",
            expected_sequence=expected_sequence,
            protocol_version=DOMAIN_BOUND_PROTOCOL_VERSION,
        )

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
        """Append a reveal; v0.4 domain provenance is copied from trusted observation."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        scope = payload.get("scope")
        principal = self._principal(credential, role="evaluator", scope=scope)
        if self._domain_registry is None:
            # Compatibility path for quarantined v0.3 episodes only.
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

        required = {
            "prediction_id", "learner_track", "target_or_feedback", "query_id",
            "scope", "split", "commit_digest", "event_digest",
        }
        if set(payload) != required:
            raise E09AuthorizationError("reveal request must use the exact v0.4 caller schema")
        if not isinstance(causation_refs, (tuple, list)) or not all(
            isinstance(ref, str) and ref.strip() for ref in causation_refs
        ):
            raise E09AuthorizationError("reveal causation refs must be non-empty strings")
        events = self._store.replay_episode(episode_id)
        commits = [
            event for event in events
            if event.get("event_type") == "prediction_commit"
            and event.get("payload", {}).get("prediction_id") == payload["prediction_id"]
            and event.get("payload", {}).get("learner_track") == payload["learner_track"]
        ]
        if len(commits) != 1:
            raise E09AuthorizationError("reveal requires exactly one prior prediction commit")
        commit = commits[0]
        if commit.get("protocol_version") != DOMAIN_BOUND_PROTOCOL_VERSION:
            raise E09AuthorizationError("legacy v0.3 predictions are quarantined from v0.4 reveals")
        if commit.get("event_id") not in causation_refs:
            raise E09AuthorizationError("reveal must cite its prediction commit event")
        committed = commit["payload"]
        for field in ("query_id", "scope", "split"):
            if payload[field] != committed[field]:
                raise E09AuthorizationError(f"reveal {field} differs from prediction commit")
        current_binding = self._trusted_domain(scope)
        trusted = self._domain_payload(current_binding)
        if trusted != {field: committed[field] for field in trusted}:
            raise E09AuthorizationError("prediction domain provenance is no longer trusted")
        event_payload = {**payload, **trusted}
        return self._store.append_event(
            episode_id=episode_id,
            event_id=event_id,
            event_type="evidence_reveal",
            idempotency_key=idempotency_key,
            payload=event_payload,
            actor_role="evaluator",
            causation_refs=causation_refs,
            integrity_metadata=_identity_metadata(principal),
            payload_schema="evidence_reveal@4",
            expected_sequence=expected_sequence,
            protocol_version=DOMAIN_BOUND_PROTOCOL_VERSION,
        )

    def issue_branch_merge_authorization(
        self,
        credential: object,
        *,
        episode_id: str,
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
        receipt_signer: E09GrantSigner | None = None,
        receipt_ttl: timedelta = timedelta(minutes=1),
        domain_registry: E09DomainRegistry | None = None,
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
        if receipt_signer is not None and not callable(getattr(receipt_signer, "sign", None)):
            raise TypeError("receipt_signer must implement sign")
        if not isinstance(receipt_ttl, timedelta) or receipt_ttl <= timedelta(0):
            raise ValueError("receipt_ttl must be a positive timedelta")
        self._clock = clock or SystemUTCClock()
        self._receipt_signer = receipt_signer
        self._receipt_ttl = receipt_ttl
        if domain_registry is not None and not callable(getattr(domain_registry, "resolve", None)):
            raise TypeError("domain_registry must implement resolve")
        self._domain_registry = domain_registry

    def verify_branch_merge_authorization(self, **request: Any):
        """Verify with the service clock; caller-supplied now is rejected."""
        if "now" in request:
            raise E09AuthorizationError("verification time is controlled by the verifier service")
        if "world_family_by_evidence" in request:
            raise E09AuthorizationError("world-family overrides are forbidden; E09 derives domain from observations")
        current = self._clock.now()
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise E09AuthenticationError("verifier clock must return a timezone-aware datetime")
        return resolve_branch_merge_authorization(
            self._store,
            signature_verifier=self._signature_verifier,
            verifier_id=self.verifier_id,
            now=current,
            domain_registry=self._domain_registry,
            **request,
        )

    def issue_verification_receipt(self, **request: Any) -> dict[str, Any]:
        """Verify a grant and issue a signed receipt for all candidate evidence refs."""
        if self._receipt_signer is None:
            raise E09AuthorizationError("verifier receipt signer is not configured")
        if self._domain_registry is None:
            raise E09AuthorizationError("trusted E09 domain registry is required for verification receipts")
        forbidden = {"candidate_evidence_world_family_by_ref", "world_family_by_evidence"}
        if forbidden.intersection(request):
            raise E09AuthorizationError("caller-supplied world-family overrides are forbidden")
        receipt_only_fields = {"candidate_evidence_refs"}
        verification_request = {
            key: value for key, value in request.items() if key not in receipt_only_fields
        }
        permit = self.verify_branch_merge_authorization(**verification_request)
        current = self._clock.now()
        if not isinstance(current, datetime) or current.tzinfo is None:
            raise E09AuthenticationError("verifier clock must return a timezone-aware datetime")
        current = current.astimezone(timezone.utc)
        episode_id = request["episode_id"]
        authorization_ref = request["authorization_ref"]
        events = self._store.replay_episode(episode_id)
        matches = [event for event in events if event.get("event_id") == authorization_ref]
        if len(matches) != 1:
            raise E09AuthenticationError("verified authorization event disappeared from E09 replay")
        grant_payload = matches[0]["payload"]
        grant_expiry = datetime.fromisoformat(grant_payload["expires_at"].replace("Z", "+00:00"))
        expires_at = min(grant_expiry, current + self._receipt_ttl)
        if expires_at <= current:
            raise E09AuthorizationError("grant expires before a verifier receipt can be issued")

        candidate_refs = request.get("candidate_evidence_refs", permit.evidence_refs)
        if (not isinstance(candidate_refs, (tuple, list)) or not candidate_refs
                or any(not isinstance(ref, str) or not ref.strip() for ref in candidate_refs)
                or len(candidate_refs) != len(set(candidate_refs))):
            raise E09AuthorizationError("candidate_evidence_refs must be a non-empty unique reference list")
        all_evidence_refs = tuple(sorted(candidate_refs))
        if not set(permit.evidence_refs).issubset(set(all_evidence_refs)):
            raise E09AuthorizationError("candidate evidence refs must include all authorization evidence refs")
        evidence = []
        for ref in all_evidence_refs:
            item = resolve_e09_reveal(
                self._store,
                episode_id=episode_id,
                evidence_ref=ref,
                scope=request["scope"],
                learner_track=request["learner_track"],
                domain_registry=self._domain_registry,
            )
            evidence.append({
                "evidence_id": item.evidence_id,
                "episode_id": item.episode_id,
                "world_family": item.world_family,
                "split_role": item.split_role.value,
                "observation_id": item.observation_id,
                "outcome": item.outcome,
                "model_version": item.model_version,
                "measurement_cost": item.measurement_cost,
                "prediction_commit_step": item.prediction_commit_step,
                "label_visibility_step": item.label_visibility_step,
                "provenance": item.provenance,
                "domain_id": item.domain_id,
                "domain_registry_id": item.domain_registry_id,
                "domain_registry_version": item.domain_registry_version,
            })

        receipt = {
            "schema_version": "e09_verification_receipt@2",
            "receipt_id": secrets.token_hex(16),
            "nonce": secrets.token_urlsafe(32),
            "audience": "e12a6-lifecycle-writer",
            "verifier_id": self.verifier_id,
            "episode_id": episode_id,
            "authorization_ref": authorization_ref,
            "scope": request["scope"],
            "parent_state_ref": request["parent_state_ref"],
            "branch_ids": list(permit.branch_ids),
            "authorization_evidence_refs": list(permit.evidence_refs),
            "evidence_refs": list(all_evidence_refs),
            "issuer_id": permit.issuer_id,
            "authorization_event_digest": permit.event_digest,
            "issued_at": current.isoformat(),
            "expires_at": expires_at.isoformat(),
            "evidence": evidence,
            "signature_algorithm": "Ed25519",
            "signature": "",
        }
        from prototype.e09_verification_receipt import verification_receipt_signing_bytes

        signature = self._receipt_signer.sign(
            self.verifier_id, verification_receipt_signing_bytes(receipt)
        )
        if not isinstance(signature, str) or not signature.strip():
            raise E09AuthenticationError("verifier receipt signer returned an invalid signature")
        receipt["signature"] = signature
        return receipt
