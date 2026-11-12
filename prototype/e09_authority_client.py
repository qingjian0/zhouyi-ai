"""Typed client facade for E09 Authority UDS RPC; contains no SQLite access."""
from __future__ import annotations

import hashlib
from typing import Any

from prototype.unix_ipc import UnixJSONRPCClient


class E09AuthorityRPCClient:
    """Narrow client for the allowlisted E09 Authority RPC operations."""

    def __init__(self, transport: UnixJSONRPCClient, *, deadline_ms: int = 5_000) -> None:
        if not isinstance(transport, UnixJSONRPCClient):
            raise TypeError("transport must be UnixJSONRPCClient")
        if isinstance(deadline_ms, bool) or not isinstance(deadline_ms, int) or not 1 <= deadline_ms <= 30_000:
            raise ValueError("deadline_ms must be between 1 and 30000")
        self.transport = transport
        self.deadline_ms = deadline_ms

    def _request(
        self, operation: str, body: dict[str, Any], *, operation_id: str, deadline_ms: int | None = None
    ) -> dict[str, Any]:
        return self.transport.request(
            operation,
            body,
            operation_id=operation_id,
            deadline_ms=self.deadline_ms if deadline_ms is None else deadline_ms,
        )

    @staticmethod
    def _read_operation_id(*parts: str) -> str:
        digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]
        return f"read-{digest}"

    def put_observation_input(
        self, *, scope: str, payload: dict[str, Any], operation_id: str
    ) -> str:
        result = self._request(
            "observation.put_input",
            {"scope": scope, "payload": payload},
            operation_id=operation_id,
        )
        payload_ref = result.get("payload_ref")
        if not isinstance(payload_ref, str) or not payload_ref:
            raise RuntimeError("E09 Authority returned an invalid payload reference")
        return payload_ref

    def append_observation(
        self,
        *,
        episode_id: str,
        event_id: str,
        observation_id: str,
        query_id: str,
        scope: str,
        split: str,
        learner_workload_id: str,
        operation_id: str,
        payload_ref: str | None = None,
        feature_schema_version: str | None = None,
        causation_refs: tuple[str, ...] = (),
        expected_sequence: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "episode_id": episode_id,
            "event_id": event_id,
            "observation_id": observation_id,
            "query_id": query_id,
            "scope": scope,
            "split": split,
            "learner_workload_id": learner_workload_id,
            "causation_refs": list(causation_refs),
        }
        if payload_ref is not None:
            body["payload_ref"] = payload_ref
        if feature_schema_version is not None:
            body["feature_schema_version"] = feature_schema_version
        if expected_sequence is not None:
            body["expected_sequence"] = expected_sequence
        return self._request(
            "observation.append", body, operation_id=operation_id
        )

    def read_observation_input(
        self, *, episode_id: str, observation_id: str, scope: str, operation_id: str | None = None
    ) -> Any:
        result = self._request(
            "observation.read_input",
            {"episode_id": episode_id, "observation_id": observation_id, "scope": scope},
            operation_id=operation_id or self._read_operation_id("input", episode_id, observation_id, scope),
        )
        if "payload" not in result:
            raise RuntimeError("E09 Authority omitted observation payload")
        return result["payload"]

    def append_prediction_commit(
        self,
        *,
        episode_id: str,
        event_id: str,
        payload: dict[str, Any],
        causation_refs: tuple[str, ...],
        operation_id: str,
        expected_sequence: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "episode_id": episode_id,
            "event_id": event_id,
            "payload": payload,
            "causation_refs": list(causation_refs),
        }
        if expected_sequence is not None:
            body["expected_sequence"] = expected_sequence
        return self._request("prediction.commit", body, operation_id=operation_id)

    def append_evidence_reveal(
        self,
        *,
        episode_id: str,
        event_id: str,
        payload: dict[str, Any],
        causation_refs: tuple[str, ...],
        operation_id: str,
        expected_sequence: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "episode_id": episode_id,
            "event_id": event_id,
            "payload": payload,
            "causation_refs": list(causation_refs),
        }
        if expected_sequence is not None:
            body["expected_sequence"] = expected_sequence
        return self._request("evidence.reveal", body, operation_id=operation_id)

    def read_support_feedback(
        self,
        *,
        episode_id: str,
        reveal_event_id: str,
        scope: str,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "evidence.read_support_feedback",
            {"episode_id": episode_id, "reveal_event_id": reveal_event_id, "scope": scope},
            operation_id=operation_id or self._read_operation_id("feedback", episode_id, reveal_event_id, scope),
        )

    def read_learner_episode(
        self,
        *,
        episode_id: str,
        scope: str,
        learner_track: str,
        operation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        result = self._request(
            "episode.read_for_learner",
            {"episode_id": episode_id, "scope": scope, "learner_track": learner_track},
            operation_id=operation_id or self._read_operation_id(
                "episode", episode_id, scope, learner_track
            ),
        )
        events = result.get("events")
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            raise RuntimeError("E09 Authority returned an invalid learner event projection")
        return events

    def append_structure_version(
        self,
        *,
        episode_id: str,
        event_id: str,
        scope: str,
        learner_track: str,
        payload: dict[str, Any],
        operation_id: str,
        causation_refs: tuple[str, ...] = (),
        expected_sequence: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "episode_id": episode_id,
            "event_id": event_id,
            "scope": scope,
            "learner_track": learner_track,
            "payload": payload,
            "causation_refs": list(causation_refs),
        }
        if expected_sequence is not None:
            body["expected_sequence"] = expected_sequence
        return self._request("structure.append", body, operation_id=operation_id)

    def append_revision(
        self,
        *,
        episode_id: str,
        event_id: str,
        scope: str,
        learner_track: str,
        payload: dict[str, Any],
        causation_refs: tuple[str, ...],
        operation_id: str,
        expected_sequence: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "episode_id": episode_id,
            "event_id": event_id,
            "scope": scope,
            "learner_track": learner_track,
            "payload": payload,
            "causation_refs": list(causation_refs),
        }
        if expected_sequence is not None:
            body["expected_sequence"] = expected_sequence
        return self._request("revision.append", body, operation_id=operation_id)

    def read_learner_checkpoint(
        self,
        *,
        episode_id: str,
        scope: str,
        learner_track: str,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "structure.read_checkpoint",
            {"episode_id": episode_id, "scope": scope, "learner_track": learner_track},
            operation_id=operation_id or self._read_operation_id(
                "checkpoint", episode_id, scope, learner_track
            ),
        )


class E09LearnerMemorySource:
    """Duck-typed replay source for ZPCMMemory; returns no raw reveal labels."""

    def __init__(
        self, client: E09AuthorityRPCClient, *, scope: str, learner_track: str
    ) -> None:
        if not isinstance(client, E09AuthorityRPCClient):
            raise TypeError("client must be E09AuthorityRPCClient")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be a non-empty string")
        if not isinstance(learner_track, str) or not learner_track.strip():
            raise ValueError("learner_track must be a non-empty string")
        self.client = client
        self.scope = scope
        self.learner_track = learner_track

    def replay_episode(self, episode_id: str) -> list[dict[str, Any]]:
        return self.client.read_learner_episode(
            episode_id=episode_id,
            scope=self.scope,
            learner_track=self.learner_track,
        )
