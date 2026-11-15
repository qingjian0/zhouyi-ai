"""M11: evidence-bounded audit of dynamic Yixiang relation networks.

Explicit event/trajectory auditor, not a predictor or causal model.
Repeated state signatures are allowed: a state may recur at later steps.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Phase(str, Enum):
    QIONG = "qiong"
    BIAN = "bian"
    TONG = "tong"
    JIU = "jiu"


class DynamicDecision(str, Enum):
    BLOCKED = "blocked_incomplete_or_inconsistent"
    HUMAN_REVIEW = "ready_for_human_review"


@dataclass(frozen=True)
class DynamicSnapshot:
    snapshot_id: str
    subject_id: str
    step: int
    state_signature: str
    context_signature: str
    relation_signatures: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class RelationTransition:
    event_id: str
    subject_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    trigger_condition: str
    change_kind: str
    changed_relations: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class PhaseEvidence:
    phase: Phase
    snapshot_id: str
    relation_signature: str
    window_id: str
    outcome: str
    evidence_ref: str


@dataclass(frozen=True)
class DynamicNetworkAudit:
    subject_id: str
    decision: DynamicDecision
    reason_codes: Tuple[str, ...]
    snapshot_count: int
    transition_count: int
    phase_counts: Tuple[Tuple[str, int], ...]
    durable_relation_signatures: Tuple[str, ...]
    interpretation_ceiling: str = "evidence_bounded_temporal_structure_only"
    non_claims: Tuple[str, ...] = (
        "not_causal_identification",
        "not_future_prediction",
        "not_proof_of_universal_law",
        "not_proof_that_classical_texts_encode_this_algorithm",
    )


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _unique_tuple(values: Tuple[str, ...], field: str, *, allow_empty: bool = False) -> None:
    if not isinstance(values, tuple) or (not values and not allow_empty):
        raise ValueError(f"{field} must be a {'possibly empty' if allow_empty else 'non-empty'} tuple")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{field} entries must be non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{field} entries must be unique")


def audit_dynamic_network(
    snapshots: Tuple[DynamicSnapshot, ...],
    transitions: Tuple[RelationTransition, ...],
    phase_evidence: Tuple[PhaseEvidence, ...],
    *,
    minimum_durable_windows: int = 2,
) -> DynamicNetworkAudit:
    """Audit one subject's ordered snapshots, explicit transitions and phase evidence.

    QIONG requires failed; BIAN requires changed plus a matching incoming
    transition; TONG requires viable and a relation present in the snapshot;
    JIU requires maintained across distinct windows. A pass is HUMAN_REVIEW.
    Cyclic/recurrent state signatures are valid.
    """
    if not isinstance(snapshots, tuple) or not snapshots:
        raise ValueError("snapshots must be a non-empty tuple")
    if not isinstance(transitions, tuple) or not isinstance(phase_evidence, tuple):
        raise ValueError("transitions and phase_evidence must be tuples")
    if isinstance(minimum_durable_windows, bool) or not isinstance(minimum_durable_windows, int) or minimum_durable_windows < 2:
        raise ValueError("minimum_durable_windows must be an integer >= 2")

    snapshot_by_id = {}
    subject_id = None
    previous_step = None
    snapshot_refs = []
    for item in snapshots:
        if not isinstance(item, DynamicSnapshot):
            raise ValueError("snapshots must contain DynamicSnapshot values")
        for field in ("snapshot_id", "subject_id", "state_signature", "context_signature"):
            _nonempty(getattr(item, field), field)
        _unique_tuple(item.relation_signatures, "relation_signatures", allow_empty=True)
        _unique_tuple(item.evidence_refs, "snapshot evidence_refs")
        if isinstance(item.step, bool) or not isinstance(item.step, int) or item.step < 0:
            raise ValueError("snapshot step must be a non-negative integer")
        if subject_id is None:
            subject_id = item.subject_id
        if item.subject_id != subject_id:
            raise ValueError("all snapshots must belong to one subject")
        if item.snapshot_id in snapshot_by_id:
            raise ValueError("snapshot_id values must be unique")
        if previous_step is not None and item.step <= previous_step:
            raise ValueError("snapshot steps must be strictly increasing")
        previous_step = item.step
        snapshot_by_id[item.snapshot_id] = item
        snapshot_refs.extend(item.evidence_refs)

    event_ids = set()
    transition_refs = []
    reasons = []
    incoming = {}
    for event in transitions:
        if not isinstance(event, RelationTransition):
            raise ValueError("transitions must contain RelationTransition values")
        for field in ("event_id", "subject_id", "from_snapshot_id", "to_snapshot_id", "trigger_condition", "change_kind"):
            _nonempty(getattr(event, field), field)
        _unique_tuple(event.changed_relations, "changed_relations")
        _unique_tuple(event.evidence_refs, "transition evidence_refs")
        if event.event_id in event_ids:
            raise ValueError("event_id values must be unique")
        event_ids.add(event.event_id)
        if event.subject_id != subject_id:
            raise ValueError("transition subject_id does not match snapshots")
        if event.from_snapshot_id not in snapshot_by_id or event.to_snapshot_id not in snapshot_by_id:
            reasons.append("TRANSITION_REFERENCES_UNKNOWN_SNAPSHOT")
            continue
        source, target = snapshot_by_id[event.from_snapshot_id], snapshot_by_id[event.to_snapshot_id]
        if source.step >= target.step:
            reasons.append("TRANSITION_TIME_ORDER_INVALID")
        incoming.setdefault(event.to_snapshot_id, []).append(event)
        transition_refs.extend(event.evidence_refs)

    phase_refs = []
    phase_counts = {phase.value: 0 for phase in Phase}
    durable_windows = {}
    phase_keys = set()
    for item in phase_evidence:
        if not isinstance(item, PhaseEvidence):
            raise ValueError("phase_evidence must contain PhaseEvidence values")
        if not isinstance(item.phase, Phase):
            raise ValueError("phase must be a Phase enum value")
        for field in ("snapshot_id", "relation_signature", "window_id", "outcome", "evidence_ref"):
            _nonempty(getattr(item, field), field)
        if item.snapshot_id not in snapshot_by_id:
            reasons.append("PHASE_EVIDENCE_REFERENCES_UNKNOWN_SNAPSHOT")
            continue
        snap = snapshot_by_id[item.snapshot_id]
        key = (item.phase, item.snapshot_id, item.relation_signature, item.window_id)
        if key in phase_keys:
            reasons.append("DUPLICATE_PHASE_EVIDENCE_KEY")
        phase_keys.add(key)
        phase_counts[item.phase.value] += 1
        if item.phase is Phase.QIONG:
            if item.outcome != "failed":
                reasons.append("QIONG_REQUIRES_FAILED_OUTCOME")
        elif item.phase is Phase.BIAN:
            matches = [event for event in incoming.get(item.snapshot_id, ())
                       if item.relation_signature in event.changed_relations]
            if item.outcome != "changed" or not matches:
                reasons.append("BIAN_REQUIRES_EVIDENCED_INCOMING_CHANGE")
        elif item.phase is Phase.TONG:
            if item.outcome != "viable" or item.relation_signature not in snap.relation_signatures:
                reasons.append("TONG_REQUIRES_OBSERVED_VIABLE_RELATION")
        elif item.phase is Phase.JIU:
            if item.outcome != "maintained" or item.relation_signature not in snap.relation_signatures:
                reasons.append("JIU_REQUIRES_OBSERVED_MAINTAINED_RELATION")
            else:
                durable_windows.setdefault(item.relation_signature, set()).add(item.window_id)
        phase_refs.append(item.evidence_ref)

    refs = snapshot_refs + transition_refs + phase_refs
    if len(refs) != len(set(refs)):
        reasons.append("EVIDENCE_REFERENCE_REUSED")
    durable = tuple(sorted(relation for relation, windows in durable_windows.items()
                           if len(windows) >= minimum_durable_windows))
    for relation, windows in durable_windows.items():
        if len(windows) < minimum_durable_windows:
            reasons.append(f"INSUFFICIENT_DURABILITY_WINDOWS:{relation}")

    return DynamicNetworkAudit(
        subject_id=subject_id or "",
        decision=DynamicDecision.BLOCKED if reasons else DynamicDecision.HUMAN_REVIEW,
        reason_codes=tuple(sorted(set(reasons))),
        snapshot_count=len(snapshots),
        transition_count=len(transitions),
        phase_counts=tuple(sorted(phase_counts.items())),
        durable_relation_signatures=durable,
    )
