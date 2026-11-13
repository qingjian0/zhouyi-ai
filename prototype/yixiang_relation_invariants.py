"""Role-typed relation invariants for scoped classical yixiang transfer."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class InvariantDecision(str, Enum):
    ACCEPT_SCOPED = "accept_scoped"
    ABSTAIN = "abstain"
    REJECT = "reject"

@dataclass(frozen=True)
class RelationEdge:
    predicate: str
    subject_role: str
    object_role: str
    polarity: str = "positive"
    order: int = 0

@dataclass(frozen=True)
class RelationFrame:
    frame_id: str
    domain: str
    roles: Tuple[str, ...]
    edges: Tuple[RelationEdge, ...]
    conditions: Tuple[Tuple[str, str], ...]
    evidence_refs: Tuple[str, ...]

@dataclass(frozen=True)
class InvariantCheck:
    name: str
    source_value: str
    target_value: str
    source_evidence_ref: str
    target_evidence_ref: str
    critical: bool = True

@dataclass(frozen=True)
class RelationTransferContract:
    transfer_id: str
    source: RelationFrame
    target: RelationFrame
    role_mapping: Tuple[Tuple[str, str], ...]
    required_context_axes: Tuple[str, ...]
    invariant_checks: Tuple[InvariantCheck, ...]
    unresolved_defeaters: Tuple[str, ...] = ()
    causal_transfer: bool = False
    causal_evidence_refs: Tuple[str, ...] = ()

@dataclass(frozen=True)
class RelationTransferAssessment:
    transfer_id: str
    decision: InvariantDecision
    reason_codes: Tuple[str, ...]
    mapped_roles: Tuple[Tuple[str, str], ...]
    preserved_invariants: Tuple[str, ...]
    mismatched_critical_invariants: Tuple[str, ...]
    empirical_causality_established: bool = False
    scope_only: bool = True

def _nonempty(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")

def _validate_frame(frame: RelationFrame, label: str) -> None:
    if not isinstance(frame, RelationFrame):
        raise ValueError(f"{label} must be RelationFrame")
    _nonempty(frame.frame_id, f"{label}.frame_id")
    _nonempty(frame.domain, f"{label}.domain")
    if not isinstance(frame.roles, tuple) or not frame.roles:
        raise ValueError(f"{label}.roles must be a non-empty tuple")
    for role in frame.roles:
        _nonempty(role, f"{label}.role")
    if len(set(frame.roles)) != len(frame.roles):
        raise ValueError(f"{label}.roles must be unique")
    if not isinstance(frame.edges, tuple) or not frame.edges:
        raise ValueError(f"{label}.edges must be a non-empty tuple")
    for edge in frame.edges:
        if not isinstance(edge, RelationEdge):
            raise ValueError(f"{label}.edges must contain RelationEdge")
        for field in ("predicate", "subject_role", "object_role", "polarity"):
            _nonempty(getattr(edge, field), f"{label}.edge.{field}")
        if edge.subject_role not in frame.roles or edge.object_role not in frame.roles:
            raise ValueError(f"{label}.edge references an undeclared role")
        if not isinstance(edge.order, int) or isinstance(edge.order, bool):
            raise ValueError(f"{label}.edge.order must be int")
    if not isinstance(frame.conditions, tuple):
        raise ValueError(f"{label}.conditions must be tuple")
    keys = []
    for pair in frame.conditions:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError(f"{label}.conditions must contain pairs")
        _nonempty(pair[0], f"{label}.condition.name")
        _nonempty(pair[1], f"{label}.condition.value")
        keys.append(pair[0])
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label}.condition names must be unique")
    if not isinstance(frame.evidence_refs, tuple) or any(not isinstance(x, str) or not x.strip() for x in frame.evidence_refs):
        raise ValueError(f"{label}.evidence_refs must be non-empty strings")

def _mapped_edges(frame: RelationFrame, role_map: dict[str, str]) -> Counter:
    return Counter((e.predicate, role_map[e.subject_role], role_map[e.object_role], e.polarity, e.order) for e in frame.edges)

def assess_relation_transfer(contract: RelationTransferContract) -> RelationTransferAssessment:
    if not isinstance(contract, RelationTransferContract):
        raise ValueError("contract must be RelationTransferContract")
    _nonempty(contract.transfer_id, "transfer_id")
    _validate_frame(contract.source, "source")
    _validate_frame(contract.target, "target")
    if not isinstance(contract.role_mapping, tuple):
        raise ValueError("role_mapping must be tuple")
    src, tgt, role_map = [], [], {}
    for pair in contract.role_mapping:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("role_mapping entries must be pairs")
        a, b = pair
        _nonempty(a, "mapped source role"); _nonempty(b, "mapped target role")
        src.append(a); tgt.append(b); role_map[a] = b
    if len(src) != len(set(src)) or len(tgt) != len(set(tgt)):
        raise ValueError("role_mapping must be one-to-one")
    if any(x not in contract.source.roles for x in src) or any(x not in contract.target.roles for x in tgt):
        raise ValueError("role_mapping contains unknown role")
    if not isinstance(contract.required_context_axes, tuple) or any(not isinstance(x, str) or not x.strip() for x in contract.required_context_axes):
        raise ValueError("required_context_axes must be a tuple of non-empty strings")
    if len(set(contract.required_context_axes)) != len(contract.required_context_axes):
        raise ValueError("required_context_axes must be unique")
    if not isinstance(contract.invariant_checks, tuple) or any(not isinstance(x, InvariantCheck) for x in contract.invariant_checks):
        raise ValueError("invariant_checks must contain InvariantCheck")
    names = []
    for item in contract.invariant_checks:
        for field in ("name", "source_value", "target_value", "source_evidence_ref", "target_evidence_ref"):
            _nonempty(getattr(item, field), f"invariant.{field}")
        if not isinstance(item.critical, bool):
            raise ValueError("invariant.critical must be bool")
        names.append(item.name)
    if len(names) != len(set(names)):
        raise ValueError("invariant check names must be unique")
    for field in ("unresolved_defeaters", "causal_evidence_refs"):
        values = getattr(contract, field)
        if not isinstance(values, tuple) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f"{field} must be a tuple of non-empty strings")
    if not isinstance(contract.causal_transfer, bool):
        raise ValueError("causal_transfer must be bool")

    reasons, hard, preserved, mismatched = [], [], [], []
    if set(src) != set(contract.source.roles) or set(tgt) != set(contract.target.roles):
        reasons.append("ROLE_MAPPING_INCOMPLETE")
    if not contract.source.evidence_refs or not contract.target.evidence_refs:
        reasons.append("SIDE_SPECIFIC_EVIDENCE_MISSING")
    if set(src) == set(contract.source.roles) and _mapped_edges(contract.source, role_map) != Counter(
        (e.predicate, e.subject_role, e.object_role, e.polarity, e.order) for e in contract.target.edges
    ):
        hard.append("RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH")
    sc, tc = dict(contract.source.conditions), dict(contract.target.conditions)
    for axis in contract.required_context_axes:
        if axis not in sc or axis not in tc:
            reasons.append("REQUIRED_CONTEXT_AXIS_MISSING")
        elif sc[axis] != tc[axis]:
            reasons.append("REQUIRED_CONTEXT_AXIS_MISMATCH")
    for item in contract.invariant_checks:
        if item.source_value == item.target_value:
            preserved.append(item.name)
        elif item.critical:
            mismatched.append(item.name)
    if mismatched:
        hard.append("CRITICAL_INVARIANT_NOT_PRESERVED")
    if contract.unresolved_defeaters:
        reasons.append("UNRESOLVED_DEFEATER_PRESENT")
    if contract.causal_transfer and not contract.causal_evidence_refs:
        reasons.append("CAUSAL_TRANSFER_WITHOUT_CAUSAL_EVIDENCE")
    decision = InvariantDecision.REJECT if hard else InvariantDecision.ABSTAIN if reasons else InvariantDecision.ACCEPT_SCOPED
    return RelationTransferAssessment(contract.transfer_id, decision, tuple(hard + reasons), contract.role_mapping, tuple(preserved), tuple(mismatched), False, True)
