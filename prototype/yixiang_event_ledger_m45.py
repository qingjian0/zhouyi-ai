"""Append-only event and provenance ledger for Zhouyi-AI experiments."""
from dataclasses import dataclass
from enum import Enum

class EventKind(str, Enum):
    CANDIDATE_SELECTED="candidate_selected"
    EXPERIMENT_APPROVED="experiment_approved"
    EXPERIMENT_EXECUTED="experiment_executed"
    OBSERVATION_RECORDED="observation_recorded"
    BELIEF_UPDATED="belief_updated"
    STOP_DECIDED="stop_decided"
    REVIEW_RECORDED="review_recorded"
    TRANSPORT_AUDITED="transport_audited"

@dataclass(frozen=True)
class ExperimentEvent:
    event_id: str
    sequence: int
    run_id: str
    kind: EventKind
    stage: str
    artifact_ref: str
    evidence_refs: tuple
    context_id: str
    timestamp: str
    actor: str
    payload_ref: str
    previous_event_id: str = ""

@dataclass(frozen=True)
class LedgerAudit:
    valid: bool
    issues: tuple
    event_count: int

def audit_ledger(events):
    events=tuple(events); issues=[]; ids=set(); runs={}
    for i,e in enumerate(events):
        if not e.event_id or e.event_id in ids: issues.append("duplicate_or_empty_event_id")
        ids.add(e.event_id)
        if e.sequence!=i: issues.append("non_contiguous_sequence:"+e.event_id)
        expected=events[i-1].event_id if i else ""
        if e.previous_event_id!=expected: issues.append("broken_event_link:"+e.event_id)
        if not all((e.run_id,e.stage,e.artifact_ref,e.context_id,e.timestamp,e.actor,e.payload_ref)):
            issues.append("missing_required_provenance:"+e.event_id)
        if not e.evidence_refs: issues.append("missing_evidence_refs:"+e.event_id)
        if e.run_id not in runs: runs[e.run_id]=e.context_id
        elif runs[e.run_id]!=e.context_id: issues.append("run_context_changed:"+e.run_id)
    return LedgerAudit(not issues,tuple(sorted(set(issues))),len(events))

def append_event(events,event):
    prior=tuple(events)
    if event.sequence!=len(prior): raise ValueError("sequence_must_append")
    expected=prior[-1].event_id if prior else ""
    if event.previous_event_id!=expected: raise ValueError("previous_event_link_mismatch")
    result=prior+(event,)
    audit=audit_ledger(result)
    if not audit.valid: raise ValueError(";".join(audit.issues))
    return result
