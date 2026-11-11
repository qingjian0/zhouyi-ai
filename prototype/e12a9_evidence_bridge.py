"""E12-A9: bind evaluator verdicts to lifecycle evidence without overclaiming.

Validates commit/verdict consistency and aggregates scored episodes per
candidate version and scope. Not a signature system: production must
authenticate evaluator provenance independently.
"""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass
from typing import Sequence
from prototype.e12a7_orthogonal_lifecycle import EpistemicStatus, EventKind, LifecycleEvent, OrthogonalLifecycleLedger

@dataclass(frozen=True)
class BoundEvaluation:
    candidate_ref: str
    scope_id: str
    commit_digest: str
    episode_id: str
    prediction: int
    gold_label: int
    scored: bool
    correct: bool

@dataclass(frozen=True)
class EvidenceBatch:
    candidate_ref: str
    scope_id: str
    evidence_id: str
    sample_count: int
    correct_count: int
    error_count: int
    accuracy: float | None
    wilson_lower_bound: float | None
    epistemic_status: EpistemicStatus
    commit_digests: tuple[str, ...]

def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()

def bind_verdict(candidate_ref: str, scope_id: str, commit, verdict) -> BoundEvaluation:
    if not candidate_ref or "@" not in candidate_ref:
        raise ValueError("candidate_ref must identify an immutable candidate version")
    if not scope_id.strip():
        raise ValueError("scope_id must be non-empty")
    if verdict.episode_id != commit.episode_id:
        raise ValueError("verdict episode does not match prediction commit")
    if verdict.commit_digest != commit.commit_digest:
        raise ValueError("verdict is not bound to this prediction commit")
    if not verdict.scored or commit.prediction is None or not commit.identifiable:
        raise ValueError("non-identifiable or unscored prediction cannot be evidence")
    expected = commit.prediction == verdict.gold_label
    if verdict.correct is not expected:
        raise ValueError("verdict correctness is inconsistent with prediction and gold")
    return BoundEvaluation(candidate_ref, scope_id, commit.commit_digest,
                           commit.episode_id, commit.prediction, verdict.gold_label,
                           True, expected)

def _wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        raise ValueError("n must be positive")
    p, z2 = successes / n, z * z
    denom = 1 + z2 / n
    center = p + z2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return (center - margin) / denom

def aggregate_evidence(evaluations: Sequence[BoundEvaluation], *,
                       min_samples: int = 30,
                       required_wilson_lower_bound: float = 0.80) -> EvidenceBatch:
    if min_samples < 1:
        raise ValueError("min_samples must be positive")
    if not 0 < required_wilson_lower_bound <= 1:
        raise ValueError("required_wilson_lower_bound must be in (0, 1]")
    if not evaluations:
        raise ValueError("at least one bound evaluation is required")
    refs, scopes = {e.candidate_ref for e in evaluations}, {e.scope_id for e in evaluations}
    if len(refs) != 1 or len(scopes) != 1:
        raise ValueError("batch must contain one candidate version and one scope")
    digests = [e.commit_digest for e in evaluations]
    if len(set(digests)) != len(digests):
        raise ValueError("duplicate commit digest in evidence batch")
    if any(not e.scored for e in evaluations):
        raise ValueError("unscored evaluations cannot enter evidence batch")
    n = len(evaluations)
    correct = sum(e.correct for e in evaluations)
    errors = n - correct
    accuracy = correct / n
    lower = _wilson_lower_bound(correct, n)
    # Exact synthetic benchmark policy; noisy domains need noise-aware inference.
    status = (EpistemicStatus.CONTRADICTED if errors else
              EpistemicStatus.SUPPORTED if n >= min_samples and lower >= required_wilson_lower_bound
              else EpistemicStatus.UNDERDETERMINED)
    identity = {"candidate_ref": next(iter(refs)), "scope_id": next(iter(scopes)),
                "commit_digests": sorted(digests), "correct_count": correct,
                "sample_count": n, "status": status.value}
    return EvidenceBatch(identity["candidate_ref"], identity["scope_id"],
        "e12a9:" + _sha(identity), n, correct, errors, accuracy, lower, status,
        tuple(sorted(digests)))

def append_evidence(ledger: OrthogonalLifecycleLedger, batch: EvidenceBatch,
                    *, event_id: str | None = None) -> LifecycleEvent:
    event = LifecycleEvent(
        sequence=len(ledger.events) + 1,
        event_id=event_id or batch.evidence_id,
        candidate_ref=batch.candidate_ref,
        kind=EventKind.EPISTEMIC_ASSESSMENT,
        scope_id=batch.scope_id,
        epistemic_status=batch.epistemic_status,
        evidence_ids=(batch.evidence_id,),
        reason=(f"E12-A9 scored={batch.sample_count}, errors={batch.error_count}, "
                f"accuracy={batch.accuracy:.6f}, wilson_lower={batch.wilson_lower_bound:.6f}"))
    ledger.append(event)
    return event
