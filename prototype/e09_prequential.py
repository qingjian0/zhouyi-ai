"""Prequential runner for E09-B.

This module adds a predict/commit/reveal boundary around the existing learner.
Its revision arm deliberately calls the existing full-data fit() and is named
BATCH_REFIT; it is an evaluation harness, not an incremental-update claim.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Hashable, Sequence

from prototype.e09_counterexample_learner import (
    CounterexampleRuleLearner, Example,
)
from prototype.e09_evidence_ledger import EvidenceLedger, EvidenceError
from prototype.e09_incremental_learner import IncrementalConjunctionLearner

Value = Hashable
Label = Hashable


class PrequentialError(ValueError):
    """Invalid prequential state transition."""


@dataclass(frozen=True)
class PredictionCommit:
    prediction_id: str
    observation_id: str
    inputs: tuple[Value, ...]
    model_version: int
    prediction: Label | None
    decision_status: str
    step: int


@dataclass(frozen=True)
class EvidenceReveal:
    reveal_id: str
    prediction_id: str
    label: Label
    step: int


@dataclass(frozen=True)
class RevisionEvent:
    revision_id: str
    trigger_reveal_id: str
    before_model_version: int
    after_model_version: int
    before_snapshot: str
    after_snapshot: str
    operation: str
    training_example_count: int
    candidate_evaluations: int
    step: int


class PrequentialRunner:
    """Enforces predict -> commit -> reveal -> append -> selected revision arm."""

    REVISION_MODE = "BATCH_REFIT"

    def __init__(self, learner, ledger: EvidenceLedger | None = None, *,
                 revision_mode: str = "BATCH_REFIT") -> None:
        if revision_mode not in {"BATCH_REFIT", "INCREMENTAL_INDEX"}:
            raise PrequentialError("unsupported revision mode")
        if revision_mode == "INCREMENTAL_INDEX" and not isinstance(
            learner, IncrementalConjunctionLearner
        ):
            raise PrequentialError("INCREMENTAL_INDEX requires IncrementalConjunctionLearner")
        self.REVISION_MODE = revision_mode
        self.learner = learner
        self.ledger = ledger or EvidenceLedger()
        self.model_version = 0
        self.step = 0
        self._predictions: dict[str, PredictionCommit] = {}
        self._reveals: dict[str, EvidenceReveal] = {}
        self._revisions: list[RevisionEvent] = []

    def bootstrap(self, records: Sequence[tuple[str, Example]]) -> None:
        """Load prequentially unavailable historical training evidence."""
        if self.model_version or self._predictions or self.ledger.records():
            raise PrequentialError("bootstrap is allowed only on an empty runner")
        if not records:
            raise PrequentialError("bootstrap requires at least one record")
        for sample_id, example in records:
            self.ledger.append(sample_id, example, source="bootstrap")
        if self.REVISION_MODE == "BATCH_REFIT":
            self.ledger.fit(self.learner)
        else:
            # Replay every raw record, including conflicts, so the index learns
            # which historical inputs are quarantined by ledger adjudication.
            for record in self.ledger.records():
                self.learner.observe(record.example.inputs, record.example.label)
        self.model_version = 1
        self.step += 1

    def predict_and_commit(self, observation_id: str,
                           inputs: Sequence[Value]) -> PredictionCommit:
        if not isinstance(observation_id, str) or not observation_id.strip():
            raise PrequentialError("observation_id must be non-empty")
        if self.model_version == 0:
            raise PrequentialError("bootstrap the learner before prediction")
        if observation_id in {p.observation_id for p in self._predictions.values()}:
            raise PrequentialError("observation already has a committed prediction")
        values = tuple(inputs)
        prediction = self.learner.predict(values)
        status = "PREDICT" if prediction is not None else "ABSTAIN"
        self.step += 1
        commit = PredictionCommit(
            prediction_id=f"pred-{len(self._predictions) + 1}",
            observation_id=observation_id,
            inputs=values,
            model_version=self.model_version,
            prediction=prediction,
            decision_status=status,
            step=self.step,
        )
        # Persist in the runner's append-only commit collection before reveal.
        self._predictions[commit.prediction_id] = commit
        return commit

    def reveal(self, prediction_id: str, label: Label, *,
               source: str = "feedback", source_id: str = "") -> EvidenceReveal:
        commit = self._predictions.get(prediction_id)
        if commit is None:
            raise PrequentialError("reveal requires an existing prediction commit")
        if prediction_id in self._reveals:
            raise PrequentialError("prediction already has a reveal")
        self.step += 1
        reveal = EvidenceReveal(
            reveal_id=f"reveal-{len(self._reveals) + 1}",
            prediction_id=prediction_id,
            label=label,
            step=self.step,
        )
        try:
            self.ledger.append(
                commit.observation_id,
                Example(commit.inputs, label),
                source=source,
                source_id=source_id,
            )
        except EvidenceError as exc:
            raise PrequentialError(f"evidence append rejected: {exc}") from exc
        self._reveals[prediction_id] = reveal
        return reveal

    def revise(self, prediction_id: str) -> RevisionEvent:
        reveal = self._reveals.get(prediction_id)
        if reveal is None:
            raise PrequentialError("revision requires a prior evidence reveal")
        if any(r.trigger_reveal_id == reveal.reveal_id for r in self._revisions):
            raise PrequentialError("this reveal already triggered a revision")
        before = json.dumps(self.learner.snapshot(), sort_keys=True, default=repr)
        before_version = self.model_version
        before_cost = self.learner.report.get("candidate_patterns_evaluated", 0)
        if self.REVISION_MODE == "BATCH_REFIT":
            # Baseline: recompute from all uncontested historical evidence.
            self.ledger.fit(self.learner)
        else:
            commit = self._predictions[prediction_id]
            # Apply only this newly revealed input; conflicts retract its prior
            # contribution inside the incremental learner.
            self.learner.observe(commit.inputs, reveal.label)
        self.model_version += 1
        self.step += 1
        after = json.dumps(self.learner.snapshot(), sort_keys=True, default=repr)
        report = self.learner.report
        event = RevisionEvent(
            revision_id=f"revision-{len(self._revisions) + 1}",
            trigger_reveal_id=reveal.reveal_id,
            before_model_version=before_version,
            after_model_version=self.model_version,
            before_snapshot=before,
            after_snapshot=after,
            operation=self.REVISION_MODE,
            training_example_count=report.get("training_examples", 0),
            candidate_evaluations=(report.get("candidate_patterns_evaluated", 0) if self.REVISION_MODE == "BATCH_REFIT" else report.get("candidate_patterns_evaluated", 0) - before_cost),
            step=self.step,
        )
        self._revisions.append(event)
        return event

    def score(self) -> dict:
        scored = []
        for prediction_id, reveal in self._reveals.items():
            commit = self._predictions[prediction_id]
            if commit.prediction is not None:
                scored.append(commit.prediction == reveal.label)
        return {
            "prediction_commits": len(self._predictions),
            "revealed_observations": len(self._reveals),
            "coverage": (
                sum(p.prediction is not None for p in self._predictions.values())
                / len(self._predictions) if self._predictions else None
            ),
            "accuracy_when_predicted": (
                sum(scored) / len(scored) if scored else None
            ),
            "revision_mode": self.REVISION_MODE,
            "revision_count": len(self._revisions),
            "model_version": self.model_version,
        }

    def snapshot(self) -> dict:
        return {
            "revision_mode": self.REVISION_MODE,
            "model_version": self.model_version,
            "step": self.step,
            "prediction_commits": [asdict(p) for p in self._predictions.values()],
            "evidence_reveals": [asdict(r) for r in self._reveals.values()],
            "revision_events": [asdict(r) for r in self._revisions],
            "ledger": self.ledger.snapshot(),
            "score": self.score(),
        }
