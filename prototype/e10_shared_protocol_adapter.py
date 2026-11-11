"""E10 adapter that mirrors the E10-A prequential ledger into protocol v0.2.

This is persistence/conformance integration only. It does not implement an
E10 relation learner, transactional cross-store commit, process isolation,
or restart reconstruction.
"""
from __future__ import annotations

from typing import Any

from prototype.e10a_prequential_ledger import PrequentialLedger, canonical_hash
from prototype.shared_evidence_protocol import (
    SQLiteEvidenceStore, digest_payload,
)


class E10ProtocolAdapterError(RuntimeError):
    """The adapter is fail-closed after a partial cross-store operation."""


class E10SharedProtocolAdapter:
    LEARNER_TRACK = "e10"

    def __init__(
        self, ledger: PrequentialLedger, store: SQLiteEvidenceStore, *,
        episode_id: str, initial_version_id: str,
        initial_structure: dict[str, Any], learner_track: str = LEARNER_TRACK,
    ) -> None:
        if ledger.episode_id != episode_id:
            raise ValueError("ledger and adapter episode_id must match")
        if not isinstance(learner_track, str) or not learner_track.strip():
            raise ValueError("learner_track must be non-empty")
        if not isinstance(initial_structure, dict):
            raise ValueError("initial_structure must be an object")
        if store.replay_episode(episode_id):
            raise E10ProtocolAdapterError("adapter currently requires a fresh episode")
        self.ledger = ledger
        self.store = store
        self.episode_id = episode_id
        self.learner_track = learner_track
        self._failed = False
        self._committed: set[str] = set()
        self._revealed: dict[str, str] = {}
        self._reveal_event_ids: dict[str, str] = {}
        self._version_id = initial_version_id
        self._append_structure(
            version_id=initial_version_id,
            definition=initial_structure,
            parents=[],
            evidence_ids=[],
            causation_refs=[],
        )

    def _assert_healthy(self) -> None:
        if self._failed:
            raise E10ProtocolAdapterError(
                "adapter is fail-closed after a partial cross-store operation"
            )

    def _event_id(self, kind: str, identity: str) -> str:
        return f"{self.episode_id}:{kind}:{identity}"

    def _append_structure(
        self, *, version_id: str, definition: dict[str, Any],
        parents: list[str], evidence_ids: list[str],
        causation_refs: list[str],
    ) -> str:
        event_id = self._event_id("structure", version_id)
        self.store.append_event(
            episode_id=self.episode_id,
            event_id=event_id,
            event_type="structure_version",
            idempotency_key=event_id,
            actor_role="learner",
            causation_refs=causation_refs,
            payload={
                "structure_id": "e10-relation-mechanism",
                "version_id": version_id,
                "kind": "relation_mechanism",
                "definition": {
                    "representation": "e10-native",
                    "definition": definition,
                    "definition_digest": digest_payload(definition),
                },
                "parent_version_ids": parents,
                "support_evidence_ids": evidence_ids,
                "learner_track": self.learner_track,
            },
        )
        return event_id

    def commit_prediction(
        self, *, prediction_id: str, observation_id: str,
        observation_payload: dict[str, Any], model_version: str,
        candidate_set_hash: str, decision_status: str,
        prediction: Any = None, confidence: float | None = None,
        compute_cost: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_healthy()
        if prediction_id in self._committed:
            raise ValueError("prediction_id already committed by this adapter")
        try:
            # Only a digest of learner-visible query payload is persisted.
            observation_event_id = self._event_id("observation", observation_id)
            self.store.append_event(
                episode_id=self.episode_id,
                event_id=observation_event_id,
                event_type="observation",
                idempotency_key=observation_event_id,
                actor_role="runner",
                payload={
                    "observation_id": observation_id,
                    "payload_ref": digest_payload(observation_payload),
                    "payload_schema": "e10-observation-v1",
                },
            )
            # E10's native ledger remains the source of its own event semantics.
            self.ledger.commit_prediction(
                prediction_id=prediction_id,
                observation_id=observation_id,
                model_version=model_version,
                candidate_set_hash=candidate_set_hash,
                decision_status=decision_status,
                prediction=prediction,
                confidence=confidence,
                compute_cost=compute_cost,
            )
            protocol_event_id = self._event_id("prediction", prediction_id)
            self.store.commit_prediction(
                episode_id=self.episode_id,
                event_id=protocol_event_id,
                idempotency_key=protocol_event_id,
                actor_role="learner",
                causation_refs=[observation_event_id],
                payload={
                    "prediction_id": prediction_id,
                    "observation_id": observation_id,
                    "model_version": model_version,
                    "candidate_set_hash": candidate_set_hash,
                    "decision_status": decision_status,
                    "prediction": prediction,
                    "confidence": confidence,
                    "compute_cost": compute_cost or {},
                    "learner_track": self.learner_track,
                },
            )
            self._committed.add(prediction_id)
            return {
                "prediction_id": prediction_id,
                "observation_id": observation_id,
                "event_id": protocol_event_id,
                "decision_status": decision_status,
            }
        except Exception as exc:
            self._failed = True
            raise E10ProtocolAdapterError(
                f"prediction commit failed; adapter stopped for reconciliation: {exc}"
            ) from exc

    def reveal_evidence(
        self, *, reveal_id: str, prediction_id: str, target: Any,
        reveal_source: str = "evaluator",
        reliability: dict[str, Any] | None = None,
    ) -> str:
        self._assert_healthy()
        if prediction_id not in self._committed:
            raise ValueError("reveal requires a prediction committed by this adapter")
        if prediction_id in self._revealed:
            raise ValueError("prediction already revealed by this adapter")
        try:
            event_id = self._event_id("reveal", reveal_id)
            prediction_event_id = self._event_id("prediction", prediction_id)
            # Persist the evaluator reveal before mutating E10's native ledger.
            self.store.reveal_evidence(
                episode_id=self.episode_id,
                event_id=event_id,
                idempotency_key=event_id,
                actor_role="evaluator",
                causation_refs=[prediction_event_id],
                payload={
                    "prediction_id": prediction_id,
                    "learner_track": self.learner_track,
                    "target_or_feedback": target,
                    "reveal_source": reveal_source,
                    "reliability": reliability or {},
                },
            )
            self.ledger.reveal_evidence(
                reveal_id=reveal_id,
                prediction_id=prediction_id,
                target=target,
                reveal_source=reveal_source,
                reliability=reliability,
            )
            self._revealed[prediction_id] = event_id
            self._reveal_event_ids[reveal_id] = event_id
            return event_id
        except Exception as exc:
            self._failed = True
            raise E10ProtocolAdapterError(
                f"evidence reveal failed; adapter stopped for reconciliation: {exc}"
            ) from exc

    def append_revision(
        self, *, revision_id: str, operation: str,
        evidence_ids: list[str], before_version_ids: list[str],
        after_version_id: str, after_structure: dict[str, Any],
        rationale_code: str, actual_compute: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_healthy()
        if not isinstance(after_structure, dict):
            raise ValueError("after_structure must be an object")
        if not isinstance(after_version_id, str) or not after_version_id.strip():
            raise ValueError("after_version_id must be non-empty")
        if not isinstance(before_version_ids, list) or self._version_id not in before_version_ids:
            raise ValueError("before_version_ids must include the current E10 structure version")
        if after_version_id == self._version_id:
            raise ValueError("after_version_id must create a new structure version")
        try:
            reveal_event_ids = []
            for reveal_id in evidence_ids:
                match = self._reveal_event_ids.get(reveal_id)
                if match is None:
                    raise ValueError(f"unknown adapter reveal id: {reveal_id}")
                reveal_event_ids.append(match)
            # Record the E10-native revision before publishing its resulting
            # structure version. A failure leaves this adapter fail-closed.
            self.ledger.append_revision(
                revision_id=revision_id,
                operation=operation,
                evidence_ids=evidence_ids,
                before_version_ids=before_version_ids,
                after_version_ids=[after_version_id],
                rationale_code=rationale_code,
                actual_compute=actual_compute,
            )
            structure_event_id = self._append_structure(
                version_id=after_version_id,
                definition=after_structure,
                parents=before_version_ids,
                evidence_ids=reveal_event_ids,
                causation_refs=reveal_event_ids,
            )
            revision_event_id = self._event_id("revision", revision_id)
            self.store.append_revision(
                episode_id=self.episode_id,
                event_id=revision_event_id,
                idempotency_key=revision_event_id,
                actor_role="learner",
                causation_refs=reveal_event_ids + [structure_event_id],
                payload={
                    "revision_id": revision_id,
                    "operation": operation,
                    "trigger_evidence_ids": reveal_event_ids,
                    "before_version_ids": before_version_ids,
                    "after_version_ids": [after_version_id],
                    "rationale_code": rationale_code,
                    "actual_compute": actual_compute or {},
                    "learner_track": self.learner_track,
                },
            )
            self._version_id = after_version_id
            return {
                "revision_id": revision_id,
                "structure_event_id": structure_event_id,
                "revision_event_id": revision_event_id,
                "after_version_id": after_version_id,
            }
        except Exception as exc:
            self._failed = True
            raise E10ProtocolAdapterError(
                f"revision persistence failed; adapter stopped for reconciliation: {exc}"
            ) from exc

    def replay(self) -> list[dict[str, Any]]:
        self._assert_healthy()
        return self.store.replay_episode(self.episode_id)

    def native_snapshot(self) -> dict[str, Any]:
        self._assert_healthy()
        return self.ledger.snapshot()
