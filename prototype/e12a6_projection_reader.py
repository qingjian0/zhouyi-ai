"""Lazy, read-only access to the E12-A6 SQLite current-state projections.

The append-only ZPCM event log remains authoritative. This reader never builds a
whole LifecycleLedger unless the caller explicitly requests materialization.
"""
from __future__ import annotations

from typing import Iterator

from prototype.e12a6_lifecycle_contract import (
    Action, Candidate, Evidence, LifecycleLedger,
)
from prototype.e12a6_zpcm_persistence import (
    LifecyclePersistenceError, _action_from_dict, _candidate_from_dict,
    _evidence_from_dict,
)
from prototype.zpcm_memory import ZPCMMemory


class LifecycleProjectionReader:
    """Scoped, lazy projection reader; not a replacement for event replay validation."""

    def __init__(self, memory: ZPCMMemory, *, scope: str) -> None:
        if not isinstance(memory, ZPCMMemory):
            raise TypeError("memory must be ZPCMMemory")
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope required")
        self._memory = memory
        self.scope = scope

    def counts(self) -> dict[str, int]:
        with self._memory.lock:
            return self._memory.lifecycle_state_projection_counts(scope=self.scope)

    def get_candidate(self, candidate_id: str, version: int) -> Candidate | None:
        with self._memory.lock:
            row = self._memory.get_lifecycle_candidate_projection(
                scope=self.scope, candidate_id=candidate_id, candidate_version=version,
            )
        return None if row is None else _candidate_from_dict(row["candidate"])

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        with self._memory.lock:
            row = self._memory.get_lifecycle_evidence_projection(
                scope=self.scope, evidence_id=evidence_id,
            )
        return None if row is None else _evidence_from_dict(row["evidence"])

    def get_action(self, action_id: str) -> Action | None:
        with self._memory.lock:
            row = self._memory.get_lifecycle_action_projection(
                scope=self.scope, action_id=action_id,
            )
        return None if row is None else _action_from_dict(row["action"])

    def iter_candidates(self, *, page_size: int = 256) -> Iterator[Candidate]:
        for row in self._memory.iter_lifecycle_candidate_projections(
            scope=self.scope, page_size=page_size,
        ):
            yield _candidate_from_dict(row["candidate"])

    def iter_evidence(self, *, page_size: int = 256) -> Iterator[Evidence]:
        for row in self._memory.iter_lifecycle_evidence_projections(
            scope=self.scope, page_size=page_size,
        ):
            yield _evidence_from_dict(row["evidence"])

    def iter_actions(self, *, page_size: int = 256) -> Iterator[Action]:
        for row in self._memory.iter_lifecycle_action_projections(
            scope=self.scope, page_size=page_size,
        ):
            yield _action_from_dict(row["action"])

    def verify(self) -> dict[str, int | str | bool]:
        """Digest-check the event stream and compare all scoped projection rows."""
        return self._memory.verify_e12a6_current_state_projection(scope=self.scope)

    def materialize_ledger(self, *, require_verified: bool = True) -> LifecycleLedger:
        """Explicitly build a full in-memory ledger; O(scope state) memory by design."""
        if require_verified:
            report = self.verify()
            if not report["ok"]:
                raise LifecyclePersistenceError(
                    "cannot materialize an inconsistent lifecycle projection"
                )
        ledger = LifecycleLedger()
        for evidence in self.iter_evidence():
            ledger.evidence[evidence.evidence_id] = evidence
        for candidate in self.iter_candidates():
            ledger.candidates[(candidate.candidate_id, candidate.version)] = candidate
        for action in self.iter_actions():
            ledger.actions.append(action)
            ledger._action_ids.add(action.action_id)
        return ledger
