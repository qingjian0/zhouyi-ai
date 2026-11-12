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
    STRICT_PROTOCOL_VERSION,
    EventReceipt,
    EvidenceEpisodeReader,
    SQLiteEvidenceStore,
    digest_payload,
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




@dataclass(frozen=True)
class E09DomainBinding:
    """Versioned domain attribution resolved by the trusted E09 registry."""

    world_family: str
    registry_id: str
    registry_version: str

    def __post_init__(self) -> None:
        for field in ("world_family", "registry_id", "registry_version"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string")


class E09DomainRegistry(Protocol):
    """Trusted, versioned mapping from an observation context to its domain."""

    def resolve(self, *, episode_id: str, scope: str, observation_id: str) -> E09DomainBinding:
        ...


class E09LearnerBindingResolver(Protocol):
    """Trusted mapping from an experiment track to its assigned learner workload."""

    def resolve(
        self, *, episode_id: str, scope: str, learner_track: str
    ) -> str:
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
        learner_binding_resolver: E09LearnerBindingResolver | None = None,
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
        if learner_binding_resolver is not None and not callable(
            getattr(learner_binding_resolver, "resolve", None)
        ):
            raise TypeError("learner_binding_resolver must implement resolve")
        self._learner_binding_resolver = learner_binding_resolver

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

    def validate_adapter_workloads(
        self,
        *,
        scope: str,
        observer_credential: object,
        learner_credential: object,
        evaluator_credential: object,
    ) -> None:
        """Fail fast unless all three adapter workload identities are authorized."""
        if self._domain_registry is None:
            raise E09AuthorizationError("trusted E09 domain registry is not configured")
        self._principal(observer_credential, role="observer", scope=scope)
        self._principal(learner_credential, role="learner", scope=scope)
        self._principal(evaluator_credential, role="evaluator", scope=scope)

    def _principal_any(
        self, credential: object, *, roles: frozenset[str], scope: str
    ) -> E09AuthenticatedWorkload:
        if not isinstance(scope, str) or not scope.strip():
            raise E09AuthorizationError("scope must be a non-empty string")
        try:
            principal = self._authenticator.authenticate(credential)
        except Exception as exc:
            raise E09AuthenticationError("workload authentication failed") from exc
        if not isinstance(principal, E09AuthenticatedWorkload):
            raise E09AuthenticationError("authenticator returned an invalid workload identity")
        if not roles.intersection(principal.roles):
            raise E09AuthorizationError("workload lacks a permitted role")
        if scope not in principal.scopes:
            raise E09AuthorizationError("workload is not authorized for the requested scope")
        return principal

    def _resolve_learner_binding(
        self, *, episode_id: str, scope: str, learner_track: str
    ) -> str:
        if not isinstance(learner_track, str) or not learner_track.strip():
            raise E09AuthorizationError("learner_track must be a non-empty string")
        if self._learner_binding_resolver is None:
            raise E09AuthorizationError("trusted learner binding resolver is not configured")
        try:
            workload_id = self._learner_binding_resolver.resolve(
                episode_id=episode_id, scope=scope, learner_track=learner_track
            )
        except Exception as exc:
            raise E09AuthorizationError(
                "no trusted learner workload is assigned to this episode/scope/track"
            ) from exc
        if not isinstance(workload_id, str) or not workload_id.strip():
            raise E09AuthenticationError("learner binding resolver returned an invalid workload ID")
        return workload_id

    def _require_learner_assignment(
        self,
        principal: E09AuthenticatedWorkload,
        *,
        episode_id: str,
        scope: str,
        learner_track: str,
    ) -> None:
        expected = self._resolve_learner_binding(
            episode_id=episode_id, scope=scope, learner_track=learner_track
        )
        if principal.workload_id != expected:
            raise E09AuthorizationError("workload is not assigned to the requested learner track")

    def put_observation_input(
        self, credential: object, *, scope: str, payload: Any
    ) -> str:
        """Persist an observer input through Authority and return its content digest."""
        self._principal(credential, role="observer", scope=scope)
        payload_ref = digest_payload(payload)
        self._store.put_payload(payload_ref, payload)
        return payload_ref

    def read_observation_input(
        self,
        credential: object,
        *,
        episode_id: str,
        observation_id: str,
        scope: str,
    ) -> Any:
        """Return input only to an authorized observer/learner after Observation exists."""
        principal = self._principal_any(
            credential, roles=frozenset({"observer", "learner"}), scope=scope
        )
        events = self._store.replay_episode(episode_id)
        matches = [
            event for event in events
            if event.get("event_type") == "observation"
            and event.get("payload", {}).get("observation_id") == observation_id
        ]
        if len(matches) != 1:
            raise E09AuthorizationError("input read requires exactly one prior Observation")
        event = matches[0]
        if "learner" in principal.roles:
            self._require_learner_assignment(
                principal,
                episode_id=episode_id,
                scope=scope,
                learner_track=event.get("payload", {}).get("learner_track"),
            )
        if (
            event.get("actor_role") != "observer"
            or event.get("payload", {}).get("scope") != scope
            or (
                "learner" in principal.roles
                and event.get("payload", {}).get("learner_workload_id") != principal.workload_id
            )
            or not isinstance(
                event.get("integrity_metadata", {}).get("authenticated_workload"), dict
            )
        ):
            raise E09AuthorizationError("Observation is outside the authenticated input boundary")
        payload_ref = event.get("payload", {}).get("payload_ref")
        if not isinstance(payload_ref, str) or not payload_ref:
            raise E09AuthorizationError("Observation has no durable input payload reference")
        return self._store.get_payload(payload_ref)

    def read_learner_episode(
        self,
        credential: object,
        *,
        episode_id: str,
        scope: str,
        learner_track: str,
    ) -> list[dict[str, Any]]:
        """Return a learner-safe, provenance-checked event projection for ZPCM sync."""
        principal = self._principal(credential, role="learner", scope=scope)
        self._require_learner_assignment(
            principal, episode_id=episode_id, scope=scope, learner_track=learner_track
        )
        events = self._store.replay_episode(episode_id)
        by_id = {event.get("event_id"): event for event in events}
        own_commit_ids: set[str] = set()
        own_observation_ids: set[str] = set()
        for event in events:
            if event.get("event_type") != "prediction_commit":
                continue
            payload = event.get("payload", {})
            workload = event.get("integrity_metadata", {}).get("authenticated_workload", {})
            causes = event.get("causation_refs", [])
            if (
                event.get("actor_role") != "learner"
                or payload.get("scope") != scope
                or payload.get("learner_track") != learner_track
                or not isinstance(workload, dict)
                or workload.get("workload_id") != principal.workload_id
                or not isinstance(causes, list)
                or len(causes) != 1
            ):
                continue
            observation = by_id.get(causes[0])
            if not isinstance(observation, dict) or observation.get("event_type") != "observation":
                continue
            observation_payload = observation.get("payload", {})
            observation_workload = observation.get("integrity_metadata", {}).get(
                "authenticated_workload", {}
            )
            if (
                observation.get("actor_role") != "observer"
                or observation_payload.get("scope") != scope
                or observation_payload.get("learner_track") != learner_track
                or observation_payload.get("learner_workload_id") != principal.workload_id
                or observation_payload.get("split") != payload.get("split")
                or observation_payload.get("observation_id") != payload.get("observation_id")
                or observation_payload.get("query_id") != payload.get("query_id")
                or not isinstance(observation_workload, dict)
                or not isinstance(observation_workload.get("workload_id"), str)
            ):
                continue
            own_commit_ids.add(event.get("event_id"))
            own_observation_ids.add(observation.get("event_id"))

        own_reveal_ids: set[str] = set()
        for reveal in events:
            if reveal.get("event_type") != "evidence_reveal":
                continue
            reveal_payload = reveal.get("payload", {})
            reveal_workload = reveal.get("integrity_metadata", {}).get(
                "authenticated_workload", {}
            )
            reveal_causes = reveal.get("causation_refs", [])
            if (
                reveal.get("actor_role") != "evaluator"
                or not isinstance(reveal_workload, dict)
                or not isinstance(reveal_workload.get("workload_id"), str)
                or reveal_payload.get("scope") != scope
                or reveal_payload.get("split") != "SUPPORT"
                or reveal_payload.get("learner_track") != learner_track
                or not isinstance(reveal_causes, list)
                or len(reveal_causes) != 1
                or reveal_causes[0] not in own_commit_ids
            ):
                continue
            commit = by_id.get(reveal_causes[0])
            commit_payload = commit.get("payload", {}) if isinstance(commit, dict) else {}
            if (
                not isinstance(commit, dict)
                or commit_payload.get("split") != "SUPPORT"
                or reveal_payload.get("prediction_id") != commit_payload.get("prediction_id")
                or reveal_payload.get("query_id") != commit_payload.get("query_id")
                or reveal_payload.get("learner_track") != commit_payload.get("learner_track")
                or reveal_payload.get("commit_digest") != commit_payload.get("interop_commit_digest")
                or reveal_payload.get("event_digest") != commit.get("payload_digest")
            ):
                continue
            own_reveal_ids.add(reveal.get("event_id"))
        expected_roles = {
            "observation": "observer",
            "prediction_commit": "learner",
            "evidence_reveal": "evaluator",
            "structure_version": "learner",
            "revision": "learner",
        }
        projection: list[dict[str, Any]] = []
        for event in events:
            event_type = event.get("event_type")
            if event_type not in expected_roles:
                continue
            payload = event.get("payload", {})
            if payload.get("scope") != scope:
                continue
            if event_type == "prediction_commit" and event.get("event_id") not in own_commit_ids:
                continue
            if event_type == "observation" and (
                event.get("event_id") not in own_observation_ids
                or payload.get("learner_workload_id") != principal.workload_id
            ):
                continue
            if event_type == "evidence_reveal" and event.get("event_id") not in own_reveal_ids:
                continue
            event_workload = event.get("integrity_metadata", {}).get("authenticated_workload", {})
            if event_type in {"structure_version", "revision"} and (
                not isinstance(event_workload, dict)
                or event_workload.get("workload_id") != principal.workload_id
            ):
                continue
            event_track = payload.get("learner_track")
            if event_track != learner_track:
                continue
            authenticated_workload = event.get("integrity_metadata", {}).get(
                "authenticated_workload"
            )
            if (
                event.get("actor_role") != expected_roles[event_type]
                or not isinstance(authenticated_workload, dict)
                or not isinstance(authenticated_workload.get("workload_id"), str)
            ):
                raise E09AuthorizationError(
                    "learner replay encountered an event outside the authenticated role boundary"
                )
            safe_payload = dict(payload)
            if event_type == "evidence_reveal":
                safe_payload.pop("target_or_feedback", None)
                safe_payload.pop("reveal_source", None)
            if event_type == "structure_version":
                definition = safe_payload.get("definition")
                if isinstance(definition, dict):
                    definition = dict(definition)
                    definition.pop("snapshot", None)
                    definition.pop("ledger_snapshot", None)
                    safe_payload["definition"] = definition
            safe_payload.pop("raw_input", None)
            safe_payload.pop("target_or_feedback", None)
            safe_payload.pop("reveal_source", None)
            projection.append({
                "event_id": event["event_id"],
                "event_type": event_type,
                "protocol_version": event.get("protocol_version"),
                "sequence_no": event.get("sequence_no"),
                "payload_digest": event.get("payload_digest"),
                "payload": safe_payload,
            })
        return projection

    def read_support_feedback(
        self,
        credential: object,
        *,
        episode_id: str,
        reveal_event_id: str,
        scope: str,
    ) -> dict[str, Any]:
        """Release only lineage-verified SUPPORT feedback to the authorized learner."""
        principal = self._principal(credential, role="learner", scope=scope)
        events = self._store.replay_episode(episode_id)
        by_id = {event.get("event_id"): event for event in events}
        reveal = by_id.get(reveal_event_id)
        if not isinstance(reveal, dict) or reveal.get("event_type") != "evidence_reveal":
            raise E09AuthorizationError("support feedback requires a durable Evidence Reveal")
        reveal_payload = reveal.get("payload", {})
        if (
            reveal.get("actor_role") != "evaluator"
            or reveal_payload.get("scope") != scope
            or reveal_payload.get("split") != "SUPPORT"
            or not isinstance(
                reveal.get("integrity_metadata", {}).get("authenticated_workload"), dict
            )
        ):
            raise E09AuthorizationError("only authenticated SUPPORT feedback is readable by Learner")
        reveal_causes = reveal.get("causation_refs", [])
        if not isinstance(reveal_causes, list) or len(reveal_causes) != 1:
            raise E09AuthorizationError("Evidence Reveal must reference exactly one Prediction Commit")
        commit = by_id.get(reveal_causes[0])
        if not isinstance(commit, dict) or commit.get("event_type") != "prediction_commit":
            raise E09AuthorizationError("Evidence Reveal has no durable Prediction Commit")
        commit_payload = commit.get("payload", {})
        self._require_learner_assignment(
            principal, episode_id=episode_id, scope=scope,
            learner_track=commit_payload.get("learner_track"),
        )
        if (
            commit.get("actor_role") != "learner"
            or commit_payload.get("scope") != scope
            or commit_payload.get("split") != "SUPPORT"
            or not isinstance(
                commit.get("integrity_metadata", {}).get("authenticated_workload"), dict
            )
            or commit.get("integrity_metadata", {}).get("authenticated_workload", {}).get("workload_id")
                != principal.workload_id
            or reveal_payload.get("prediction_id") != commit_payload.get("prediction_id")
            or reveal_payload.get("query_id") != commit_payload.get("query_id")
            or reveal_payload.get("learner_track") != commit_payload.get("learner_track")
            or reveal_payload.get("commit_digest") != commit_payload.get("interop_commit_digest")
            or reveal_payload.get("event_digest") != commit.get("payload_digest")
        ):
            raise E09AuthorizationError("Evidence Reveal does not match its authenticated SUPPORT Commit")
        commit_causes = commit.get("causation_refs", [])
        if not isinstance(commit_causes, list) or len(commit_causes) != 1:
            raise E09AuthorizationError("Prediction Commit must reference exactly one Observation")
        observation = by_id.get(commit_causes[0])
        if not isinstance(observation, dict) or observation.get("event_type") != "observation":
            raise E09AuthorizationError("Prediction Commit has no durable Observation")
        observation_payload = observation.get("payload", {})
        if (
            observation.get("actor_role") != "observer"
            or observation_payload.get("scope") != scope
            or observation_payload.get("split") != "SUPPORT"
            or observation_payload.get("observation_id") != commit_payload.get("observation_id")
            or observation_payload.get("query_id") != commit_payload.get("query_id")
            or observation_payload.get("learner_track") != commit_payload.get("learner_track")
            or observation_payload.get("learner_workload_id") != principal.workload_id
            or not isinstance(
                observation.get("integrity_metadata", {}).get("authenticated_workload"), dict
            )
        ):
            raise E09AuthorizationError("Prediction Commit is not grounded in an authenticated SUPPORT Observation")
        feedback = reveal_payload.get("target_or_feedback")
        if feedback is None:
            raise E09AuthorizationError("Evidence Reveal contains no SUPPORT feedback")
        return {
            "reveal_event_id": reveal_event_id,
            "prediction_id": reveal_payload["prediction_id"],
            "query_id": reveal_payload["query_id"],
            "learner_track": reveal_payload["learner_track"],
            "feedback": feedback,
        }

    def append_observation(
        self,
        credential: object,
        *,
        episode_id: str,
        event_id: str,
        idempotency_key: str,
        observation_id: str,
        query_id: str,
        scope: str,
        split: str,
        payload_ref: str | None = None,
        feature_schema_version: str | None = None,
        learner_track: str,
        causation_refs: tuple[str, ...] | list[str] = (),
        expected_sequence: int | None = None,
    ) -> EventReceipt:
        """Append an observation with domain attribution derived from the trusted registry."""
        if self._domain_registry is None:
            raise E09AuthorizationError("trusted E09 domain registry is not configured")
        principal = self._principal(credential, role="observer", scope=scope)
        binding = self._domain_registry.resolve(
            episode_id=episode_id, scope=scope, observation_id=observation_id
        )
        if not isinstance(binding, E09DomainBinding):
            raise E09AuthenticationError("domain registry returned an invalid binding")
        payload = {
            "observation_id": observation_id,
            "query_id": query_id,
            "scope": scope,
            "split": split,
            "domain_provenance_schema": "e09-domain-provenance@1",
            "domain_registry_id": binding.registry_id,
            "domain_registry_version": binding.registry_version,
            "world_family": binding.world_family,
        }
        for field, value in (
            ("payload_ref", payload_ref),
            ("feature_schema_version", feature_schema_version),
        ):
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise E09AuthorizationError(f"{field} must be a non-empty string")
                payload[field] = value
        learner_workload_id = self._resolve_learner_binding(
            episode_id=episode_id, scope=scope, learner_track=learner_track
        )
        payload["learner_track"] = learner_track
        payload["learner_workload_id"] = learner_workload_id
        if payload_ref is not None:
            try:
                self._store.get_payload(payload_ref)
            except Exception as exc:
                raise E09AuthorizationError(
                    "observation payload_ref must reference an existing digest-verified payload"
                ) from exc
        return self._store.append_event(
            episode_id=episode_id, event_id=event_id, event_type="observation",
            idempotency_key=idempotency_key, payload=payload,
            actor_role="observer", causation_refs=causation_refs,
            integrity_metadata=_identity_metadata(principal),
            expected_sequence=expected_sequence, protocol_version=STRICT_PROTOCOL_VERSION,
        )

    def _observation_domain(self, episode_id: str, observation_id: str) -> dict[str, str]:
        events = self._store.replay_episode(episode_id)
        matches = [
            event for event in events
            if event.get("event_type") == "observation"
            and event.get("payload", {}).get("observation_id") == observation_id
        ]
        if len(matches) != 1:
            raise E09AuthorizationError("prediction requires exactly one prior observation")
        observation = matches[0]
        payload = observation.get("payload", {})
        identity = observation.get("integrity_metadata", {}).get("authenticated_workload")
        fields = (
            "domain_provenance_schema", "domain_registry_id",
            "domain_registry_version", "world_family",
        )
        if (observation.get("actor_role") != "observer"
                or not isinstance(identity, dict)
                or payload.get("domain_provenance_schema") != "e09-domain-provenance@1"
                or any(not isinstance(payload.get(field), str) or not payload[field].strip()
                       for field in fields[1:])):
            raise E09AuthorizationError("observation has no authenticated domain provenance")
        return {field: payload[field] for field in fields}

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
        """Append a learner commit while binding domain metadata from its Observation."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        scope = payload.get("scope")
        principal = self._principal(credential, role="learner", scope=scope)
        self._require_learner_assignment(
            principal, episode_id=episode_id, scope=scope,
            learner_track=payload.get("learner_track"),
        )
        events = self._store.replay_episode(episode_id)
        observation_id = payload.get("observation_id")
        observations = [
            event for event in events
            if event.get("event_type") == "observation"
            and event.get("payload", {}).get("observation_id") == observation_id
        ]
        if len(observations) != 1:
            raise E09AuthorizationError("prediction requires exactly one prior observation")
        observation = observations[0]
        observation_payload = observation.get("payload", {})
        observation_workload = observation.get("integrity_metadata", {}).get(
            "authenticated_workload", {}
        )
        if (
            observation_payload.get("scope") != scope
            or observation_payload.get("split") != payload.get("split")
            or observation_payload.get("learner_track") != payload.get("learner_track")
            or observation_payload.get("learner_workload_id") != principal.workload_id
            or observation.get("actor_role") != "observer"
            or not isinstance(observation_workload, dict)
            or not isinstance(observation_workload.get("workload_id"), str)
            or observation.get("event_id") not in set(causation_refs)
        ):
            raise E09AuthorizationError(
                "prediction must causally reference an Observation assigned to this learner in the same scope, track and split"
            )
        domain = self._observation_domain(episode_id, observation_id)
        normalized = dict(payload)
        for field, value in domain.items():
            if field in normalized and normalized[field] != value:
                raise E09AuthorizationError(f"prediction commit cannot override {field}")
            normalized[field] = value
        return self._store.append_event(
            episode_id=episode_id, event_id=event_id, event_type="prediction_commit",
            idempotency_key=idempotency_key, payload=normalized,
            actor_role="learner", causation_refs=causation_refs,
            integrity_metadata=_identity_metadata(principal),
            expected_sequence=expected_sequence, protocol_version=STRICT_PROTOCOL_VERSION,
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
        """Append an evaluator reveal; the event role is derived, never supplied."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        scope = payload.get("scope")
        principal = self._principal(credential, role="evaluator", scope=scope)
        events = self._store.replay_episode(episode_id)
        prediction_id = payload.get("prediction_id")
        learner_track = payload.get("learner_track")
        commits = [
            event for event in events
            if event.get("event_type") == "prediction_commit"
            and event.get("payload", {}).get("prediction_id") == prediction_id
            and event.get("payload", {}).get("learner_track") == learner_track
        ]
        if len(commits) != 1:
            raise E09AuthorizationError("reveal requires exactly one committed prediction")
        commit = commits[0]
        if (commit.get("payload", {}).get("scope") != scope
                or commit.get("event_id") not in set(causation_refs)):
            raise E09AuthorizationError("reveal must causally reference a commit in the same scope")
        domain = self._observation_domain(episode_id, commit["payload"].get("observation_id"))
        normalized = dict(payload)
        for field, value in domain.items():
            if field in normalized and normalized[field] != value:
                raise E09AuthorizationError(f"evidence reveal cannot override {field}")
            if commit["payload"].get(field) != value:
                raise E09AuthorizationError(f"prediction commit {field} does not match its observation")
            normalized[field] = value
        return self._store.append_event(
            episode_id=episode_id,
            event_id=event_id,
            event_type="evidence_reveal",
            idempotency_key=idempotency_key,
            payload=normalized,
            actor_role="evaluator",
            causation_refs=causation_refs,
            integrity_metadata=_identity_metadata(principal),
            expected_sequence=expected_sequence,
            protocol_version=STRICT_PROTOCOL_VERSION,
        )

    def append_structure_version(
        self,
        credential: object,
        *,
        episode_id: str,
        event_id: str,
        idempotency_key: str,
        scope: str,
        learner_track: str,
        payload: dict[str, Any],
        causation_refs: tuple[str, ...] | list[str] = (),
        expected_sequence: int | None = None,
    ) -> EventReceipt:
        """Append a learner structure checkpoint after validating its causal support."""
        principal = self._principal(credential, role="learner", scope=scope)
        self._require_learner_assignment(
            principal, episode_id=episode_id, scope=scope, learner_track=learner_track
        )
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        normalized = dict(payload)
        if normalized.get("scope", scope) != scope:
            raise E09AuthorizationError("structure version scope does not match authenticated scope")
        if normalized.get("learner_track", learner_track) != learner_track:
            raise E09AuthorizationError("structure version learner_track mismatch")
        normalized["scope"] = scope
        normalized["learner_track"] = learner_track
        required = {"structure_id", "version_id", "kind", "definition",
                    "parent_version_ids", "support_evidence_ids"}
        if not required.issubset(normalized):
            raise E09AuthorizationError(
                f"structure version missing fields: {sorted(required - normalized.keys())}"
            )
        for field in ("structure_id", "version_id", "kind"):
            if not isinstance(normalized[field], str) or not normalized[field].strip():
                raise E09AuthorizationError(f"structure version {field} must be non-empty")
        if not isinstance(normalized["definition"], dict):
            raise E09AuthorizationError("structure version definition must be an object")
        parents = normalized["parent_version_ids"]
        supports = normalized["support_evidence_ids"]
        if (not isinstance(parents, (tuple, list))
                or any(not isinstance(x, str) or not x.strip() for x in parents)
                or len(parents) != len(set(parents))):
            raise E09AuthorizationError("parent_version_ids must be unique non-empty strings")
        if (not isinstance(supports, (tuple, list))
                or any(not isinstance(x, str) or not x.strip() for x in supports)
                or len(supports) != len(set(supports))):
            raise E09AuthorizationError("support_evidence_ids must be unique non-empty strings")
        causes = tuple(causation_refs)
        if len(causes) != len(set(causes)) or any(not isinstance(x, str) or not x.strip() for x in causes):
            raise E09AuthorizationError("causation_refs must be unique non-empty strings")
        if not set(supports).issubset(set(causes)):
            raise E09AuthorizationError("every support evidence reference must be a causal reference")
        events = self._store.replay_episode(episode_id)
        structures = {
            event["payload"].get("version_id"): event
            for event in events if event.get("event_type") == "structure_version"
        }
        reveals = {
            event.get("event_id"): event
            for event in events if event.get("event_type") == "evidence_reveal"
        }
        if bool(parents) != bool(supports):
            raise E09AuthorizationError("non-bootstrap structure versions require both parents and support evidence")
        for parent_id in parents:
            parent = structures.get(parent_id)
            if (parent is None
                    or parent.get("actor_role") != "learner"
                    or not isinstance(parent.get("integrity_metadata", {}).get("authenticated_workload"), dict)
                    or parent.get("integrity_metadata", {}).get("authenticated_workload", {}).get("workload_id")
                        != principal.workload_id
                    or parent["payload"].get("structure_id") != normalized["structure_id"]
                    or parent["payload"].get("learner_track") != learner_track
                    or parent["payload"].get("scope") != scope):
                raise E09AuthorizationError("parent structure version is missing or outside the authorized scope/track")
        for evidence_id in supports:
            reveal = reveals.get(evidence_id)
            if (reveal is None
                    or reveal.get("actor_role") != "evaluator"
                    or not isinstance(reveal.get("integrity_metadata", {}).get("authenticated_workload"), dict)
                    or reveal["payload"].get("scope") != scope
                    or reveal["payload"].get("learner_track") != learner_track):
                raise E09AuthorizationError("support evidence is missing or outside the authorized scope/track")
            self.read_support_feedback(
                credential, episode_id=episode_id, reveal_event_id=evidence_id, scope=scope
            )
        return self._store.append_event(
            episode_id=episode_id, event_id=event_id, event_type="structure_version",
            idempotency_key=idempotency_key, payload=normalized,
            actor_role="learner", causation_refs=causes,
            integrity_metadata=_identity_metadata(principal),
            expected_sequence=expected_sequence, protocol_version=STRICT_PROTOCOL_VERSION,
        )

    def append_revision(
        self,
        credential: object,
        *,
        episode_id: str,
        event_id: str,
        idempotency_key: str,
        scope: str,
        learner_track: str,
        payload: dict[str, Any],
        causation_refs: tuple[str, ...] | list[str],
        expected_sequence: int | None = None,
    ) -> EventReceipt:
        """Append a learner revision bound to prior reveals and structure versions."""
        principal = self._principal(credential, role="learner", scope=scope)
        self._require_learner_assignment(
            principal, episode_id=episode_id, scope=scope, learner_track=learner_track
        )
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dictionary")
        normalized = dict(payload)
        if normalized.get("scope", scope) != scope:
            raise E09AuthorizationError("revision scope does not match authenticated scope")
        if normalized.get("learner_track", learner_track) != learner_track:
            raise E09AuthorizationError("revision learner_track mismatch")
        normalized["scope"] = scope
        normalized["learner_track"] = learner_track
        required = {"revision_id", "operation", "trigger_evidence_ids",
                    "before_version_ids", "after_version_ids"}
        if not required.issubset(normalized):
            raise E09AuthorizationError(f"revision missing fields: {sorted(required - normalized.keys())}")
        for field in ("revision_id", "operation"):
            if not isinstance(normalized[field], str) or not normalized[field].strip():
                raise E09AuthorizationError(f"revision {field} must be non-empty")
        triggers = normalized["trigger_evidence_ids"]
        before = normalized["before_version_ids"]
        after = normalized["after_version_ids"]
        for field, values in (("trigger_evidence_ids", triggers),
                              ("before_version_ids", before), ("after_version_ids", after)):
            if (not isinstance(values, (tuple, list)) or not values
                    or any(not isinstance(x, str) or not x.strip() for x in values)
                    or len(values) != len(set(values))):
                raise E09AuthorizationError(f"{field} must be unique non-empty strings")
        causes = tuple(causation_refs)
        if len(causes) != len(set(causes)) or any(not isinstance(x, str) or not x.strip() for x in causes):
            raise E09AuthorizationError("causation_refs must be unique non-empty strings")
        if not set(triggers).issubset(set(causes)):
            raise E09AuthorizationError("every trigger evidence reference must be a causal reference")
        events = self._store.replay_episode(episode_id)
        reveals = {
            event.get("event_id"): event
            for event in events if event.get("event_type") == "evidence_reveal"
        }
        structures = {
            event["payload"].get("version_id"): event
            for event in events if event.get("event_type") == "structure_version"
        }
        for evidence_id in triggers:
            reveal = reveals.get(evidence_id)
            if (reveal is None
                    or reveal.get("actor_role") != "evaluator"
                    or not isinstance(reveal.get("integrity_metadata", {}).get("authenticated_workload"), dict)
                    or reveal["payload"].get("scope") != scope
                    or reveal["payload"].get("learner_track") != learner_track):
                raise E09AuthorizationError("revision trigger evidence is missing or outside the authorized scope/track")
            self.read_support_feedback(
                credential, episode_id=episode_id, reveal_event_id=evidence_id, scope=scope
            )
        before_events = [structures.get(version_id) for version_id in before]
        after_events = [structures.get(version_id) for version_id in after]
        if any(event is None for event in before_events + after_events):
            raise E09AuthorizationError("revision references an unknown structure version")
        structure_ids = {
            event["payload"].get("structure_id") for event in before_events + after_events
        }
        if len(structure_ids) != 1 or any(
            event.get("actor_role") != "learner"
            or not isinstance(event.get("integrity_metadata", {}).get("authenticated_workload"), dict)
            or event.get("integrity_metadata", {}).get("authenticated_workload", {}).get("workload_id")
                != principal.workload_id
            or event["payload"].get("learner_track") != learner_track
            or event["payload"].get("scope") != scope
            for event in before_events + after_events
        ):
            raise E09AuthorizationError("revision structure versions cross scope, track, or structure boundaries")
        after_event_ids = {event["event_id"] for event in after_events}
        if not after_event_ids.issubset(set(causes)):
            raise E09AuthorizationError("revision causation must include its resulting structure version events")
        before_ids = set(before)
        for after_event in after_events:
            after_payload = after_event["payload"]
            if (not before_ids.intersection(set(after_payload.get("parent_version_ids", [])))
                    or not set(triggers).issubset(set(after_payload.get("support_evidence_ids", [])))):
                raise E09AuthorizationError(
                    "resulting structure version must descend from the declared parent and cite every trigger"
                )
        return self._store.append_event(
            episode_id=episode_id, event_id=event_id, event_type="revision",
            idempotency_key=idempotency_key, payload=normalized,
            actor_role="learner", causation_refs=causes,
            integrity_metadata=_identity_metadata(principal),
            expected_sequence=expected_sequence, protocol_version=STRICT_PROTOCOL_VERSION,
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
        store: EvidenceEpisodeReader,
        *,
        signature_verifier: Callable[[str, str, bytes, str], bool],
        verifier_id: str,
        clock: E09Clock | None = None,
        receipt_signer: E09GrantSigner | None = None,
        receipt_ttl: timedelta = timedelta(minutes=1),
    ) -> None:
        if not callable(getattr(store, "replay_episode", None)):
            raise TypeError("store must implement the read-only replay_episode interface")
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

    def issue_verification_receipt(self, **request: Any) -> dict[str, Any]:
        """Verify and issue a fresh receipt for direct in-process callers."""
        return self._issue_verification_receipt(request)

    def issue_verification_receipt_with_identity(
        self, *, _receipt_id: str, _nonce: str, _issued_at: str, **request: Any
    ) -> dict[str, Any]:
        """Issue using a verifier-owned durable identity reserved by the authenticated RPC."""
        if (not isinstance(_receipt_id, str) or not _receipt_id
                or not isinstance(_nonce, str) or not _nonce
                or not isinstance(_issued_at, str) or not _issued_at):
            raise E09AuthenticationError("durable receipt identity is invalid")
        return self._issue_verification_receipt(
            request,
            receipt_identity={
                "receipt_id": _receipt_id, "nonce": _nonce, "issued_at": _issued_at,
            },
        )

    def _issue_verification_receipt(
        self, request: dict[str, Any], *, receipt_identity: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Verify a grant and issue a signed receipt for all candidate evidence refs."""
        if self._receipt_signer is None:
            raise E09AuthorizationError("verifier receipt signer is not configured")
        receipt_only_fields = {
            "candidate_evidence_refs", "candidate_evidence_world_family_by_ref",
            "world_family_by_evidence",
        }
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
        issued_at = current
        receipt_id = secrets.token_hex(16)
        nonce = secrets.token_urlsafe(32)
        if receipt_identity is not None:
            try:
                issued_at = datetime.fromisoformat(
                    receipt_identity["issued_at"].replace("Z", "+00:00")
                )
            except (TypeError, ValueError) as exc:
                raise E09AuthenticationError("durable receipt timestamp is invalid") from exc
            if issued_at.tzinfo is None:
                raise E09AuthenticationError("durable receipt timestamp must be timezone-aware")
            issued_at = issued_at.astimezone(timezone.utc)
            receipt_id, nonce = receipt_identity["receipt_id"], receipt_identity["nonce"]
        expires_at = min(grant_expiry, issued_at + self._receipt_ttl)
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
        world_family_assertions = []
        for field in ("world_family_by_evidence", "candidate_evidence_world_family_by_ref"):
            if field not in request:
                continue
            mapping = request[field]
            expected_refs = (
                set(permit.evidence_refs)
                if field == "world_family_by_evidence"
                else set(all_evidence_refs)
            )
            if (not isinstance(mapping, dict)
                    or set(mapping) != expected_refs
                    or any(not isinstance(value, str) or not value.strip()
                           for value in mapping.values())):
                raise E09AuthorizationError(
                    f"{field} must exactly cover its authorized evidence reference set when supplied"
                )
            world_family_assertions.append((field, mapping))

        evidence = []
        for ref in all_evidence_refs:
            item = resolve_e09_reveal(
                self._store,
                episode_id=episode_id,
                evidence_ref=ref,
                scope=request["scope"],
                learner_track=request["learner_track"],
            )
            for field, mapping in world_family_assertions:
                if ref in mapping and mapping[ref] != item.world_family:
                    raise E09AuthorizationError(
                        f"{field} conflicts with trusted Observation domain for {ref}"
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
            })

        receipt = {
            "schema_version": "e09_verification_receipt@1",
            "receipt_id": receipt_id,
            "nonce": nonce,
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
            "issued_at": issued_at.isoformat(),
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
