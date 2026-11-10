"""E12-A7 minimal orthogonal lifecycle projection.

The event ledger is append-only; snapshots are deterministic projections.
This module is a small symbolic contract prototype, not a learner/evaluator
security boundary and not a causal discovery system.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple


class WorkflowStage(str, Enum):
    OBSERVED = "observed"
    PROPOSED = "proposed"
    DISCRIMINATION_PENDING = "discrimination_pending"
    TRAIN_SUPPORTED = "train_supported"
    GATE_VALIDATED = "gate_validated"
    REUSED = "reused"
    CHALLENGED = "challenged"
    REVISION_PENDING = "revision_pending"
    RETIRED = "retired"


class EpistemicStatus(str, Enum):
    UNKNOWN = "unknown"
    UNDERDETERMINED = "underdetermined"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    REFUTED_IN_SCOPE = "refuted_in_scope"


class ScopeStatus(str, Enum):
    UNTESTED = "untested"
    IN_SCOPE_SUPPORTED = "in_scope_supported"
    OUT_OF_SCOPE = "out_of_scope"
    SHIFT_SUSPECTED = "shift_suspected"
    SPECIALIZED = "specialized"


class InvocationPolicy(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_with_warning"
    REQUIRE_CONFIRMATION = "require_confirmation"
    ABSTAIN = "abstain"


class EventKind(str, Enum):
    WORKFLOW_TRANSITION = "workflow_transition"
    EPISTEMIC_ASSESSMENT = "epistemic_assessment"
    SCOPE_ASSESSMENT = "scope_assessment"


@dataclass(frozen=True)
class CandidateVersion:
    candidate_id: str
    version: int
    definition: str
    grammar_version: str
    parent_refs: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("candidate_id", "definition", "grammar_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        if any(not isinstance(x, str) or not x.strip() for x in self.parent_refs):
            raise ValueError("parent_refs must contain non-empty strings")


@dataclass(frozen=True)
class LifecycleEvent:
    sequence: int
    event_id: str
    candidate_ref: str
    kind: EventKind
    scope_id: Optional[str] = None
    workflow_from: Optional[WorkflowStage] = None
    workflow_to: Optional[WorkflowStage] = None
    epistemic_status: Optional[EpistemicStatus] = None
    scope_status: Optional[ScopeStatus] = None
    evidence_ids: Tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValueError("sequence must be a positive integer")
        for name in ("event_id", "candidate_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.kind, EventKind):
            raise TypeError("kind must be an EventKind")
        if self.scope_id is not None and not self.scope_id.strip():
            raise ValueError("scope_id cannot be blank")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        if any(not isinstance(x, str) or not x.strip() for x in self.evidence_ids):
            raise ValueError("evidence_ids must contain non-empty strings")
        if self.kind is EventKind.WORKFLOW_TRANSITION:
            if self.workflow_from is None or self.workflow_to is None:
                raise ValueError("workflow transition requires from and to stages")
            if self.epistemic_status is not None or self.scope_status is not None:
                raise ValueError("workflow event cannot mutate epistemic or scope status")
        elif self.kind is EventKind.EPISTEMIC_ASSESSMENT:
            if self.scope_id is None or self.epistemic_status is None:
                raise ValueError("epistemic assessment requires scope_id and status")
            if self.workflow_from is not None or self.workflow_to is not None or self.scope_status is not None:
                raise ValueError("epistemic event cannot mutate other dimensions")
            if self.epistemic_status in (EpistemicStatus.SUPPORTED, EpistemicStatus.CONTRADICTED,
                                         EpistemicStatus.REFUTED_IN_SCOPE) and not self.evidence_ids:
                raise ValueError("evidence-backed epistemic status requires evidence_ids")
        elif self.kind is EventKind.SCOPE_ASSESSMENT:
            if self.scope_id is None or self.scope_status is None:
                raise ValueError("scope assessment requires scope_id and status")
            if self.workflow_from is not None or self.workflow_to is not None or self.epistemic_status is not None:
                raise ValueError("scope event cannot mutate other dimensions")


_ALLOWED_TRANSITIONS = {
    (WorkflowStage.OBSERVED, WorkflowStage.PROPOSED),
    (WorkflowStage.PROPOSED, WorkflowStage.DISCRIMINATION_PENDING),
    (WorkflowStage.DISCRIMINATION_PENDING, WorkflowStage.TRAIN_SUPPORTED),
    (WorkflowStage.TRAIN_SUPPORTED, WorkflowStage.GATE_VALIDATED),
    (WorkflowStage.GATE_VALIDATED, WorkflowStage.REUSED),
    (WorkflowStage.GATE_VALIDATED, WorkflowStage.CHALLENGED),
    (WorkflowStage.REUSED, WorkflowStage.CHALLENGED),
    (WorkflowStage.CHALLENGED, WorkflowStage.REVISION_PENDING),
    (WorkflowStage.REVISION_PENDING, WorkflowStage.PROPOSED),
    (WorkflowStage.CHALLENGED, WorkflowStage.RETIRED),
}


def candidate_ref(candidate_id: str, version: int) -> str:
    return f"{candidate_id}@{version}"


class OrthogonalLifecycleLedger:
    """Append-only event ledger with scope-specific evidence projections."""

    def __init__(self) -> None:
        self._candidates: Dict[str, CandidateVersion] = {}
        self._events: list[LifecycleEvent] = []
        self._event_ids: set[str] = set()

    @property
    def events(self) -> Tuple[LifecycleEvent, ...]:
        return tuple(self._events)

    def register(self, candidate: CandidateVersion) -> None:
        ref = candidate_ref(candidate.candidate_id, candidate.version)
        if ref in self._candidates:
            raise ValueError(f"candidate version already registered: {ref}")
        self._candidates[ref] = candidate

    def _project(self) -> dict:
        workflow = {ref: WorkflowStage.OBSERVED for ref in self._candidates}
        epistemic: Dict[tuple[str, str], EpistemicStatus] = {}
        scopes: Dict[tuple[str, str], ScopeStatus] = {}
        for event in self._events:
            ref = event.candidate_ref
            if event.kind is EventKind.WORKFLOW_TRANSITION:
                workflow[ref] = event.workflow_to
            elif event.kind is EventKind.EPISTEMIC_ASSESSMENT:
                epistemic[(ref, event.scope_id)] = event.epistemic_status
            elif event.kind is EventKind.SCOPE_ASSESSMENT:
                scopes[(ref, event.scope_id)] = event.scope_status
        return {"workflow": workflow, "epistemic": epistemic, "scopes": scopes}

    def append(self, event: LifecycleEvent) -> None:
        if event.event_id in self._event_ids:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        if event.sequence != len(self._events) + 1:
            raise ValueError("event sequence must be contiguous and append-only")
        if event.candidate_ref not in self._candidates:
            raise ValueError(f"unknown candidate version: {event.candidate_ref}")
        state = self._project()
        if event.kind is EventKind.WORKFLOW_TRANSITION:
            current = state["workflow"][event.candidate_ref]
            pair = (event.workflow_from, event.workflow_to)
            if current is not event.workflow_from:
                raise ValueError("stale workflow transition")
            if pair not in _ALLOWED_TRANSITIONS:
                raise ValueError("workflow transition is not allowed")
        elif event.kind is EventKind.EPISTEMIC_ASSESSMENT:
            if event.scope_id is None:
                raise ValueError("scope_id required")
            if event.epistemic_status is EpistemicStatus.REFUTED_IN_SCOPE:
                scope = state["scopes"].get((event.candidate_ref, event.scope_id),
                                            ScopeStatus.UNTESTED)
                if scope is ScopeStatus.OUT_OF_SCOPE:
                    raise ValueError("cannot refute a candidate in a declared out-of-scope context")
        self._events.append(event)
        self._event_ids.add(event.event_id)

    def snapshot(self, candidate_id: str, version: int, scope_id: str) -> dict:
        ref = candidate_ref(candidate_id, version)
        if ref not in self._candidates:
            raise ValueError(f"unknown candidate version: {ref}")
        if not isinstance(scope_id, str) or not scope_id.strip():
            raise ValueError("scope_id must be a non-empty string")
        state = self._project()
        workflow = state["workflow"][ref]
        epistemic = state["epistemic"].get((ref, scope_id), EpistemicStatus.UNKNOWN)
        scope = state["scopes"].get((ref, scope_id), ScopeStatus.UNTESTED)

        if workflow is WorkflowStage.RETIRED:
            policy = InvocationPolicy.ABSTAIN
        elif epistemic in (EpistemicStatus.UNDERDETERMINED, EpistemicStatus.CONTRADICTED,
                           EpistemicStatus.REFUTED_IN_SCOPE):
            policy = InvocationPolicy.ABSTAIN
        elif scope in (ScopeStatus.OUT_OF_SCOPE, ScopeStatus.SHIFT_SUSPECTED,
                       ScopeStatus.UNTESTED):
            policy = InvocationPolicy.ABSTAIN
        elif workflow is WorkflowStage.CHALLENGED:
            policy = InvocationPolicy.ABSTAIN
        elif workflow is WorkflowStage.REVISION_PENDING:
            policy = InvocationPolicy.REQUIRE_CONFIRMATION
        elif workflow in (WorkflowStage.GATE_VALIDATED, WorkflowStage.REUSED) and epistemic is EpistemicStatus.SUPPORTED and scope is ScopeStatus.IN_SCOPE_SUPPORTED:
            policy = InvocationPolicy.ALLOW
        elif scope is ScopeStatus.SPECIALIZED:
            policy = InvocationPolicy.REQUIRE_CONFIRMATION
        else:
            policy = InvocationPolicy.ABSTAIN

        return {
            "candidate_ref": ref,
            "workflow_stage": workflow.value,
            "epistemic_status": epistemic.value,
            "scope_status": scope.value,
            "invocation_policy": policy.value,
        }

    def replay(self) -> dict:
        """Return the deterministic full projection, useful for replay checks."""
        state = self._project()
        return {
            "workflow": {k: v.value for k, v in sorted(state["workflow"].items())},
            "epistemic": {f"{k[0]}|{k[1]}": v.value for k, v in sorted(state["epistemic"].items())},
            "scopes": {f"{k[0]}|{k[1]}": v.value for k, v in sorted(state["scopes"].items())},
        }
