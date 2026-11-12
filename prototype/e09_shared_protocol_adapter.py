"""E09 adapter for the shared durable evidence protocol.

The adapter keeps E09's learner semantics intact while persisting the
predict/commit/reveal/revise lifecycle in SQLite. It is a trusted-runner
integration, not evaluator/learner process isolation or crash-resume support.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Sequence

from prototype.shared_evidence_protocol import (
    EVIDENCE_SPLITS, STRICT_PROTOCOL_VERSION, SQLiteEvidenceStore, digest_payload,
)
from prototype.e09_prequential import (
    PrequentialRunner, PrequentialError,
    PredictionCommit as RunnerPredictionCommit,
    EvidenceReveal as RunnerEvidenceReveal,
    RevisionEvent as RunnerRevisionEvent,
)
from prototype.e09_evidence_ledger import EvidenceLedger
from prototype.e09_counterexample_learner import Example
from prototype.cpg_interop import (
    EvidenceReveal, EvidenceSplit, PredictionCommit, canonical_json, validate_reveal_binding,
)


class E09ProtocolAdapterError(RuntimeError):
    """The adapter cannot safely continue after a partial integration failure."""


class E09SharedProtocolAdapter:
    LEARNER_TRACK = "e09"

    def __init__(self, runner: PrequentialRunner, store: SQLiteEvidenceStore,
                 *, episode_id: str, scope: str, split: str = "SUPPORT",
                 learner_track: str = LEARNER_TRACK,
                 structure_id: str = "e09-rule-set",
                 structure_kind: str = "rule_set",
                 version_prefix: str = "e09",
                 memory_projection: Any | None = None) -> None:
        if not isinstance(episode_id, str) or not episode_id.strip():
            raise ValueError("episode_id must be non-empty")
        if not isinstance(learner_track, str) or not learner_track.strip():
            raise ValueError("learner_track must be non-empty")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be non-empty")
        if split not in EVIDENCE_SPLITS:
            raise ValueError(f"split must be one of {sorted(EVIDENCE_SPLITS)}")
        for name, value in (("structure_id", structure_id), ("structure_kind", structure_kind), ("version_prefix", version_prefix)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        if runner.model_version < 1:
            raise PrequentialError("bootstrap the E09 runner before attaching the adapter")
        self.runner = runner
        self.store = store
        self.episode_id = episode_id
        self.learner_track = learner_track
        self.scope = scope
        self.split = split
        self.structure_id = structure_id
        self.structure_kind = structure_kind
        self.version_prefix = version_prefix
        self.memory_projection = memory_projection
        self._failed = False
        self._committed_predictions: set[str] = set()
        self._commit_digests: dict[str, str] = {}
        self._event_digests: dict[str, str] = {}
        self._interop_commits: dict[str, PredictionCommit] = {}
        self._prediction_queries: dict[str, str] = {}
        self._reveals: dict[str, str] = {}
        self._version_id = f"{self.version_prefix}-v{runner.model_version}"
        if self.store.replay_episode(self.episode_id):
            raise E09ProtocolAdapterError(
                "adapter currently requires a fresh episode; replay/resume is not implemented"
            )
        self._append_initial_structure()
        self._sync_memory()

    def _sync_memory(self) -> None:
        if self.memory_projection is None:
            return
        try:
            self.memory_projection.sync_episode(
                self.store, episode_id=self.episode_id, scope=self.scope,
                learner_track=self.learner_track,
            )
        except Exception as exc:
            self._failed = True
            raise E09ProtocolAdapterError(
                f"ZPCM projection failed; E09 source events remain durable and replayable: {exc}"
            ) from exc

    @staticmethod
    def _restore_label(value: Any) -> Any:
        return tuple(value) if isinstance(value, list) else value

    @classmethod
    def resume_srok(
        cls, store: SQLiteEvidenceStore, *, episode_id: str, scope: str,
        split: str, learner_track: str, version_prefix: str,
        learner_factory: Callable[[dict[str, Any]], Any],
        memory_projection: Any | None = None,
    ) -> "E09SharedProtocolAdapter":
        """Rebuild SROK/E09 in-memory state from durable events and checkpoints.

        Requires episodes created with payload-vault and ledger-snapshot support.
        Delivery is replayed at least once; E09 IDs and learner state make it
        idempotent. This remains a trusted single-process recovery path.
        """
        events = store.replay_episode(episode_id)
        structures = [
            e for e in events
            if e["event_type"] == "structure_version"
            and e["payload"].get("learner_track") == learner_track
        ]
        if not structures:
            raise E09ProtocolAdapterError("episode has no durable structure checkpoint")
        latest = structures[-1]
        latest_payload = latest["payload"]
        definition = latest_payload.get("definition", {})
        if "snapshot" not in definition or "ledger_snapshot" not in definition:
            raise E09ProtocolAdapterError("episode predates resumable SROK checkpoint schema")
        learner = learner_factory(definition["snapshot"])
        ledger = EvidenceLedger()
        ledger_snapshot = definition["ledger_snapshot"]
        for record in ledger_snapshot.get("records", []):
            ledger.append(
                record["sample_id"],
                Example(tuple(record["inputs"]), cls._restore_label(record["label"])),
                source=record.get("source", ""),
                source_id=record.get("source_id", ""),
            )
        runner = PrequentialRunner(learner, ledger, revision_mode=definition["revision_mode"])
        version_id = latest_payload["version_id"]
        try:
            model_version = int(definition.get("runner_model_version") or version_id.rsplit("-v", 1)[1])
        except (KeyError, ValueError, IndexError) as exc:
            raise E09ProtocolAdapterError("invalid durable model version") from exc
        runner.model_version = model_version

        observations = {
            e["payload"]["observation_id"]: e["payload"]
            for e in events if e["event_type"] == "observation"
        }
        instance = cls.__new__(cls)
        instance.runner = runner
        instance.store = store
        instance.episode_id = episode_id
        instance.learner_track = learner_track
        instance.scope = scope
        instance.split = split
        instance.structure_id = latest_payload["structure_id"]
        instance.structure_kind = latest_payload["kind"]
        instance.version_prefix = version_prefix
        instance.memory_projection = memory_projection
        instance._failed = False
        instance._committed_predictions = set()
        instance._commit_digests = {}
        instance._event_digests = {}
        instance._interop_commits = {}
        instance._prediction_queries = {}
        instance._reveals = {}
        instance._version_id = version_id

        for event in events:
            if event["event_type"] != "prediction_commit":
                continue
            payload = event["payload"]
            if payload.get("learner_track") != learner_track:
                continue
            prediction_id = payload["prediction_id"]
            observation_id = payload["observation_id"]
            observation = observations.get(observation_id)
            if observation is None:
                raise E09ProtocolAdapterError("prediction has no durable observation")
            stored_input = store.get_payload(observation["payload_ref"])
            inputs = tuple(stored_input["inputs"])
            prediction = cls._restore_label(payload.get("prediction"))
            model_number = int(payload["model_version"].rsplit("-model-", 1)[1])
            step = int(payload.get("compute_cost", {}).get("step", 0))
            runner._predictions[prediction_id] = RunnerPredictionCommit(
                prediction_id, observation_id, inputs, model_number, prediction,
                "PREDICT" if prediction is not None else "ABSTAIN", step,
            )
            interop = PredictionCommit(
                commit_id=prediction_id,
                candidate_ref=f"{instance.structure_id}@{version_prefix}-v{model_number}",
                query_id=payload["query_id"],
                scope=payload["scope"],
                input_digest=observation["payload_ref"],
                identifiable=prediction is not None,
                prediction_json=canonical_json(cls._jsonable(prediction)) if prediction is not None else None,
                abstention_reason=None if prediction is not None else "E09_NO_IDENTIFIABLE_PREDICTION",
                episode_id=episode_id,
                learner_track=learner_track,
                split=EvidenceSplit(split.lower()),
                model_version=payload["model_version"],
            )
            if interop.commit_digest != payload["interop_commit_digest"]:
                raise E09ProtocolAdapterError("reconstructed prediction commit digest mismatch")
            instance._committed_predictions.add(prediction_id)
            instance._commit_digests[prediction_id] = interop.commit_digest
            instance._event_digests[prediction_id] = event["payload_digest"]
            instance._interop_commits[prediction_id] = interop
            instance._prediction_queries[prediction_id] = observation_id
            if hasattr(learner, "last_inference"):
                learner.last_inference = dict(
                    payload.get("compute_cost", {}).get("inference_report", {})
                )

        ledger_ids = {record.sample_id for record in ledger.records()}
        reveal_event_to_prediction = {}
        support_reveals = []
        for event in events:
            if event["event_type"] != "evidence_reveal":
                continue
            payload = event["payload"]
            if payload.get("learner_track") != learner_track:
                continue
            prediction_id = payload["prediction_id"]
            reveal_event_to_prediction[event["event_id"]] = prediction_id
            if payload.get("split") != "SUPPORT":
                continue
            commit = runner._predictions.get(prediction_id)
            if commit is None:
                raise E09ProtocolAdapterError("support reveal has no prediction commit")
            label = cls._restore_label(payload["target_or_feedback"])
            if commit.observation_id not in ledger_ids:
                ledger.append(commit.observation_id, Example(commit.inputs, label),
                              source=payload.get("reveal_source", "feedback"))
                ledger_ids.add(commit.observation_id)
            reveal_id = f"reveal-{prediction_id}"
            runner._reveals[prediction_id] = RunnerEvidenceReveal(
                reveal_id, prediction_id, label, int(event["sequence_no"]),
            )
            instance._reveals[prediction_id] = event["event_id"]
            support_reveals.append((event, prediction_id, reveal_id))

        revised_reveal_ids = set()
        for event in events:
            if event["event_type"] != "revision":
                continue
            payload = event["payload"]
            if payload.get("learner_track") != learner_track:
                continue
            trigger = (payload.get("trigger_evidence_ids") or [None])[0]
            prediction_id = reveal_event_to_prediction.get(trigger)
            if prediction_id is None:
                raise E09ProtocolAdapterError("revision trigger reveal cannot be resolved")
            reveal_id = f"reveal-{prediction_id}"
            before = (payload.get("before_version_ids") or [version_id])[0]
            after = (payload.get("after_version_ids") or [version_id])[0]
            runner._revisions.append(RunnerRevisionEvent(
                payload["revision_id"], reveal_id,
                int(before.rsplit("-v", 1)[1]), int(after.rsplit("-v", 1)[1]),
                "", "", payload["operation"], payload.get("training_example_count", 0),
                payload.get("candidate_evaluations", 0), int(event["sequence_no"]),
            ))
            revised_reveal_ids.add(reveal_id)

        # Crash window: structure snapshot was committed, but its following
        # revision event was not. The structure's support_evidence_ids are the
        # durable commit marker, so synthesize the in-memory dedupe record.
        for structure in structures:
            sp = structure["payload"]
            for evidence_id in sp.get("support_evidence_ids", []):
                prediction_id = reveal_event_to_prediction.get(evidence_id)
                if prediction_id is None:
                    continue
                reveal_id = f"reveal-{prediction_id}"
                if reveal_id in revised_reveal_ids:
                    continue
                before = (sp.get("parent_version_ids") or [version_id])[0]
                after = sp["version_id"]
                sd = sp.get("definition", {})
                runner._revisions.append(RunnerRevisionEvent(
                    f"recovered-{after}", reveal_id,
                    int(before.rsplit("-v", 1)[1]), int(after.rsplit("-v", 1)[1]),
                    "", "", sd.get("revision_mode", runner.REVISION_MODE),
                    sd.get("training_example_count", 0),
                    sd.get("candidate_evaluations", 0), int(structure["sequence_no"]),
                ))
                revised_reveal_ids.add(reveal_id)

        completed_revisions = sum(bool(e["payload"].get("support_evidence_ids")) for e in structures)
        runner.step = 1 + len(runner._predictions) + len(support_reveals) + completed_revisions
        if memory_projection is not None:
            instance._sync_memory()
        return instance

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
            "ledger_snapshot": self.runner.ledger.snapshot(),
            "runner_model_version": self.runner.model_version,
            "runner_step": self.runner.step,
        }
        self.store.append_event(
            episode_id=self.episode_id,
            event_id=f"{self.episode_id}:structure:{self._version_id}",
            event_type="structure_version",
            idempotency_key=f"{self.episode_id}:structure:{self._version_id}",
            actor_role="learner",
            payload={
                "structure_id": self.structure_id,
                "version_id": self._version_id,
                "kind": self.structure_kind,
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
            self.store.put_payload(input_digest, {"inputs": self._jsonable(input_values)})
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
                    "query_id": observation_id,
                    "scope": self.scope,
                    "split": self.split,
                    "payload_ref": input_digest,
                    "feature_schema_version": "e09-categorical-input-v1",
                },
                protocol_version=STRICT_PROTOCOL_VERSION,
            )
            commit = self.runner.predict_and_commit(observation_id, input_values)
            interop_commit = PredictionCommit(
                commit_id=commit.prediction_id,
                candidate_ref=f"{self.structure_id}@{self._version_id}",
                query_id=observation_id,
                scope=self.scope,
                input_digest=input_digest,
                identifiable=commit.prediction is not None,
                prediction_json=(
                    canonical_json(self._jsonable(commit.prediction))
                    if commit.prediction is not None else None
                ),
                abstention_reason=(
                    None if commit.prediction is not None else "E09_NO_IDENTIFIABLE_PREDICTION"
                ),
                episode_id=self.episode_id,
                learner_track=self.learner_track,
                split=EvidenceSplit(self.split.lower()),
                model_version=f"{self.version_prefix}-model-{commit.model_version}",
            )
            prediction_payload = {
                "prediction_id": commit.prediction_id,
                "interop_commit_digest": interop_commit.commit_digest,
                "observation_id": observation_id,
                "query_id": observation_id,
                "scope": self.scope,
                "split": self.split,
                "model_version": f"{self.version_prefix}-model-{commit.model_version}",
                "learner_track": self.learner_track,
                "candidate_set_hash": digest_payload(self._snapshot()),
                "decision_status": (
                    "PREDICT" if commit.prediction is not None else "ABSTAIN_AMBIGUOUS"
                ),
                "prediction": self._jsonable(commit.prediction),
                "compute_cost": {
                    "revision_mode": self.runner.REVISION_MODE,
                    "step": commit.step,
                    "inference_report": self._jsonable(
                        getattr(self.runner.learner, "last_inference", {})
                    ),
                },
            }
            prediction_event_id = f"{self.episode_id}:prediction:{commit.prediction_id}"
            prediction_receipt = self.store.commit_prediction(
                episode_id=self.episode_id,
                event_id=prediction_event_id,
                idempotency_key=prediction_event_id,
                actor_role="learner",
                causation_refs=[observation_event_id],
                payload=prediction_payload,
                protocol_version=STRICT_PROTOCOL_VERSION,
            )
            self._committed_predictions.add(commit.prediction_id)
            self._commit_digests[commit.prediction_id] = interop_commit.commit_digest
            self._event_digests[commit.prediction_id] = prediction_receipt.payload_digest
            self._interop_commits[commit.prediction_id] = interop_commit
            self._prediction_queries[commit.prediction_id] = observation_id
            self._sync_memory()
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
            interop_reveal = EvidenceReveal(
                evidence_id=event_id,
                commit_digest=self._commit_digests[prediction_id],
                query_id=self._prediction_queries[prediction_id],
                scope=self.scope,
                split=EvidenceSplit(self.split.lower()),
                outcome_json=canonical_json(self._jsonable(label)),
                source_ref=event_id,
                episode_id=self.episode_id,
                learner_track=self.learner_track,
            )
            validate_reveal_binding(self._interop_commits[prediction_id], interop_reveal, require_context=True)
            self.store.reveal_evidence(
                episode_id=self.episode_id,
                event_id=event_id,
                idempotency_key=event_id,
                actor_role="evaluator",
                causation_refs=[f"{self.episode_id}:prediction:{prediction_id}"],
                payload={
                    "prediction_id": prediction_id,
                    "query_id": self._prediction_queries[prediction_id],
                    "scope": self.scope,
                    "split": self.split,
                    "commit_digest": interop_reveal.commit_digest,
                    "event_digest": self._event_digests[prediction_id],
                    "learner_track": self.learner_track,
                    "target_or_feedback": self._jsonable(label),
                    "reveal_source": source,
                },
                protocol_version=STRICT_PROTOCOL_VERSION,
            )
            # Source IDs remain in E09's provenance ledger, not learner-facing
            # protocol payloads; the protocol has no evaluator-only field ACL.
            # Only SUPPORT evidence may enter the learner's update path.
            # Gate/test labels are recorded for evaluator-side scoring only.
            if self.split == "SUPPORT":
                self.runner.reveal(
                    prediction_id, label, source=source, source_id=source_id
                )
                self._reveals[prediction_id] = event_id
            self._sync_memory()
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
            after_version = f"{self.version_prefix}-v{revision.after_model_version}"
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
                    "structure_id": self.structure_id,
                    "version_id": after_version,
                    "kind": self.structure_kind,
                    "definition": {
                        "revision_mode": revision.operation,
                        "snapshot_digest": digest_payload(snapshot),
                        "snapshot": snapshot,
                        "training_example_count": revision.training_example_count,
                        "candidate_evaluations": revision.candidate_evaluations,
                        "ledger_snapshot": self.runner.ledger.snapshot(),
                        "runner_model_version": self.runner.model_version,
                        "runner_step": self.runner.step,
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
            self._sync_memory()
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
