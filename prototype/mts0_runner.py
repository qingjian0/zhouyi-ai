"""MTS-0: minimal prequential training/evaluation harness.

This module wraps the existing E01 learned sparse-composition baseline with
prediction-before-reveal bookkeeping. It is a research harness, not a secure
multi-process evaluator or a trained language model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
from statistics import mean, stdev
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


@dataclass(frozen=True)
class PublicExample:
    """Locked-test input DTO deliberately excludes target labels."""
    query: tuple[float, ...]
    candidates: tuple[tuple[float, ...], ...]


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


def _example_payload(example: Example | PublicExample) -> dict[str, Any]:
    return {
        "query": example.query,
        "candidates": example.candidates,
    }


def _learner_process(
    connection,
    support: list[Example],
    locked_inputs: list[PublicExample],
    feature_dim: int,
    choose_k: int,
    epochs: int,
) -> None:
    """Train and predict in a process that never receives locked-test labels."""
    try:
        weights = train_ranker(support, feature_dim=feature_dim, epochs=epochs)
        predictions = [
            predict_indices(example, weights, choose_k)
            for example in locked_inputs
        ]
        connection.send({
            "ok": True,
            "pid": os.getpid(),
            "weights": weights,
            "predictions": predictions,
        })
        # Keep the learner process alive until the evaluator has started. This
        # makes the distinct-process audit deterministic rather than PID-reuse
        # dependent.
        if connection.recv() != "release":
            raise RuntimeError("learner process received an invalid release signal")
    except Exception as exc:
        try:
            connection.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


def _evaluator_process(connection, predictions, outcomes) -> None:
    """Evaluate after batch sealing; receives labels but no learner state."""
    try:
        evaluator_examples = [
            Example((), (), tuple(outcome)) for outcome in outcomes
        ]
        metrics = score_predictions(evaluator_examples, predictions)
        connection.send({"ok": True, "pid": os.getpid(), "metrics": metrics})
    except Exception as exc:
        try:
            connection.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


def _receive_process_result(connection, process, label: str, timeout: float = 120.0):
    if not connection.poll(timeout):
        process.terminate()
        process.join(timeout=5)
        raise TimeoutError(f"{label} process did not return within {timeout} seconds")
    try:
        result = connection.recv()
    except EOFError as exc:
        process.join(timeout=5)
        raise RuntimeError(f"{label} process exited without a result") from exc
    if not isinstance(result, dict) or result.get("ok") is not True:
        process.join(timeout=5)
        detail = result.get("error", "invalid worker response") if isinstance(result, dict) else "invalid worker response"
        raise RuntimeError(f"{label} process failed: {detail}")
    return result


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
    """Train in a label-blind learner process, seal commits, then evaluate separately."""
    if train_count < 1 or locked_test_count < 1:
        raise ValueError("train_count and locked_test_count must be positive")

    support = make_dataset(
        train_count, seed, candidate_count, feature_dim, choose_k
    )
    locked_test = make_dataset(
        locked_test_count, seed + 1_000_003, candidate_count, feature_dim, choose_k
    )
    locked_inputs = [
        PublicExample(example.query, example.candidates)
        for example in locked_test
    ]
    outcomes = [example.targets for example in locked_test]

    context = multiprocessing.get_context("spawn")
    learner_parent, learner_child = context.Pipe(duplex=True)
    learner_process = context.Process(
        target=_learner_process,
        args=(learner_child, support, locked_inputs, feature_dim, choose_k, epochs),
        name="mts0-learner",
    )
    evaluator_parent = evaluator_child = evaluator_process = None
    learner_result = None
    try:
        learner_process.start()
        learner_child.close()
        learner_result = _receive_process_result(
            learner_parent, learner_process, "learner"
        )
        weights = learner_result["weights"]
        predictions = [tuple(row) for row in learner_result["predictions"]]
        if len(predictions) != locked_test_count:
            raise RuntimeError("learner returned an incomplete prediction batch")
        model_version = "e01-linear-ranker-v1:" + digest(weights)[:16]

        ledger = EvidenceLedger()
        for index, (example, prediction) in enumerate(zip(locked_inputs, predictions)):
            ledger.commit(
                commit_id=f"mts0-{seed}-{index}",
                query_id=f"query-{index}",
                scope="e01-sparse-composition-v1",
                input_payload=_example_payload(example),
                model_version=model_version,
                prediction=prediction,
            )

        # No evaluator process is started until the complete prediction batch is sealed.
        ledger.seal_commits()
        evaluator_parent, evaluator_child = context.Pipe(duplex=False)
        evaluator_process = context.Process(
            target=_evaluator_process,
            args=(evaluator_child, predictions, outcomes),
            name="mts0-evaluator",
        )
        evaluator_process.start()
        evaluator_child.close()
        evaluator_result = _receive_process_result(
            evaluator_parent, evaluator_process, "evaluator"
        )
        evaluator_process.join(timeout=30)
        if evaluator_process.is_alive() or evaluator_process.exitcode != 0:
            raise RuntimeError("evaluator process did not exit cleanly")

        # Only after evaluator execution are the revealed outcomes appended to the
        # coordinator's audit ledger.
        for index, outcome in enumerate(outcomes):
            ledger.reveal(
                evidence_id=f"locked-{seed}-{index}",
                commit_id=f"mts0-{seed}-{index}",
                scope="e01-sparse-composition-v1",
                split=EvidenceSplit.LOCKED_TEST,
                outcome=outcome,
            )

        evaluator_reveals = ledger.visible_reveals(ConsumerRole.EVALUATOR)
        learner_reveals = ledger.visible_reveals(ConsumerRole.LEARNER)
        selector_reveals = ledger.visible_reveals(ConsumerRole.SELECTOR)
        orchestrator_pid = os.getpid()
        learner_pid = learner_result["pid"]
        evaluator_pid = evaluator_result["pid"]
        metrics = evaluator_result["metrics"]
        return {
            "experiment": "MTS-0-prequential-e01",
            "seed": seed,
            "model_version": model_version,
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
                "orchestrator_pid": orchestrator_pid,
                "learner_pid": learner_pid,
                "evaluator_pid": evaluator_pid,
                "learner_and_evaluator_are_distinct_processes": learner_pid != evaluator_pid,
                "evaluator_started_after_batch_seal": ledger.commits_sealed,
                "learner_received_locked_test_label_count": 0,
                "evaluator_received_locked_test_label_count": len(outcomes),
            },
            "learned_weights": weights,
            "limitations": [
                "Synthetic E01 task only; not natural-language understanding.",
                "Learner and evaluator run in separate spawned processes; the trusted orchestrator still holds labels.",
                "Same-UID process separation is not a security boundary against ptrace, root, or a compromised host.",
                "IID held-out evaluation is not a structural OOD benchmark.",
                "No claim of CPG-EI superiority or general intelligence.",
            ],
        }
    finally:
        # Release the learner only after the evaluator has had a chance to start;
        # always clean up if an exception interrupts the orchestration.
        if learner_process.is_alive():
            try:
                learner_parent.send("release")
            except (BrokenPipeError, EOFError, OSError):
                pass
            learner_process.join(timeout=10)
            if learner_process.is_alive():
                learner_process.terminate()
                learner_process.join(timeout=5)
        if evaluator_process is not None and evaluator_process.is_alive():
            evaluator_process.terminate()
            evaluator_process.join(timeout=5)
        learner_parent.close()
        if evaluator_parent is not None:
            evaluator_parent.close()



def run_mts0_multiseed(
    *,
    start_seed: int = 7,
    seed_count: int = 5,
    train_count: int = 1200,
    locked_test_count: int = 400,
    candidate_count: int = 7,
    feature_dim: int = 6,
    choose_k: int = 3,
    epochs: int = 180,
) -> dict[str, Any]:
    """Run independent seeds and report per-seed metrics plus mean/sample stddev."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2 for variance reporting")
    if train_count < 1 or locked_test_count < 1:
        raise ValueError("sample counts must be positive")
    results = [
        run_mts0(
            seed=start_seed + offset,
            train_count=train_count,
            locked_test_count=locked_test_count,
            candidate_count=candidate_count,
            feature_dim=feature_dim,
            choose_k=choose_k,
            epochs=epochs,
        )
        for offset in range(seed_count)
    ]
    metric_names = tuple(results[0]["metrics"])
    if any(tuple(result["metrics"]) != metric_names for result in results):
        raise RuntimeError("metric schema changed between seeds")
    summary = {
        name: {
            "mean": mean(result["metrics"][name] for result in results),
            "sample_stddev": stdev(result["metrics"][name] for result in results),
        }
        for name in metric_names
    }
    return {
        "experiment": "MTS-0-multiseed-prequential-e01",
        "seed_start": start_seed,
        "seed_count": seed_count,
        "configuration": {
            "train_count": train_count,
            "locked_test_count": locked_test_count,
            "candidate_count": candidate_count,
            "feature_dim": feature_dim,
            "choose_k": choose_k,
            "epochs": epochs,
        },
        "summary": summary,
        "per_seed": [
            {
                "seed": result["seed"],
                "metrics": result["metrics"],
                "audit": result["audit"],
            }
            for result in results
        ],
        "limitations": [
            "Synthetic E01 IID task only; not structural OOD or natural-language evaluation.",
            "Same-process visibility policy is not a security boundary.",
            "Mean and sample standard deviation over seeds do not replace confidence intervals or task-family replication.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--seeds", type=int, default=0,
                        help="Run a multi-seed evaluation; 0 runs one seed.")
    parser.add_argument("--start-seed", type=int, default=7)
    parser.add_argument("--train-samples", type=int, default=1200)
    parser.add_argument("--test-samples", type=int, default=400)
    parser.add_argument("--epochs", type=int, default=180)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.seeds:
        result = run_mts0_multiseed(
            start_seed=args.start_seed,
            seed_count=args.seeds,
            train_count=args.train_samples,
            locked_test_count=args.test_samples,
            epochs=args.epochs,
        )
    else:
        result = run_mts0(
            seed=args.seed,
            train_count=args.train_samples,
            locked_test_count=args.test_samples,
            epochs=args.epochs,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
