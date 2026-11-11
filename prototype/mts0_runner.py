"""MTS-0: minimal prequential training/evaluation harness.

This module wraps the existing E01 learned sparse-composition baseline with
prediction-before-reveal bookkeeping. It is a research harness, not a secure
multi-process evaluator or a trained language model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from prototype.e01_learned_ranker import (
    Example,
    make_dataset,
    predict_indices,
    score_predictions,
    train_ranker,
)


class EvidenceSplit(str, Enum):
    SUPPORT = "support"
    GATE_DEV = "gate_dev"
    LOCKED_TEST = "locked_test"


class ConsumerRole(str, Enum):
    LEARNER = "learner"
    SELECTOR = "selector"
    EVALUATOR = "evaluator"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PredictionCommit:
    commit_id: str
    query_id: str
    scope: str
    input_digest: str
    model_version: str
    prediction: tuple[int, ...]
    commit_digest: str
    sequence: int


@dataclass(frozen=True)
class EvidenceReveal:
    evidence_id: str
    commit_digest: str
    query_id: str
    scope: str
    split: EvidenceSplit
    outcome: tuple[int, ...]
    sequence: int


class EvidenceLedger:
    """Append-only in-memory ledger with role-based visibility metadata.

    Visibility checks are policy guards for this prototype only. A production
    locked-test boundary requires a separate process/service and access control.
    """

    def __init__(self) -> None:
        self._commits: dict[str, PredictionCommit] = {}
        self._reveals: dict[str, EvidenceReveal] = {}
        self._events: list[tuple[str, str]] = []
        self._commits_sealed = False

    @property
    def commits_sealed(self) -> bool:
        return self._commits_sealed

    def seal_commits(self) -> None:
        """Close the prediction phase; reveals are forbidden before this point."""
        if self._commits_sealed:
            raise ValueError("prediction commits are already sealed")
        if not self._commits:
            raise ValueError("cannot seal an empty prediction batch")
        self._commits_sealed = True

    @property
    def commits(self) -> tuple[PredictionCommit, ...]:
        return tuple(self._commits.values())

    @property
    def reveals(self) -> tuple[EvidenceReveal, ...]:
        return tuple(self._reveals.values())

    def commit(
        self,
        *,
        commit_id: str,
        query_id: str,
        scope: str,
        input_payload: Any,
        model_version: str,
        prediction: Iterable[int],
    ) -> PredictionCommit:
        if self._commits_sealed:
            raise ValueError("cannot add predictions after the commit phase is sealed")
        if not all(isinstance(x, str) and x.strip() for x in (commit_id, query_id, scope, model_version)):
            raise ValueError("commit identifiers, scope and model_version must be non-empty strings")
        if commit_id in self._commits:
            raise ValueError("duplicate commit_id")
        pred = tuple(prediction)
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in pred):
            raise ValueError("prediction indices must be non-negative integers")
        if len(set(pred)) != len(pred):
            raise ValueError("prediction indices must be unique")
        payload = {
            "commit_id": commit_id,
            "query_id": query_id,
            "scope": scope,
            "input_digest": digest(input_payload),
            "model_version": model_version,
            "prediction": pred,
        }
        record = PredictionCommit(
            **payload, commit_digest=digest(payload), sequence=len(self._events)
        )
        self._commits[commit_id] = record
        self._events.append(("commit", commit_id))
        return record

    def reveal(
        self,
        *,
        evidence_id: str,
        commit_id: str,
        scope: str,
        split: EvidenceSplit,
        outcome: Iterable[int],
    ) -> EvidenceReveal:
        if not self._commits_sealed:
            raise ValueError("prediction batch must be sealed before any evidence reveal")
        if not isinstance(split, EvidenceSplit):
            raise ValueError("split must be an EvidenceSplit")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("evidence_id must be non-empty")
        if evidence_id in self._reveals:
            raise ValueError("duplicate evidence_id")
        commit = self._commits.get(commit_id)
        if commit is None:
            raise ValueError("reveal requires an existing prediction commit")
        if scope != commit.scope:
            raise ValueError("reveal scope does not match prediction commit")
        target = tuple(outcome)
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in target):
            raise ValueError("outcome indices must be non-negative integers")
        if len(set(target)) != len(target):
            raise ValueError("outcome indices must be unique")
        reveal = EvidenceReveal(
            evidence_id=evidence_id,
            commit_digest=commit.commit_digest,
            query_id=commit.query_id,
            scope=scope,
            split=split,
            outcome=target,
            sequence=len(self._events),
        )
        self._reveals[evidence_id] = reveal
        self._events.append(("reveal", evidence_id))
        return reveal

    def visible_reveals(self, role: ConsumerRole) -> tuple[EvidenceReveal, ...]:
        if not isinstance(role, ConsumerRole):
            raise ValueError("role must be a ConsumerRole")
        visible: list[EvidenceReveal] = []
        for reveal in self._reveals.values():
            if role is ConsumerRole.EVALUATOR:
                visible.append(reveal)
            elif role is ConsumerRole.SELECTOR and reveal.split in (
                EvidenceSplit.SUPPORT,
                EvidenceSplit.GATE_DEV,
            ):
                visible.append(reveal)
            elif role is ConsumerRole.LEARNER and reveal.split is EvidenceSplit.SUPPORT:
                visible.append(reveal)
        return tuple(visible)


def _example_payload(example: Example) -> dict[str, Any]:
    return {
        "query": example.query,
        "candidates": example.candidates,
    }


def run_mts0(
    *,
    seed: int = 7,
    train_count: int = 1200,
    locked_test_count: int = 400,
    candidate_count: int = 7,
    feature_dim: int = 6,
    choose_k: int = 3,
    epochs: int = 180,
) -> dict[str, Any]:
    """Train on support data, commit all locked predictions, then reveal labels."""
    if train_count < 1 or locked_test_count < 1:
        raise ValueError("train_count and locked_test_count must be positive")

    support = make_dataset(
        train_count, seed, candidate_count, feature_dim, choose_k
    )
    locked_test = make_dataset(
        locked_test_count, seed + 1_000_003, candidate_count, feature_dim, choose_k
    )
    weights = train_ranker(support, feature_dim=feature_dim, epochs=epochs)

    ledger = EvidenceLedger()
    predictions: list[tuple[int, ...]] = []
    for index, example in enumerate(locked_test):
        prediction = predict_indices(example, weights, choose_k)
        predictions.append(prediction)
        ledger.commit(
            commit_id=f"mts0-{seed}-{index}",
            query_id=f"query-{index}",
            scope="e01-sparse-composition-v1",
            input_payload=_example_payload(example),
            model_version="e01-linear-ranker-v1",
            prediction=prediction,
        )

    # Seal the complete prediction batch before the evaluator can reveal any label.
    ledger.seal_commits()

    # The evaluator receives labels only after every prediction is committed.
    for index, example in enumerate(locked_test):
        ledger.reveal(
            evidence_id=f"locked-{seed}-{index}",
            commit_id=f"mts0-{seed}-{index}",
            scope="e01-sparse-composition-v1",
            split=EvidenceSplit.LOCKED_TEST,
            outcome=example.targets,
        )

    evaluator_reveals = ledger.visible_reveals(ConsumerRole.EVALUATOR)
    learner_reveals = ledger.visible_reveals(ConsumerRole.LEARNER)
    selector_reveals = ledger.visible_reveals(ConsumerRole.SELECTOR)
    metrics = score_predictions(
        [Example(row.query, row.candidates, reveal.outcome)
         for row, reveal in zip(locked_test, evaluator_reveals)],
        predictions,
    )
    return {
        "experiment": "MTS-0-prequential-e01",
        "seed": seed,
        "model_version": "e01-linear-ranker-v1",
        "train_samples": train_count,
        "locked_test_samples": locked_test_count,
        "candidate_count": candidate_count,
        "feature_dim": feature_dim,
        "selected_per_example": choose_k,
        "epochs": epochs,
        "metrics": metrics,
        "audit": {
            "prediction_commits": len(ledger.commits),
            "locked_test_reveals": len(ledger.reveals),
            "learner_visible_locked_test_reveals": len(learner_reveals),
            "selector_visible_locked_test_reveals": len(selector_reveals),
            "evaluator_visible_locked_test_reveals": len(evaluator_reveals),
            "prediction_batch_sealed_before_reveal": ledger.commits_sealed,
            "all_predictions_committed_before_reveal": (
                ledger.commits_sealed and len(ledger.commits) == len(ledger.reveals)
            ),
        },
        "learned_weights": weights,
        "limitations": [
            "Synthetic E01 task only; not natural-language understanding.",
            "In-process visibility metadata is not a security boundary.",
            "IID held-out evaluation is not a structural OOD benchmark.",
            "No claim of CPG-EI superiority or general intelligence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=1200)
    parser.add_argument("--test-samples", type=int, default=400)
    parser.add_argument("--epochs", type=int, default=180)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_mts0(
        seed=args.seed,
        train_count=args.train_samples,
        locked_test_count=args.test_samples,
        epochs=args.epochs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
