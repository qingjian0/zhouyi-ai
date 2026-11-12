"""Role-specific E09 ports built only on the authenticated Authority RPC client.

These facades keep Observer, Learner and Evaluator call surfaces separate.
They are not process/security boundaries by themselves: deploy each role with
its own OS identity, socket peer mapping and client instance.
"""
from __future__ import annotations

from typing import Any

from prototype.e09_authority_client import E09AuthorityRPCClient, E09LearnerMemorySource


class _RolePort:
    def __init__(self, client: E09AuthorityRPCClient) -> None:
        if not isinstance(client, E09AuthorityRPCClient):
            raise TypeError("role ports require E09AuthorityRPCClient")
        self.client = client


class E09ObserverPort(_RolePort):
    """Observer-only input persistence and Observation publication."""

    def observe(
        self,
        *,
        episode_id: str,
        observation_id: str,
        query_id: str,
        scope: str,
        split: str,
        learner_track: str,
        input_payload: dict[str, Any],
        put_operation_id: str,
        observation_operation_id: str,
        feature_schema_version: str | None = None,
        causation_refs: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        payload_ref = self.client.put_observation_input(
            scope=scope, payload=input_payload, operation_id=put_operation_id
        )
        event_id = f"{episode_id}:observation:{observation_id}"
        receipt = self.client.append_observation(
            episode_id=episode_id,
            event_id=event_id,
            observation_id=observation_id,
            query_id=query_id,
            scope=scope,
            split=split,
            learner_track=learner_track,
            operation_id=observation_operation_id,
            payload_ref=payload_ref,
            feature_schema_version=feature_schema_version,
            causation_refs=causation_refs,
        )
        return {"payload_ref": payload_ref, "observation_receipt": receipt}


class E09LearnerPort(_RolePort):
    """Learner-only reads, commits, revisions and memory projection."""

    def read_observation(
        self, *, episode_id: str, observation_id: str, scope: str
    ) -> Any:
        return self.client.read_observation_input(
            episode_id=episode_id, observation_id=observation_id, scope=scope
        )

    def commit_prediction(
        self,
        *,
        episode_id: str,
        prediction_id: str,
        payload: dict[str, Any],
        observation_event_id: str,
        operation_id: str,
    ) -> dict[str, Any]:
        return self.client.append_prediction_commit(
            episode_id=episode_id,
            event_id=f"{episode_id}:prediction:{prediction_id}",
            payload=payload,
            causation_refs=(observation_event_id,),
            operation_id=operation_id,
        )

    def read_support_feedback(
        self, *, episode_id: str, reveal_event_id: str, scope: str
    ) -> dict[str, Any]:
        return self.client.read_support_feedback(
            episode_id=episode_id, reveal_event_id=reveal_event_id, scope=scope
        )

    def append_structure(
        self,
        *,
        episode_id: str,
        event_id: str,
        scope: str,
        learner_track: str,
        payload: dict[str, Any],
        operation_id: str,
        causation_refs: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return self.client.append_structure_version(
            episode_id=episode_id, event_id=event_id, scope=scope,
            learner_track=learner_track, payload=payload,
            operation_id=operation_id, causation_refs=causation_refs,
        )

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
    ) -> dict[str, Any]:
        return self.client.append_revision(
            episode_id=episode_id, event_id=event_id, scope=scope,
            learner_track=learner_track, payload=payload,
            causation_refs=causation_refs, operation_id=operation_id,
        )

    def checkpoint(
        self, *, episode_id: str, scope: str, learner_track: str
    ) -> dict[str, Any]:
        return self.client.read_learner_checkpoint(
            episode_id=episode_id, scope=scope, learner_track=learner_track
        )

    def memory_source(self, *, scope: str, learner_track: str) -> E09LearnerMemorySource:
        return E09LearnerMemorySource(
            self.client, scope=scope, learner_track=learner_track
        )


class E09EvaluatorPort(_RolePort):
    """Evaluator-only Evidence Reveal publication."""

    def reveal(
        self,
        *,
        episode_id: str,
        prediction_id: str,
        payload: dict[str, Any],
        commit_event_id: str,
        reveal_id: str | None = None,
        operation_id: str,
    ) -> dict[str, Any]:
        return self.client.append_evidence_reveal(
            episode_id=episode_id,
            event_id=f"{episode_id}:reveal:{reveal_id or prediction_id}",
            payload=payload,
            causation_refs=(commit_event_id,),
            operation_id=operation_id,
        )
