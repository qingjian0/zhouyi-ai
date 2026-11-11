"""ZNCA N3-B: isolated competing hypothesis arenas.

This is a deterministic reference primitive. Hypotheses hold private deltas;
none can mutate the shared state until evidence and conflict gates pass.
It is not a concurrent runtime or a trained reasoning model.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class ArenaError(ValueError):
    """Invalid hypothesis proposal or arena operation."""


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    REJECTED = "REJECTED"
    COMMITTED = "COMMITTED"
    STALE = "STALE"


@dataclass(frozen=True)
class StateSnapshot:
    version: int
    values: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if self.version < 0:
            raise ArenaError("version must be non-negative")
        keys = [key for key, _ in self.values]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ArenaError("snapshot keys must be sorted and unique")
        if any(not key.strip() for key in keys):
            raise ArenaError("snapshot keys must be non-empty")

    @classmethod
    def from_mapping(cls, version: int, values: Mapping[str, str]) -> "StateSnapshot":
        return cls(version, tuple(sorted(values.items())))

    def as_dict(self) -> dict[str, str]:
        return dict(self.values)


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    base_version: int
    read_set: tuple[str, ...]
    write_set: tuple[str, ...]
    state_delta: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]
    status: HypothesisStatus = HypothesisStatus.PROPOSED

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip():
            raise ArenaError("hypothesis_id is required")
        if self.base_version < 0:
            raise ArenaError("base_version must be non-negative")
        for name, values in (("read_set", self.read_set), ("write_set", self.write_set),
                             ("evidence_refs", self.evidence_refs)):
            if any(not value.strip() for value in values):
                raise ArenaError(f"{name} values must be non-empty")
            if len(values) != len(set(values)):
                raise ArenaError(f"{name} must not contain duplicates")
        delta_keys = [key for key, _ in self.state_delta]
        if delta_keys != sorted(delta_keys) or len(delta_keys) != len(set(delta_keys)):
            raise ArenaError("state_delta keys must be sorted and unique")
        if set(delta_keys) != set(self.write_set):
            raise ArenaError("state_delta keys must exactly match write_set")


@dataclass(frozen=True)
class CommitResult:
    status: HypothesisStatus
    snapshot: StateSnapshot
    hypothesis_id: str
    conflict_keys: tuple[str, ...] = ()
    idempotent: bool = False


class HypothesisArena:
    """Fork many hypotheses from one immutable base and gate their commits."""

    def __init__(self, base: StateSnapshot, evidence_refs: Iterable[str] = ()) -> None:
        self._base = base
        self._snapshot = base
        self._known_evidence = set(evidence_refs)
        if any(not ref.strip() for ref in self._known_evidence):
            raise ArenaError("evidence refs must be non-empty")
        self._hypotheses: dict[str, Hypothesis] = {}
        self._committed: list[Hypothesis] = {}
        self._results: dict[str, CommitResult] = {}

    @property
    def snapshot(self) -> StateSnapshot:
        return self._snapshot

    def hypotheses(self) -> tuple[Hypothesis, ...]:
        return tuple(self._hypotheses[key] for key in sorted(self._hypotheses))

    def register_evidence(self, evidence_ref: str) -> None:
        if not evidence_ref.strip():
            raise ArenaError("evidence_ref is required")
        self._known_evidence.add(evidence_ref)

    def propose(self, hypothesis: Hypothesis) -> Hypothesis:
        if hypothesis.hypothesis_id in self._hypotheses:
            raise ArenaError("hypothesis_id must be unique")
        if hypothesis.base_version != self._base.version:
            raise ArenaError("hypotheses must fork from this arena's base version")
        base_keys = set(self._base.as_dict())
        if not set(hypothesis.read_set).issubset(base_keys):
            raise ArenaError("read_set must reference keys in the base snapshot")
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def assess(self, hypothesis_id: str) -> Hypothesis:
        hypothesis = self._get(hypothesis_id)
        if hypothesis.status in (HypothesisStatus.REJECTED, HypothesisStatus.STALE,
                                 HypothesisStatus.COMMITTED):
            return hypothesis
        supported = bool(hypothesis.evidence_refs) and set(
            hypothesis.evidence_refs
        ).issubset(self._known_evidence)
        updated = Hypothesis(
            hypothesis.hypothesis_id, hypothesis.base_version,
            hypothesis.read_set, hypothesis.write_set, hypothesis.state_delta,
            hypothesis.evidence_refs,
            HypothesisStatus.SUPPORTED if supported else HypothesisStatus.CONTESTED,
        )
        self._hypotheses[hypothesis_id] = updated
        return updated

    def reject(self, hypothesis_id: str) -> Hypothesis:
        hypothesis = self._get(hypothesis_id)
        if hypothesis.status in (HypothesisStatus.COMMITTED, HypothesisStatus.STALE):
            raise ArenaError("committed or stale hypotheses cannot be rejected")
        updated = Hypothesis(
            hypothesis.hypothesis_id, hypothesis.base_version,
            hypothesis.read_set, hypothesis.write_set, hypothesis.state_delta,
            hypothesis.evidence_refs, HypothesisStatus.REJECTED,
        )
        self._hypotheses[hypothesis_id] = updated
        return updated

    def commit(self, hypothesis_id: str) -> CommitResult:
        hypothesis = self._get(hypothesis_id)
        prior = self._results.get(hypothesis_id)
        if prior is not None:
            return CommitResult(
                prior.status, prior.snapshot, prior.hypothesis_id,
                prior.conflict_keys, True,
            )
        if hypothesis.status is not HypothesisStatus.SUPPORTED:
            raise ArenaError("only SUPPORTED hypotheses may commit")

        candidate_reads = set(hypothesis.read_set)
        candidate_writes = set(hypothesis.write_set)
        conflicts: set[str] = set()
        for committed in self._committed:
            prior_reads = set(committed.read_set)
            prior_writes = set(committed.write_set)
            conflicts.update(prior_writes & (candidate_reads | candidate_writes))
            conflicts.update(prior_reads & candidate_writes)

        if conflicts:
            stale = self._replace_status(hypothesis, HypothesisStatus.STALE)
            result = CommitResult(
                stale.status, self._snapshot, hypothesis_id, tuple(sorted(conflicts))
            )
            self._results[hypothesis_id] = result
            return result

        values = self._snapshot.as_dict()
        values.update(dict(hypothesis.state_delta))
        next_snapshot = StateSnapshot.from_mapping(self._snapshot.version + 1, values)
        committed = self._replace_status(hypothesis, HypothesisStatus.COMMITTED)
        self._snapshot = next_snapshot
        self._committed.append(committed)
        result = CommitResult(committed.status, next_snapshot, hypothesis_id)
        self._results[hypothesis_id] = result
        return result

    def _get(self, hypothesis_id: str) -> Hypothesis:
        try:
            return self._hypotheses[hypothesis_id]
        except KeyError as exc:
            raise ArenaError("unknown hypothesis_id") from exc

    def _replace_status(
        self, hypothesis: Hypothesis, status: HypothesisStatus
    ) -> Hypothesis:
        updated = Hypothesis(
            hypothesis.hypothesis_id, hypothesis.base_version,
            hypothesis.read_set, hypothesis.write_set, hypothesis.state_delta,
            hypothesis.evidence_refs, status,
        )
        self._hypotheses[hypothesis.hypothesis_id] = updated
        return updated
