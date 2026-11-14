"""Cross-track CPG-EI interchange contracts.

Immutable DTOs connect research tracks without creating a second candidate
lifecycle, evidence ledger, or learner/evaluator security boundary.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")

def _refs(values: tuple[str, ...], name: str) -> None:
    if not isinstance(values, tuple) or tuple(sorted(set(values))) != values:
        raise ValueError(f"{name} must be a sorted, unique tuple")
    for value in values:
        _text(value, name)

def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be finite JSON-compatible data") from exc

def validate_canonical_json(value: str, name: str = "payload_json") -> None:
    _text(value, name)
    try:
        parsed = json.loads(value, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{name} must contain valid finite JSON") from exc
    if canonical_json(parsed) != value:
        raise ValueError(f"{name} must use canonical JSON encoding")

def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

class EvidenceSplit(str, Enum):
    SUPPORT = "support"
    GATE_DEV = "gate_dev"
    GATE_FINAL = "gate_final"
    LOCKED_TEST = "locked_test"

class ConsumerRole(str, Enum):
    LEARNER = "learner"
    SELECTOR = "selector"
    EVALUATOR = "evaluator"

class InferenceStatus(str, Enum):
    IDENTIFIED = "identified"
    AMBIGUOUS = "ambiguous"
    INCONSISTENT = "inconsistent"
    UNKNOWN = "unknown"
    ABSTAINED = "abstained"
    BUDGET_EXHAUSTED = "budget_exhausted"

@dataclass(frozen=True)
class CandidateProposal:
    candidate_ref: str
    track_id: str
    scope: str
    grammar_version: str
    definition_digest: str
    evidence_refs: tuple[str, ...] = ()
    estimated_cost: float = 0.0
    complexity: int = 1

    def __post_init__(self) -> None:
        for name in ("candidate_ref", "track_id", "scope", "grammar_version"):
            _text(getattr(self, name), name)
        if "@" not in self.candidate_ref or self.candidate_ref.endswith("@"):
            raise ValueError("candidate_ref must identify an immutable version")
        if not _SHA256_RE.fullmatch(self.definition_digest):
            raise ValueError("definition_digest must be a lowercase SHA-256 digest")
        _refs(self.evidence_refs, "evidence_refs")
        if isinstance(self.estimated_cost, bool) or not isinstance(self.estimated_cost, (int, float)) or not math.isfinite(self.estimated_cost) or self.estimated_cost < 0:
            raise ValueError("estimated_cost must be finite and non-negative")
        if isinstance(self.complexity, bool) or not isinstance(self.complexity, int) or self.complexity < 1:
            raise ValueError("complexity must be a positive integer")

@dataclass(frozen=True)
class PredictionCommit:
    commit_id: str
    candidate_ref: str
    query_id: str
    scope: str
    input_digest: str
    identifiable: bool
    prediction_json: str | None = None
    abstention_reason: str | None = None
    # Optional in the initial v1 DTO for backward compatibility; strict
    # cross-track commits must populate all four context fields.
    episode_id: str | None = None
    learner_track: str | None = None
    split: EvidenceSplit | None = None
    model_version: str | None = None

    def __post_init__(self) -> None:
        for name in ("commit_id", "candidate_ref", "query_id", "scope"):
            _text(getattr(self, name), name)
        for name in ("episode_id", "learner_track", "model_version"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if self.split is not None and not isinstance(self.split, EvidenceSplit):
            raise ValueError("split must be an EvidenceSplit")
        if not _SHA256_RE.fullmatch(self.input_digest):
            raise ValueError("input_digest must be a lowercase SHA-256 digest")
        if not isinstance(self.identifiable, bool):
            raise ValueError("identifiable must be boolean")
        if self.identifiable:
            if self.prediction_json is None:
                raise ValueError("identifiable prediction requires prediction_json")
            validate_canonical_json(self.prediction_json, "prediction_json")
            if self.abstention_reason is not None:
                raise ValueError("identified prediction cannot have abstention_reason")
        else:
            if self.prediction_json is not None:
                raise ValueError("abstaining prediction cannot expose prediction_json")
            _text(self.abstention_reason or "", "abstention_reason")

    @property
    def commit_digest(self) -> str:
        return digest_json({
            "commit_id": self.commit_id, "candidate_ref": self.candidate_ref,
            "query_id": self.query_id, "scope": self.scope,
            "input_digest": self.input_digest, "identifiable": self.identifiable,
            "prediction_json": self.prediction_json,
            "abstention_reason": self.abstention_reason,
            "episode_id": self.episode_id,
            "learner_track": self.learner_track,
            "split": self.split.value if self.split is not None else None,
            "model_version": self.model_version,
        })

@dataclass(frozen=True)
class EvidenceReveal:
    evidence_id: str
    commit_digest: str
    query_id: str
    scope: str
    split: EvidenceSplit
    outcome_json: str
    source_ref: str
    episode_id: str | None = None
    learner_track: str | None = None

    def __post_init__(self) -> None:
        for name in ("evidence_id", "query_id", "scope", "source_ref"):
            _text(getattr(self, name), name)
        for name in ("episode_id", "learner_track"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if not _SHA256_RE.fullmatch(self.commit_digest):
            raise ValueError("commit_digest must be a lowercase SHA-256 digest")
        if not isinstance(self.split, EvidenceSplit):
            raise ValueError("split must be an EvidenceSplit")
        validate_canonical_json(self.outcome_json, "outcome_json")

def validate_reveal_binding(
    commit: PredictionCommit,
    reveal: EvidenceReveal,
    *,
    require_context: bool = False,
) -> None:
    if require_context:
        if commit.episode_id is None or commit.learner_track is None or commit.split is None:
            raise ValueError("strict prediction commit requires episode_id, learner_track and split")
        if commit.model_version is None:
            raise ValueError("strict prediction commit requires model_version")
        if reveal.episode_id is None or reveal.learner_track is None:
            raise ValueError("strict evidence reveal requires episode_id and learner_track")
    if reveal.commit_digest != commit.commit_digest:
        raise ValueError("evidence reveal does not match prediction commit")
    if reveal.query_id != commit.query_id:
        raise ValueError("evidence reveal query does not match prediction")
    if reveal.scope != commit.scope:
        raise ValueError("evidence reveal scope does not match prediction")
    for field in ("episode_id", "learner_track"):
        committed = getattr(commit, field)
        revealed = getattr(reveal, field)
        if committed is not None and revealed != committed:
            raise ValueError(f"evidence reveal {field} does not match prediction")
    if commit.split is not None and reveal.split is not commit.split:
        raise ValueError("evidence reveal split does not match prediction")

def evidence_visible_to(reveal: EvidenceReveal, role: ConsumerRole) -> bool:
    """Metadata policy only; actual isolation requires a process/service boundary."""
    if not isinstance(role, ConsumerRole):
        raise ValueError("role must be a ConsumerRole")
    if role is ConsumerRole.EVALUATOR:
        return True
    if role is ConsumerRole.SELECTOR:
        return reveal.split in (EvidenceSplit.SUPPORT, EvidenceSplit.GATE_DEV)
    return reveal.split is EvidenceSplit.SUPPORT

@dataclass(frozen=True)
class StructureVersion:
    structure_id: str
    version: int
    track_id: str
    scope: str
    grammar_version: str
    definition_digest: str
    parent_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("structure_id", "track_id", "scope", "grammar_version"):
            _text(getattr(self, name), name)
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        if not _SHA256_RE.fullmatch(self.definition_digest):
            raise ValueError("definition_digest must be a lowercase SHA-256 digest")
        _refs(self.parent_refs, "parent_refs")
        _refs(self.evidence_refs, "evidence_refs")
        if self.ref in self.parent_refs:
            raise ValueError("structure version cannot parent itself")

    @property
    def ref(self) -> str:
        return f"{self.structure_id}@{self.version}"

@dataclass(frozen=True)
class InferenceResult:
    query_id: str
    scope: str
    status: InferenceStatus
    ranked_hypothesis_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    budget_used: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _text(self.query_id, "query_id")
        _text(self.scope, "scope")
        if not isinstance(self.status, InferenceStatus):
            raise ValueError("status must be an InferenceStatus")
        if len(set(self.ranked_hypothesis_refs)) != len(self.ranked_hypothesis_refs):
            raise ValueError("ranked_hypothesis_refs must be unique")
        for ref in self.ranked_hypothesis_refs:
            _text(ref, "ranked_hypothesis_refs")
        _refs(self.evidence_refs, "evidence_refs")
        if tuple(sorted(self.budget_used)) != self.budget_used:
            raise ValueError("budget_used must be sorted by resource name")
        if len({name for name, _ in self.budget_used}) != len(self.budget_used):
            raise ValueError("budget resource names must be unique")
        for name, amount in self.budget_used:
            _text(name, "budget resource name")
            if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
                raise ValueError("budget amounts must be non-negative integers")
        if self.status is InferenceStatus.IDENTIFIED and not self.ranked_hypothesis_refs:
            raise ValueError("identified result requires at least one hypothesis")
        if self.status in (InferenceStatus.UNKNOWN, InferenceStatus.INCONSISTENT, InferenceStatus.ABSTAINED) and self.ranked_hypothesis_refs:
            raise ValueError("unknown/inconsistent result cannot rank hypotheses")
