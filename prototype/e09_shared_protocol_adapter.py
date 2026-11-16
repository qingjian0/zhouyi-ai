"""E09 adapter for the shared durable evidence protocol.

The adapter keeps E09's learner semantics intact while persisting the
predict/commit/reveal/revise lifecycle in SQLite. It is a trusted-runner
integration, not evaluator/learner process isolation or crash-resume support.
"""
from __future__ import annotations

import json
from typing import Any, Sequence

from prototype.shared_evidence_protocol import SQLiteEvidenceStore, digest_payload
from prototype.e09_prequential import PrequentialRunner, PrequentialError


class E09ProtocolAdapterError(RuntimeError):
    """The adapter cannot safely continue after a partial integration failure."""


class E09SharedProtocolAdapter:
    LEARNER_TRACK = "e09"

    def __init__(self, runner: PrequentialRunner, store: SQLiteEvidenceStore,
                 *, episode_id: str, learner_track: str = LEARNER_TRACK) -> None:
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ValueError("episode_id must be non-empty")
        if not isinstance(learner_track, str) or not learner_track.strip():
            raise ValueError("learner_track must be non-empty")
        if runner.model_version < 1:
            raise PrequentialError("bootstrap the E09 runner before attaching the adapter")
        self.runner = runner
        self.store = store
        self.episode_id = episode_id
        self.learner_track = learner_track
        self._failed = False
        self._committed_predictions: set[str] = set()
        self._reveals: dict[str, str] = {}
        self._version_id = f"e09-v{runner.model_version}"
        if self.store.replay_episode(self.episode_id):
            raise E09ProtocolAdapterError(
                "adapter currently requires a fresh episode; replay/resume is not implemented"
            )
        self._append_initial_structure()

    @staticmethod
    def _jsonable(value: Any) -> Any:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, default=repr))

    def _snapshot(self) -> dict[str, Any]:
        return self._jsonable(self.runner.learner.snapshot())

    def _assert_healthy(self) -> None:
        if self._failed:
            raise E09ProtocolAdapterError(
                "adapter is fail-closed after a partial persistence/learner failure"
            )

    def _append_initial_structure(self) -> None:
        snapshot = self._snapshot()
        definition = {
            "revision_mode": self.runner.REVISION_MODE,
            "snapshot_digest": digest_payload(snapshot),
            "snapshot": snapshot,
            "bootstrap_training_examples": self.runner.learner.report.get("training_examples", 0),
            "bootstrap_is_pre_episode_evidence": True,
        }
        self.store.append_event(
            episode_id=self.episode_id,
            event_id=f"{self.episode_id}:structure:{self._version_id}",
            event_type="structure_version",
            idempotency_key=f"{self.episode_id}:structure:{self._version_id}",
            actor_role="learner",
            payload={
                "structure_id": "e09-rule-set",
                "version_id": self._version_id,
                "kind": "rule_set",
                "definition": definition,
                "parent_version_ids": [],
                "support_evidence_ids": [],
                "learner_track": self.learner_track,
            },
        )

    def predict_and_commit(self, observation_id: str,
                           inputs: Sequence[Any]) -> dict[str, Any]:
        self._assert_healthy()
        try:
            input_values = tuple(inputs)
            input_digest = digest_payload({"inputs": self._jsonable(input_values)})
            observation_event_id = f"{self.episode_id}:observation:{observation_id}"
            # The durable observation is sequenced before the learner predicts.
            self.store.append_event(
                episode_id=self.episode_id,
                event_id=observation_event_id,
                event_type="observation",
                idempotency_key=observation_event_id,
                actor_role="runner",
                payload={
                    "observation_id": observation_id,
                    "payload_ref": input_digest,
                    "feature_schema_version": "e09-categorical-input-v1",
                },
            )
            commit = self.runner.predict_and_commit(observation_id, input_values)
            prediction_payload = {
                "prediction_id": commit.prediction_id,
                "observation_id": observation_id,
                "model_version": f"e09-model-{commit.model_version}",
                "learner_track": self.learner_track,
                "candidate_set_hash": digest_payload(self._snapshot()),
                "decision_status": (
                    "PREDICT" if commit.prediction is not None else "ABSTAIN_AMBIGUOUS"
                ),
                "prediction": self._jsonable(commit.prediction),
                "compute_cost": {
                    "revision_mode": self.runner.REVISION_MODE,
                    "step": commit.step,
                },
            }
            prediction_event_id = f"{self.episode_id}:prediction:{commit.prediction_id}"
            self.store.commit_prediction(
                episode_id=self.episode_id,
                event_id=prediction_event_id,
                idempotency_key=prediction_event_id,
                actor_role="learner",
                causation_refs=[observation_event_id],
                payload=prediction_payload,
            )
            self._committed_predictions.add(commit.prediction_id)
            return {
                "prediction_id": commit.prediction_id,
                "observation_id": observation_id,
                "prediction": commit.prediction,
                "decision_status": prediction_payload["decision_status"],
                "model_version": commit.model_version,
                "event_id": prediction_event_id,
            }
        except Exception as exc:
            self._failed = True
            raise E09ProtocolAdapterError(
                f"prediction persistence failed; adapter stopped: {exc}"
            ) from exc

    def reveal(self, prediction_id: str, label: Any, *,
               source: str = "feedback", source_id: str = "") -> str:
        self._assert_healthy()
        if prediction_id not in self._committed_predictions:
            raise PrequentialError("reveal requires a prediction committed by this adapter")
        if prediction_id in self._reveals:
            raise PrequentialError("prediction already has a durable reveal")
        try:
            reveal_id = f"reveal-{prediction_id}"
            event_id = f"{self.episode_id}:reveal:{reveal_id}"
            self.store.reveal_evidence(
                episode_id=self.episode_id,
                event_id=event_id,
                idempotency_key=event_id,
                actor_role="evaluator",
                causation_refs=[f"{self.episode_id}:prediction:{prediction_id}"],
                payload={
                    "prediction_id": prediction_id,
                    "learner_track": self.learner_track,
                    "target_or_feedback": self._jsonable(label),
                    "reveal_source": source,
                },
            )
            # Source IDs remain in E09's provenance ledger, not learner-facing
            # protocol payloads; the protocol has no evaluator-only field ACL.
            self.runner.reveal(
                prediction_id, label, source=source, source_id=source_id
            )
            self._reveals[prediction_id] = event_id
            return event_id
        except Exception as exc:
            self._failed = True
            raise E09ProtocolAdapterError(
                f"reveal/append failed; durable state may require reconciliation: {exc}"
            ) from exc

    def revise(self, prediction_id: str) -> dict[str, Any]:
        self._assert_healthy()
        if prediction_id not in self._reveals:
            raise PrequentialError("revision requires a prior durable evidence reveal")
        try:
            reveal_event_id = self._reveals[prediction_id]
            before_version = self._version_id
            revision = self.runner.revise(prediction_id)
            after_version = f"e09-v{revision.after_model_version}"
            snapshot = self._snapshot()
            structure_event_id = f"{self.episode_id}:structure:{after_version}"
            self.store.append_event(
                episode_id=self.episode_id,
                event_id=structure_event_id,
                event_type="structure_version",
                idempotency_key=structure_event_id,
                actor_role="learner",
                causation_refs=[reveal_event_id],
                payload={
                    "structure_id": "e09-rule-set",
                    "version_id": after_version,
                    "kind": "rule_set",
                    "definition": {
                        "revision_mode": revision.operation,
                        "snapshot_digest": digest_payload(snapshot),
                        "snapshot": snapshot,
                        "training_example_count": revision.training_example_count,
                        "candidate_evaluations": revision.candidate_evaluations,
                    },
                    "parent_version_ids": [before_version],
                    "support_evidence_ids": [reveal_event_id],
                    "learner_track": self.learner_track,
                },
            )
            revision_event_id = f"{self.episode_id}:revision:{revision.revision_id}"
            self.store.append_revision(
                episode_id=self.episode_id,
                event_id=revision_event_id,
                idempotency_key=revision_event_id,
                actor_role="learner",
                causation_refs=[reveal_event_id, structure_event_id],
                payload={
                    "revision_id": revision.revision_id,
                    "operation": revision.operation,
                    "trigger_evidence_ids": [reveal_event_id],
                    "before_version_ids": [before_version],
                    "after_version_ids": [after_version],
                    "learner_track": self.learner_track,
                    "training_example_count": revision.training_example_count,
                    "candidate_evaluations": revision.candidate_evaluations,
                },
            )
            self._version_id = after_version
            return {
                "revision_id": revision.revision_id,
                "operation": revision.operation,
                "before_version_id": before_version,
                "after_version_id": after_version,
                "candidate_evaluations": revision.candidate_evaluations,
                "event_id": revision_event_id,
            }
        except Exception as exc:
            self._failed = True
            raise E09ProtocolAdapterError(
                f"revision persistence failed; adapter stopped: {exc}"
            ) from exc

    def replay(self) -> list[dict[str, Any]]:
        self._assert_healthy()
        return self.store.replay_episode(self.episode_id)

    def score(self) -> dict[str, Any]:
        self._assert_healthy()
        return self.runner.score()
