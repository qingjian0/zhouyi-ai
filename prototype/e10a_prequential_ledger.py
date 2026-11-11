"""Minimal append-only prequential ledger for E10-A.

This module enforces causal ordering inside one trusted runner. It is not a
process-isolation or cryptographic security boundary; evaluator truth must
remain in a separate process/service in production.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


SCHEMA_VERSION = "e10a-prequential-ledger-v1"
DECISIONS = {"PREDICT", "ABSTAIN_AMBIGUOUS", "ABSTAIN_INCONSISTENT", "ABSTAIN_BUDGET", "ABSTAIN_OOD_SCHEMA", "ABSTAIN_OOD_VALUE", "ABSTAIN_OOD_RELATION"}
REVISION_OPERATIONS = {"create", "keep", "modify", "split", "merge", "suspend", "retire", "abstain"}


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _json_copy(value: Any, field: str) -> Any:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON-serializable") from exc


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class PrequentialLedger:
    """Append-only event ledger with prediction-before-reveal enforcement."""

    def __init__(self, *, episode_id: str):
        self.episode_id = _string(episode_id, "episode_id")
        self._events: list[dict[str, Any]] = []
        self._commits: dict[str, dict[str, Any]] = {}
        self._reveals: dict[str, dict[str, Any]] = {}
        self._revealed_by_observation: dict[str, str] = {}
        self._revision_ids: set[str] = set()
        self._step = 0

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._step += 1
        event = {
            "schema_version": SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "event_id": f"{self.episode_id}:event:{self._step:08d}",
            "step": self._step,
            "event_type": event_type,
            **_json_copy(payload, "event payload"),
        }
        self._events.append(event)
        return copy.deepcopy(event)

    def commit_prediction(
        self, *, prediction_id: str, observation_id: str, model_version: str,
        candidate_set_hash: str, decision_status: str, prediction: Any = None,
        confidence: float | None = None, compute_cost: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prediction_id = _string(prediction_id, "prediction_id")
        observation_id = _string(observation_id, "observation_id")
        model_version = _string(model_version, "model_version")
        candidate_set_hash = _string(candidate_set_hash, "candidate_set_hash")
        if prediction_id in self._commits:
            raise ValueError("prediction_id already committed; commits are immutable")
        if observation_id in self._revealed_by_observation:
            raise ValueError("cannot commit a prediction after its observation was revealed")
        if decision_status not in DECISIONS:
            raise ValueError("unsupported decision_status")
        if decision_status == "PREDICT" and prediction is None:
            raise ValueError("PREDICT requires a prediction")
        if decision_status != "PREDICT" and prediction is not None:
            raise ValueError("abstention must not carry a prediction")
        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ValueError("confidence must be numeric in [0, 1]")
        cost = _json_copy(compute_cost or {}, "compute_cost")
        if not isinstance(cost, dict):
            raise ValueError("compute_cost must be a dictionary")
        payload = {
            "prediction_id": prediction_id,
            "observation_id": observation_id,
            "model_version": model_version,
            "candidate_set_hash": candidate_set_hash,
            "decision_status": decision_status,
            "prediction": _json_copy(prediction, "prediction") if prediction is not None else None,
            "confidence": confidence,
            "compute_cost": cost,
        }
        event = self._append("PredictionCommit", payload)
        self._commits[prediction_id] = event
        return event

    def reveal_evidence(
        self, *, reveal_id: str, prediction_id: str, target: Any,
        reveal_source: str = "evaluator", reliability: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        reveal_id = _string(reveal_id, "reveal_id")
        prediction_id = _string(prediction_id, "prediction_id")
        if reveal_id in self._reveals:
            raise ValueError("reveal_id already exists")
        if prediction_id not in self._commits:
            raise ValueError("reveal requires a prior committed prediction")
        commit = self._commits[prediction_id]
        observation_id = commit["observation_id"]
        if observation_id in self._revealed_by_observation:
            raise ValueError("observation has already been revealed")
        event = self._append("EvidenceReveal", {
            "reveal_id": reveal_id,
            "prediction_id": prediction_id,
            "observation_id": observation_id,
            "target": _json_copy(target, "target"),
            "reveal_source": _string(reveal_source, "reveal_source"),
            "reliability": _json_copy(reliability or {}, "reliability"),
            "prediction_event_id": commit["event_id"],
        })
        self._reveals[reveal_id] = event
        self._revealed_by_observation[observation_id] = reveal_id
        return event

    def append_revision(
        self, *, revision_id: str, operation: str, evidence_ids: list[str],
        before_version_ids: list[str], after_version_ids: list[str],
        rationale_code: str, actual_compute: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        revision_id = _string(revision_id, "revision_id")
        if revision_id in self._revision_ids:
            raise ValueError("revision_id already exists")
        if operation not in REVISION_OPERATIONS:
            raise ValueError("unsupported revision operation")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError("revision requires at least one revealed evidence ID")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("revision evidence IDs must be unique")
        unknown = [item for item in evidence_ids if item not in self._reveals]
        if unknown:
            raise ValueError("revision cannot cite evidence that has not been revealed")
        for name, values in (("before_version_ids", before_version_ids),
                             ("after_version_ids", after_version_ids)):
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"{name} must be a list of non-empty strings")
        event = self._append("RevisionEvent", {
            "revision_id": revision_id,
            "operation": operation,
            "trigger_evidence_ids": list(evidence_ids),
            "before_version_ids": list(before_version_ids),
            "after_version_ids": list(after_version_ids),
            "rationale_code": _string(rationale_code, "rationale_code"),
            "actual_compute": _json_copy(actual_compute or {}, "actual_compute"),
        })
        self._revision_ids.add(revision_id)
        return event

    def snapshot(self) -> dict[str, Any]:
        """Return a detached immutable-by-convention ledger snapshot."""
        events = copy.deepcopy(self._events)
        return {
            "schema_version": SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "event_count": len(events),
            "last_step": self._step,
            "events": events,
            "ledger_hash": canonical_hash(events),
        }
