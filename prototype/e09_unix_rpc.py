"""Authenticated Unix RPC facade for the E09 Authority service.

The kernel-derived UnixPeerIdentity is the only credential passed to E09
Authority. Request JSON cannot select a workload, role or scope identity.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping

from prototype.e09_authority_services import (
    E09AuthenticatedWorkload,
    E09AuthenticationError,
    E09AuthorizationError,
    E09AuthorityService,
)
from prototype.shared_evidence_protocol import (
    IdempotencyConflict,
    MissingReference,
    SequenceConflict,
)
from prototype.unix_ipc import (
    IPCRequestContext,
    IPCRequestError,
    UnixJSONRPCServer,
    UnixPeerIdentity,
    UnixPeerResolver,
)


class E09UnixRPCConfigurationError(ValueError):
    """The Authority RPC identity map or service configuration is invalid."""


class UnixPeerWorkloadAuthenticator:
    """Convert kernel-derived peer identity into a configured E09 workload.

    The workload metadata is provisioned by the Authority process. UID/GID
    mapping is performed independently by UnixPeerResolver from SO_PEERCRED.
    Both mappings must agree exactly on workload ID, roles and scopes.
    """

    def __init__(self, principals: Mapping[str, E09AuthenticatedWorkload]) -> None:
        if not principals:
            raise E09UnixRPCConfigurationError("at least one workload principal is required")
        normalized: dict[str, E09AuthenticatedWorkload] = {}
        for workload_id, principal in principals.items():
            if not isinstance(workload_id, str) or not workload_id.strip():
                raise E09UnixRPCConfigurationError("workload IDs must be non-empty")
            if not isinstance(principal, E09AuthenticatedWorkload):
                raise E09UnixRPCConfigurationError("principal map values must be E09AuthenticatedWorkload")
            if principal.workload_id != workload_id:
                raise E09UnixRPCConfigurationError("principal map key must match principal workload_id")
            normalized[workload_id] = principal
        self._principals = normalized

    def authenticate(self, credential: object) -> E09AuthenticatedWorkload:
        if not isinstance(credential, UnixPeerIdentity):
            raise E09AuthenticationError("credential did not originate from Unix peer authentication")
        principal = self._principals.get(credential.workload_id)
        if principal is None:
            raise E09AuthenticationError("Unix peer workload is not provisioned")
        if principal.roles != credential.roles or principal.scopes != credential.scopes:
            raise E09AuthenticationError("Unix peer role/scope claims do not match Authority policy")
        return principal


def _fields(
    body: dict[str, Any], *, required: set[str], optional: set[str] = frozenset()
) -> None:
    if not isinstance(body, dict):
        raise IPCRequestError("invalid_body", "Request body must be an object")
    missing = required - set(body)
    unknown = set(body) - required - optional
    if missing or unknown:
        raise IPCRequestError("invalid_body", "Request body fields do not match operation schema")


def _receipt(receipt: Any) -> dict[str, Any]:
    try:
        value = asdict(receipt)
    except (TypeError, ValueError) as exc:
        raise IPCRequestError("invalid_authority_result", "Authority returned an invalid event receipt") from exc
    return value


def _require_text(body: dict[str, Any], *names: str) -> None:
    for name in names:
        value = body.get(name)
        if not isinstance(value, str) or not value.strip():
            raise IPCRequestError("invalid_body", f"{name} must be a non-empty string")


def _require_string_list(
    body: dict[str, Any], name: str, *, optional: bool = False
) -> None:
    if name not in body and optional:
        return
    values = body.get(name)
    if not isinstance(values, list):
        raise IPCRequestError("invalid_body", f"{name} must be a JSON array")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise IPCRequestError("invalid_body", f"{name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise IPCRequestError("invalid_body", f"{name} must not contain duplicates")


def _require_payload(body: dict[str, Any]) -> None:
    if not isinstance(body.get("payload"), dict):
        raise IPCRequestError("invalid_body", "payload must be a JSON object")


def _require_sequence(body: dict[str, Any]) -> None:
    if "expected_sequence" not in body:
        return
    value = body["expected_sequence"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IPCRequestError("invalid_body", "expected_sequence must be a non-negative integer")


class E09AuthorityUnixRPC:
    """Allowlisted E09 Authority operations over a Linux UDS server."""

    def __init__(
        self,
        authority: E09AuthorityService,
        *,
        peer_resolver: UnixPeerResolver,
        socket_path: str,
        socket_mode: int = 0o660,
        max_workers: int = 32,
    ) -> None:
        if not isinstance(authority, E09AuthorityService):
            raise TypeError("authority must be E09AuthorityService")
        self.authority = authority
        self.server = UnixJSONRPCServer(
            socket_path,
            peer_resolver=peer_resolver,
            handlers=self._handlers(),
            socket_mode=socket_mode,
            max_workers=max_workers,
        )

    def _handlers(self) -> dict[str, Callable[[IPCRequestContext, dict[str, Any]], dict[str, Any]]]:
        return {
            "health": self._safe(self._health),
            "observation.put_input": self._safe(self._put_input),
            "observation.append": self._safe(self._append_observation),
            "observation.read_input": self._safe(self._read_input),
            "prediction.commit": self._safe(self._append_prediction),
            "evidence.reveal": self._safe(self._append_reveal),
            "evidence.read_support_feedback": self._safe(self._read_support_feedback),
            "episode.read_for_learner": self._safe(self._read_learner_episode),
            "structure.append": self._safe(self._append_structure),
            "revision.append": self._safe(self._append_revision),
        }

    @staticmethod
    def _safe(
        handler: Callable[[IPCRequestContext, dict[str, Any]], dict[str, Any]]
    ) -> Callable[[IPCRequestContext, dict[str, Any]], dict[str, Any]]:
        def invoke(context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
            try:
                return handler(context, body)
            except E09AuthenticationError as exc:
                raise IPCRequestError("authentication_failed", "Workload authentication failed") from exc
            except E09AuthorizationError as exc:
                raise IPCRequestError("permission_denied", "Workload is not authorized for this operation") from exc
            except IdempotencyConflict as exc:
                raise IPCRequestError("idempotency_conflict", "Operation ID was reused with different event content") from exc
            except SequenceConflict as exc:
                raise IPCRequestError("sequence_conflict", "Episode sequence is stale") from exc
            except MissingReference as exc:
                raise IPCRequestError("missing_reference", "A required durable reference is missing") from exc
            except (TypeError, ValueError) as exc:
                raise IPCRequestError("invalid_request", "Operation payload failed validation") from exc
        return invoke

    @staticmethod
    def _health(context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, required=set())
        return {"service": "e09-authority", "protocol": "zhouyi-ipc/1", "ready": True}

    def _put_input(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, required={"scope", "payload"})
        _require_text(body, "scope")
        payload_ref = self.authority.put_observation_input(
            context.peer, scope=body["scope"], payload=body["payload"]
        )
        return {"payload_ref": payload_ref}

    def _append_observation(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(
            body,
            required={"episode_id", "event_id", "observation_id", "query_id", "scope", "split"},
            optional={"payload_ref", "feature_schema_version", "causation_refs", "expected_sequence"},
        )
        _require_text(body, "episode_id", "event_id", "observation_id", "query_id", "scope", "split")
        for field in ("payload_ref", "feature_schema_version"):
            if field in body and body[field] is not None and (
                not isinstance(body[field], str) or not body[field].strip()
            ):
                raise IPCRequestError("invalid_body", f"{field} must be a non-empty string")
        _require_string_list(body, "causation_refs", optional=True)
        _require_sequence(body)
        receipt = self.authority.append_observation(
            context.peer,
            episode_id=body["episode_id"], event_id=body["event_id"],
            idempotency_key=context.operation_id,
            observation_id=body["observation_id"], query_id=body["query_id"],
            scope=body["scope"], split=body["split"],
            payload_ref=body.get("payload_ref"),
            feature_schema_version=body.get("feature_schema_version"),
            causation_refs=body.get("causation_refs", ()),
            expected_sequence=body.get("expected_sequence"),
        )
        return _receipt(receipt)

    def _read_input(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, required={"episode_id", "observation_id", "scope"})
        _require_text(body, "episode_id", "observation_id", "scope")
        payload = self.authority.read_observation_input(
            context.peer, episode_id=body["episode_id"],
            observation_id=body["observation_id"], scope=body["scope"],
        )
        return {"payload": payload}

    def _read_learner_episode(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, required={"episode_id", "scope", "learner_track"})
        _require_text(body, "episode_id", "scope", "learner_track")
        events = self.authority.read_learner_episode(
            context.peer,
            episode_id=body["episode_id"],
            scope=body["scope"],
            learner_track=body["learner_track"],
        )
        return {"events": events}

    def _read_support_feedback(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(body, required={"episode_id", "reveal_event_id", "scope"})
        _require_text(body, "episode_id", "reveal_event_id", "scope")
        return self.authority.read_support_feedback(
            context.peer,
            episode_id=body["episode_id"],
            reveal_event_id=body["reveal_event_id"],
            scope=body["scope"],
        )

    def _append_prediction(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(
            body, required={"episode_id", "event_id", "payload", "causation_refs"},
            optional={"expected_sequence"},
        )
        _require_text(body, "episode_id", "event_id")
        _require_payload(body)
        _require_string_list(body, "causation_refs")
        _require_sequence(body)
        receipt = self.authority.append_prediction_commit(
            context.peer,
            episode_id=body["episode_id"], event_id=body["event_id"],
            idempotency_key=context.operation_id, payload=body["payload"],
            causation_refs=body["causation_refs"],
            expected_sequence=body.get("expected_sequence"),
        )
        return _receipt(receipt)

    def _append_reveal(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(
            body, required={"episode_id", "event_id", "payload", "causation_refs"},
            optional={"expected_sequence"},
        )
        _require_text(body, "episode_id", "event_id")
        _require_payload(body)
        _require_string_list(body, "causation_refs")
        _require_sequence(body)
        receipt = self.authority.append_evidence_reveal(
            context.peer,
            episode_id=body["episode_id"], event_id=body["event_id"],
            idempotency_key=context.operation_id, payload=body["payload"],
            causation_refs=body["causation_refs"],
            expected_sequence=body.get("expected_sequence"),
        )
        return _receipt(receipt)

    def _append_structure(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(
            body,
            required={"episode_id", "event_id", "scope", "learner_track", "payload"},
            optional={"causation_refs", "expected_sequence"},
        )
        _require_text(body, "episode_id", "event_id", "scope", "learner_track")
        _require_payload(body)
        _require_string_list(body, "causation_refs", optional=True)
        _require_sequence(body)
        receipt = self.authority.append_structure_version(
            context.peer,
            episode_id=body["episode_id"], event_id=body["event_id"],
            idempotency_key=context.operation_id, scope=body["scope"],
            learner_track=body["learner_track"], payload=body["payload"],
            causation_refs=body.get("causation_refs", ()),
            expected_sequence=body.get("expected_sequence"),
        )
        return _receipt(receipt)

    def _append_revision(self, context: IPCRequestContext, body: dict[str, Any]) -> dict[str, Any]:
        _fields(
            body,
            required={"episode_id", "event_id", "scope", "learner_track", "payload", "causation_refs"},
            optional={"expected_sequence"},
        )
        _require_text(body, "episode_id", "event_id", "scope", "learner_track")
        _require_payload(body)
        _require_string_list(body, "causation_refs")
        _require_sequence(body)
        receipt = self.authority.append_revision(
            context.peer,
            episode_id=body["episode_id"], event_id=body["event_id"],
            idempotency_key=context.operation_id, scope=body["scope"],
            learner_track=body["learner_track"], payload=body["payload"],
            causation_refs=body["causation_refs"],
            expected_sequence=body.get("expected_sequence"),
        )
        return _receipt(receipt)

    def start(self) -> None:
        self.server.start()

    def close(self) -> None:
        self.server.close()

    def __enter__(self) -> "E09AuthorityUnixRPC":
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
