"""E12-A8 evaluator firewall prototype.

The learner worker receives public observations only. Hidden labels remain in
the coordinator/evaluator process and are never serialized to learner stdin.
This is a process/data-flow boundary, NOT an OS security sandbox.
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

@dataclass(frozen=True)
class PredictionCommit:
    episode_id: str
    query: tuple[int, int]
    prediction: int | None
    identifiable: bool
    consistent_hypotheses: int
    candidate_trace: tuple[tuple[int, int, int], ...]
    public_input_digest: str
    commit_digest: str

    @classmethod
    def from_worker_payload(cls, payload: Mapping[str, object]) -> "PredictionCommit":
        body = {
            "episode_id": str(payload["episode_id"]),
            "query": tuple(int(x) for x in payload["query"]),
            "prediction": None if payload["prediction"] is None else int(payload["prediction"]),
            "identifiable": bool(payload["identifiable"]),
            "consistent_hypotheses": int(payload["consistent_hypotheses"]),
            "candidate_trace": tuple(tuple(int(v) for v in row) for row in payload["candidate_trace"]),
            "public_input_digest": str(payload["public_input_digest"]),
        }
        digest = _digest(body)
        if digest != str(payload["commit_digest"]):
            raise ValueError("prediction commit digest mismatch")
        return cls(**body, commit_digest=digest)

@dataclass(frozen=True)
class EvaluatorVerdict:
    episode_id: str
    commit_digest: str
    gold_label: int
    scored: bool
    correct: bool | None

def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()

def run_learner_process(episode_id: str, support: Sequence[Sequence[int]], query: Sequence[int],
                        *, python_executable: str = sys.executable) -> PredictionCommit:
    """Launch learner with only public support/query; no gold-label argument exists."""
    public = {"episode_id": episode_id, "support": [list(map(int, row)) for row in support],
              "query": list(map(int, query))}
    completed = subprocess.run(
        [python_executable, "-m", "prototype.e12a8_learner_worker"],
        input=_canonical(public).decode("utf-8"), capture_output=True, check=True, text=True)
    return PredictionCommit.from_worker_payload(json.loads(completed.stdout))

class Evaluator:
    """Evaluator-owned labels; never pass this object or its mapping to learner."""
    def __init__(self, hidden_labels: Mapping[str, int]):
        self.__hidden_labels = dict(hidden_labels)
        self.__used_commits: set[str] = set()

    def evaluate(self, commit: PredictionCommit) -> EvaluatorVerdict:
        if commit.commit_digest in self.__used_commits:
            raise ValueError("prediction commit has already been evaluated")
        if commit.episode_id not in self.__hidden_labels:
            raise KeyError("evaluator has no hidden label for episode")
        self.__used_commits.add(commit.commit_digest)
        gold = self.__hidden_labels[commit.episode_id]
        scored = commit.identifiable and commit.prediction is not None
        return EvaluatorVerdict(commit.episode_id, commit.commit_digest, gold, scored,
                                 (commit.prediction == gold) if scored else None)

def commit_payload(commit: PredictionCommit) -> dict[str, object]:
    """Stable public serialization; intentionally excludes evaluator verdict."""
    return asdict(commit)
