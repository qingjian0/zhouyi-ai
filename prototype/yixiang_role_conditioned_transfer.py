"""M13: joint role, mechanism and context audit for bounded yixiang transfer."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class TransferDecision(str, Enum):
    ACCEPT_SCOPED = "accept_scoped"
    ABSTAIN = "abstain"
    REJECT = "reject"

@dataclass(frozen=True)
class MechanismStep:
    operation: str
    actor_role: str
    input_role: str
    output_role: str
    order: int

@dataclass(frozen=True)
class TransferFrame:
    frame_id: str
    domain: str
    roles: Tuple[str, ...]
    relation_edges: Tuple[Tuple[str, str, str, str, int], ...]
    mechanism: Tuple[MechanismStep, ...]
    context_axes: Tuple[Tuple[str, str], ...]
    evidence_refs: Tuple[str, ...]

@dataclass(frozen=True)
class ContextTransform:
    axis: str
    source_value: str
    target_value: str
    rule: str
    boundary: str
    source_evidence_ref: str
    target_evidence_ref: str

@dataclass(frozen=True)
class TransferContract:
    transfer_id: str
    source: TransferFrame
    target: TransferFrame
    role_mapping: Tuple[Tuple[str, str], ...]
    required_context_axes: Tuple[str, ...]
    context_transforms: Tuple[ContextTransform, ...] = ()
    required_relation_predicates: Tuple[str, ...] = ()
    required_mechanism_operations: Tuple[str, ...] = ()
    unresolved_defeaters: Tuple[str, ...] = ()

@dataclass(frozen=True)
class TransferAssessment:
    transfer_id: str
    decision: TransferDecision
    reason_codes: Tuple[str, ...]
    mapped_roles: Tuple[Tuple[str, str], ...]
    preserved_relation_count: int
    preserved_mechanism_steps: int
    matched_context_axes: Tuple[str, ...]
    transformed_context_axes: Tuple[str, ...]
    missing_context_axes: Tuple[str, ...]
    mismatched_context_axes: Tuple[str, ...]
    scope_only: bool = True
    causal_transfer_established: bool = False
    interpretation_ceiling: str = "bounded_structural_correspondence_only"

def _nonempty(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")

def _unique(values: object, field: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be tuple")
    for value in values:
        _nonempty(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} entries must be unique")

def _validate_frame(frame: TransferFrame, label: str) -> None:
    if not isinstance(frame, TransferFrame):
        raise ValueError(f"{label} must be TransferFrame")
    _nonempty(frame.frame_id, f"{label}.frame_id")
    _nonempty(frame.domain, f"{label}.domain")
    _unique(frame.roles, f"{label}.roles")
    if not frame.roles:
        raise ValueError(f"{label}.roles cannot be empty")
    if not isinstance(frame.relation_edges, tuple) or not frame.relation_edges:
        raise ValueError(f"{label}.relation_edges must be non-empty")
    for edge in frame.relation_edges:
        if not isinstance(edge, tuple) or len(edge) != 5:
            raise ValueError("relation edges need five fields")
        pred, subject, obj, polarity, order = edge
        for name, value in (("predicate", pred), ("subject", subject), ("object", obj), ("polarity", polarity)):
            _nonempty(value, f"{label}.{name}")
        if subject not in frame.roles or obj not in frame.roles:
            raise ValueError("relation edge references undeclared role")
        if not isinstance(order, int) or isinstance(order, bool):
            raise ValueError("relation order must be int")
    if not isinstance(frame.mechanism, tuple) or not frame.mechanism:
        raise ValueError("mechanism must be non-empty")
    orders = []
    for step in frame.mechanism:
        if not isinstance(step, MechanismStep):
            raise ValueError("mechanism must contain MechanismStep")
        for name in ("operation", "actor_role", "input_role", "output_role"):
            _nonempty(getattr(step, name), f"{label}.{name}")
        if any(x not in frame.roles for x in (step.actor_role, step.input_role, step.output_role)):
            raise ValueError("mechanism references undeclared role")
        if not isinstance(step.order, int) or isinstance(step.order, bool):
            raise ValueError("mechanism order must be int")
        orders.append(step.order)
    if len(orders) != len(set(orders)):
        raise ValueError("mechanism order values must be unique")
    if not isinstance(frame.context_axes, tuple):
        raise ValueError("context_axes must be tuple")
    names = []
    for pair in frame.context_axes:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("context axes must be pairs")
        _nonempty(pair[0], "context axis")
        _nonempty(pair[1], "context value")
        names.append(pair[0])
    if len(names) != len(set(names)):
        raise ValueError("context axis names must be unique")
    _unique(frame.evidence_refs, f"{label}.evidence_refs")

def assess_role_conditioned_transfer(contract: TransferContract) -> TransferAssessment:
    """Audit role topology, ordered mechanism and required context jointly."""
    if not isinstance(contract, TransferContract):
        raise ValueError("contract must be TransferContract")
    _nonempty(contract.transfer_id, "transfer_id")
    _validate_frame(contract.source, "source")
    _validate_frame(contract.target, "target")
    for name in ("required_context_axes", "required_relation_predicates", "required_mechanism_operations"):
        _unique(getattr(contract, name), name)
    if not isinstance(contract.role_mapping, tuple):
        raise ValueError("role_mapping must be tuple")
    src, tgt, role_map = [], [], {}
    for pair in contract.role_mapping:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("role mapping entries must be pairs")
        a, b = pair
        _nonempty(a, "source role")
        _nonempty(b, "target role")
        src.append(a); tgt.append(b); role_map[a] = b
    if len(src) != len(set(src)) or len(tgt) != len(set(tgt)):
        raise ValueError("role mapping must be one-to-one")
    if set(src) != set(contract.source.roles) or set(tgt) != set(contract.target.roles):
        raise ValueError("role mapping must cover all roles")
    if not isinstance(contract.context_transforms, tuple):
        raise ValueError("context_transforms must be tuple")
    transforms = {}
    for item in contract.context_transforms:
        if not isinstance(item, ContextTransform):
            raise ValueError("context transforms must contain ContextTransform")
        for name in ("axis", "source_value", "target_value", "rule", "boundary",
                     "source_evidence_ref", "target_evidence_ref"):
            _nonempty(getattr(item, name), f"context_transform.{name}")
        if item.axis in transforms or item.axis not in contract.required_context_axes:
            raise ValueError("context transform axis duplicate or not required")
        if item.source_value == item.target_value:
            raise ValueError("context transform must change value")
        if item.source_evidence_ref not in contract.source.evidence_refs or item.target_evidence_ref not in contract.target.evidence_refs:
            raise ValueError("context transform evidence not grounded")
        transforms[item.axis] = item
    if not isinstance(contract.unresolved_defeaters, tuple):
        raise ValueError("unresolved_defeaters must be tuple")
    for item in contract.unresolved_defeaters:
        _nonempty(item, "unresolved_defeater")

    source_edges = {(p, role_map[s], role_map[o], pol, n) for p, s, o, pol, n in contract.source.relation_edges}
    target_edges = set(contract.target.relation_edges)
    common_edges = source_edges & target_edges
    source_steps = {(x.order, x.operation, role_map[x.actor_role], role_map[x.input_role], role_map[x.output_role]) for x in contract.source.mechanism}
    target_steps = {(x.order, x.operation, x.actor_role, x.input_role, x.output_role) for x in contract.target.mechanism}
    common_steps = source_steps & target_steps
    hard, reasons = [], []
    if source_edges != target_edges:
        hard.append("ROLE_RELATION_TOPOLOGY_DIRECTION_POLARITY_OR_ORDER_MISMATCH")
    if source_steps != target_steps:
        hard.append("MECHANISM_OPERATION_ROLE_OR_ORDER_MISMATCH")
    for pred in contract.required_relation_predicates:
        if pred not in {x[0] for x in source_edges & target_edges}:
            reasons.append("REQUIRED_RELATION_PREDICATE_NOT_PRESERVED")
    for operation in contract.required_mechanism_operations:
        if operation not in {x[1] for x in common_steps}:
            reasons.append("REQUIRED_MECHANISM_OPERATION_NOT_PRESERVED")

    sa, ta = dict(contract.source.context_axes), dict(contract.target.context_axes)
    matched, transformed, missing, mismatched = [], [], [], []
    for axis in contract.required_context_axes:
        if axis not in sa or axis not in ta:
            missing.append(axis)
        elif sa[axis] == ta[axis]:
            matched.append(axis)
        else:
            item = transforms.get(axis)
            if item is None:
                mismatched.append(axis)
            elif item.source_value != sa[axis] or item.target_value != ta[axis]:
                reasons.append("CONTEXT_TRANSFORM_VALUE_MISMATCH")
                mismatched.append(axis)
            else:
                transformed.append(axis)
    if missing:
        reasons.append("REQUIRED_CONTEXT_AXIS_MISSING")
    if mismatched:
        reasons.append("REQUIRED_CONTEXT_AXIS_MISMATCH")
    if not contract.source.evidence_refs or not contract.target.evidence_refs:
        reasons.append("SIDE_SPECIFIC_EVIDENCE_MISSING")
    if set(contract.source.evidence_refs) & set(contract.target.evidence_refs):
        reasons.append("SOURCE_TARGET_EVIDENCE_NOT_INDEPENDENT")
    if contract.unresolved_defeaters:
        reasons.append("UNRESOLVED_DEFEATER_PRESENT")
    decision = TransferDecision.REJECT if hard else TransferDecision.ABSTAIN if reasons else TransferDecision.ACCEPT_SCOPED
    return TransferAssessment(contract.transfer_id, decision, tuple(sorted(set(hard + reasons))),
        contract.role_mapping, len(common_edges), len(common_steps), tuple(sorted(matched)),
        tuple(sorted(transformed)), tuple(sorted(missing)), tuple(sorted(mismatched)))
