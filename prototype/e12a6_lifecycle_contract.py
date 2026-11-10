"""E12-A6: typed, append-only contracts for primitive lifecycle events.

This module is infrastructure for symbolic experiments. It does not discover
primitives by itself and deliberately has no dependency on a specific learner.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from types import MappingProxyType
from typing import Optional


class SplitRole(str, Enum):
    SUPPORT = "support"
    TRAIN = "train"
    GATE_DEV = "gate_dev"
    GATE_FINAL = "gate_final"
    LOCKED_TEST = "locked_test"
    POST_DEPLOY = "post_deploy"


class CandidateState(str, Enum):
    OBSERVED = "observed"
    PROPOSED = "proposed"
    DISCRIMINATION_PENDING = "discrimination_pending"
    TRAIN_SUPPORTED = "train_supported"
    GATE_VALIDATED = "gate_validated"
    REUSED = "reused"
    CHALLENGED = "challenged"
    REVISED = "revised"
    SPECIALIZED = "specialized"
    RETIRED = "retired"
    REVALIDATION_PENDING = "revalidation_pending"


class ActionType(str, Enum):
    PROPOSE = "propose"
    REQUEST_DISCRIMINATION = "request_discrimination"
    TRAIN_SUPPORT = "train_support"
    GATE_VALIDATE = "gate_validate"
    REUSE = "reuse"
    CHALLENGE = "challenge"
    REVISE = "revise"
    SPECIALIZE = "specialize"
    RETIRE = "retire"
    REQUEST_REVALIDATION = "request_revalidation"
    REGISTER_REVISION = "register_revision"
    REVALIDATE = "revalidate"
    MEASURE = "measure"
    COMPOSE = "compose"
    PREDICT = "predict"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    version: int
    canonical_expression: str
    proposer_family: str
    supporting_families: tuple[str, ...]
    input_types: tuple[str, ...]
    operator: str
    conditions: tuple[str, ...] = ()
    uncertainty: float = 1.0
    complexity: int = 1
    proposal_cost: float = 0.0
    parent_refs: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    state: CandidateState = CandidateState.OBSERVED

    def __post_init__(self) -> None:
        _nonempty(self.candidate_id, "candidate_id")
        _nonempty(self.canonical_expression, "canonical_expression")
        _nonempty(self.proposer_family, "proposer_family")
        _nonempty(self.operator, "operator")
        if not isinstance(self.state, CandidateState):
            raise TypeError("state must be a CandidateState")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("version must be a positive integer")
        if not self.input_types or any(not item for item in self.input_types):
            raise ValueError("input_types must contain non-empty types")
        if any(not item for item in self.supporting_families):
            raise ValueError("supporting_families cannot contain empty values")
        if not math.isfinite(float(self.uncertainty)) or not 0 <= self.uncertainty <= 1:
            raise ValueError("uncertainty must be finite and in [0, 1]")
        _nonnegative(self.complexity, "complexity", allow_zero=False)
        _nonnegative(self.proposal_cost, "proposal_cost")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    episode_id: str
    world_family: str
    split_role: SplitRole
    observation_id: str
    outcome: str
    model_version: str
    measurement_cost: float = 0.0
    prediction_commit_step: Optional[int] = None
    label_visibility_step: Optional[int] = None
    provenance: str = ""

    def __post_init__(self) -> None:
        for name in ("evidence_id", "episode_id", "world_family",
                     "observation_id", "outcome", "model_version"):
            _nonempty(getattr(self, name), name)
        if not isinstance(self.split_role, SplitRole):
            raise TypeError("split_role must be a SplitRole")
        _nonnegative(self.measurement_cost, "measurement_cost")
        commit, reveal = self.prediction_commit_step, self.label_visibility_step
        if (commit is None) != (reveal is None):
            raise ValueError("prediction commit and label visibility steps must be set together")
        if commit is not None:
            _nonnegative(commit, "prediction_commit_step")
            _nonnegative(reveal, "label_visibility_step")
            if commit > reveal:
                raise ValueError("prediction must be committed before label reveal")


@dataclass(frozen=True)
class Action:
    action_id: str
    action_type: ActionType
    candidate_id: Optional[str] = None
    candidate_version: Optional[int] = None
    evidence_ids: tuple[str, ...] = ()
    cost: float = 0.0
    from_state: Optional[CandidateState] = None
    to_state: Optional[CandidateState] = None
    note: str = ""

    def __post_init__(self) -> None:
        _nonempty(self.action_id, "action_id")
        if not isinstance(self.action_type, ActionType):
            raise TypeError("action_type must be an ActionType")
        _nonnegative(self.cost, "cost")
        if (self.candidate_id is None) != (self.candidate_version is None):
            raise ValueError("candidate_id and candidate_version must be set together")
        if self.candidate_id is not None:
            _nonempty(self.candidate_id, "candidate_id")
            _nonnegative(self.candidate_version, "candidate_version", allow_zero=False)
        if (self.from_state is None) != (self.to_state is None):
            raise ValueError("from_state and to_state must be set together")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")


_TRANSITIONS = {
    ActionType.PROPOSE: {(CandidateState.OBSERVED, CandidateState.PROPOSED)},
    ActionType.REQUEST_DISCRIMINATION: {
        (CandidateState.PROPOSED, CandidateState.DISCRIMINATION_PENDING)},
    ActionType.TRAIN_SUPPORT: {
        (CandidateState.DISCRIMINATION_PENDING, CandidateState.TRAIN_SUPPORTED)},
    ActionType.GATE_VALIDATE: {
        (CandidateState.TRAIN_SUPPORTED, CandidateState.GATE_VALIDATED)},
    ActionType.REUSE: {(CandidateState.GATE_VALIDATED, CandidateState.REUSED)},
    ActionType.CHALLENGE: {
        (CandidateState.GATE_VALIDATED, CandidateState.CHALLENGED),
        (CandidateState.REUSED, CandidateState.CHALLENGED)},
    ActionType.REVISE: {(CandidateState.CHALLENGED, CandidateState.REVISED)},
    ActionType.SPECIALIZE: {(CandidateState.CHALLENGED, CandidateState.SPECIALIZED)},
    ActionType.RETIRE: {(CandidateState.CHALLENGED, CandidateState.RETIRED)},
    ActionType.REQUEST_REVALIDATION: {
        (CandidateState.REVISED, CandidateState.REVALIDATION_PENDING),
        (CandidateState.SPECIALIZED, CandidateState.REVALIDATION_PENDING)},
    ActionType.REGISTER_REVISION: {
        (CandidateState.OBSERVED, CandidateState.REVALIDATION_PENDING)},
    ActionType.REVALIDATE: {
        (CandidateState.REVALIDATION_PENDING, CandidateState.GATE_VALIDATED)},
}


def _nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _nonnegative(value: float, name: str, *, allow_zero: bool = True) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    if not math.isfinite(float(value)) or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if not allow_zero else 'non-negative'}")


class LifecycleLedger:
    """In-memory append-only ledger with explicit, versioned candidate identity."""

    __slots__ = ("_candidates", "_evidence", "_actions", "_action_ids")

    def __init__(self) -> None:
        self._candidates: dict[tuple[str, int], Candidate] = {}
        self._evidence: dict[str, Evidence] = {}
        self._actions: list[Action] = []
        self._action_ids: set[str] = set()

    @property
    def candidates(self):
        """Read-only snapshot view; candidate values are frozen dataclasses."""
        return MappingProxyType(self._candidates)

    @property
    def evidence(self):
        """Read-only evidence index; evidence values are frozen dataclasses."""
        return MappingProxyType(self._evidence)

    @property
    def actions(self) -> tuple[Action, ...]:
        """Immutable view of the append-only action sequence."""
        return tuple(self._actions)

    def add_candidate(self, candidate: Candidate) -> None:
        key = (candidate.candidate_id, candidate.version)
        if key in self.candidates:
            raise ValueError(f"duplicate candidate version: {key}")
        if candidate.state is not CandidateState.OBSERVED:
            raise ValueError("new candidates must enter the ledger as OBSERVED")
        self._candidates[key] = candidate

    def add_evidence(self, evidence: Evidence) -> None:
        if evidence.evidence_id in self.evidence:
            raise ValueError(f"duplicate evidence_id: {evidence.evidence_id}")
        self._evidence[evidence.evidence_id] = evidence

    def apply(self, action: Action) -> None:
        if action.action_id in self._action_ids:
            raise ValueError(f"duplicate action_id: {action.action_id}")
        missing = set(action.evidence_ids) - self.evidence.keys()
        if missing:
            raise ValueError(f"unknown evidence IDs: {sorted(missing)}")
        if action.candidate_id is not None:
            key = (action.candidate_id, action.candidate_version)
            if key not in self.candidates:
                raise ValueError(f"unknown candidate version: {key}")
            if action.from_state is not None:
                allowed = (action.from_state, action.to_state)
                if allowed not in _TRANSITIONS.get(action.action_type, set()):
                    raise ValueError("action type does not permit this state transition")
                current = self.candidates[key]
                if current.state is not action.from_state:
                    raise ValueError("stale or invalid candidate state transition")
                roles = {self.evidence[item].split_role for item in action.evidence_ids}
                if action.to_state is CandidateState.TRAIN_SUPPORTED:
                    if SplitRole.TRAIN not in roles:
                        raise ValueError("TRAIN evidence is required for support")
                if action.to_state is CandidateState.GATE_VALIDATED:
                    if SplitRole.GATE_FINAL not in roles:
                        raise ValueError("GATE_FINAL evidence is required for validation")
                if action.to_state is CandidateState.CHALLENGED:
                    roles = {self.evidence[item].split_role for item in action.evidence_ids}
                    if not roles.intersection({SplitRole.LOCKED_TEST, SplitRole.POST_DEPLOY}):
                        raise ValueError("challenge requires LOCKED_TEST or POST_DEPLOY evidence")
                self._candidates[key] = replace(current, state=action.to_state)
            elif action.action_type in _TRANSITIONS:
                raise ValueError("lifecycle action requires an explicit state transition")
        elif action.from_state is not None:
            raise ValueError("state transitions require a candidate reference")
        self._actions.append(action)
        self._action_ids.add(action.action_id)

    def create_revision(
        self,
        candidate_id: str,
        version: int,
        *,
        canonical_expression: str,
        operator: str,
        conditions: tuple[str, ...],
        proposer_family: str,
        supporting_families: tuple[str, ...],
        input_types: tuple[str, ...],
        complexity: int,
        proposal_cost: float,
        evidence_ids: tuple[str, ...] = (),
    ) -> Candidate:
        """Create a new semantic version; never overwrite the challenged version."""
        parent_key = (candidate_id, version)
        parent = self.candidates.get(parent_key)
        if parent is None or parent.state is not CandidateState.REVISED:
            raise ValueError("candidate must have an explicit REVISE action before versioning")
        if any(item not in self.evidence for item in evidence_ids):
            raise ValueError("revision references unknown evidence")
        revision = Candidate(
            candidate_id=candidate_id,
            version=version + 1,
            canonical_expression=canonical_expression,
            proposer_family=proposer_family,
            supporting_families=supporting_families,
            input_types=input_types,
            operator=operator,
            conditions=conditions,
            uncertainty=1.0,
            complexity=complexity,
            proposal_cost=proposal_cost,
            parent_refs=(f"{candidate_id}@{version}",),
            evidence_ids=evidence_ids,
            state=CandidateState.OBSERVED,
        )
        self.add_candidate(revision)
        self.apply(Action(
            action_id=f"{candidate_id}@{version + 1}:register-revision",
            action_type=ActionType.REGISTER_REVISION,
            candidate_id=candidate_id,
            candidate_version=version + 1,
            evidence_ids=evidence_ids,
            from_state=CandidateState.OBSERVED,
            to_state=CandidateState.REVALIDATION_PENDING,
            note=f"semantic revision of {candidate_id}@{version}",
        ))
        return self.candidates[(candidate_id, version + 1)]
