"""Audit whether a proposed analogy preserves its inferential warrant and scope."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

class TransferStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    MISSING_EVIDENCE = "missing_evidence"
    COUNTEREXAMPLE_BLOCKED = "counterexample_blocked"
    WARRANT_MISMATCH = "warrant_mismatch"
    RELATION_MISMATCH = "relation_mismatch"
    SCOPE_MISMATCH = "scope_mismatch"
    CONDITION_MISMATCH = "condition_mismatch"
    INDETERMINATE = "indeterminate"
    PROVISIONAL_TRANSFER = "provisional_transfer"

@dataclass(frozen=True)
class AnalogyProposal:
    proposal_id: str
    source_case_id: str
    target_case_id: str
    shared_features: Tuple[str, ...]
    transferred_claim: str
    source_warrant: str
    target_warrant: str
    source_relation_signature: Tuple[str, ...]
    target_relation_signature: Tuple[str, ...]
    source_scope: str
    target_scope: str
    evidence_refs: Tuple[str, ...]
    condition_refs: Tuple[str, ...]
    counterexample_refs: Tuple[str, ...]
    reviewed: bool
    warrant_comparable: bool | None
    relation_preserved: bool | None
    scope_compatible: bool | None
    conditions_compatible: bool | None

@dataclass(frozen=True)
class TransferAssessment:
    proposal_id: str
    status: TransferStatus
    failed_gates: Tuple[str, ...]
    unresolved_gates: Tuple[str, ...]
    evidence_count: int
    counterexample_count: int
    transfer_truth_established: bool = False
    semantic_validity_established: bool = False
    adjudication: str = "human_review_required"

def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")

def _refs(values, name, allow_empty=False):
    if not isinstance(values, tuple):
        raise ValueError(f"{name} must be tuple")
    for value in values:
        _nonempty(value, name)
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")
    if not allow_empty and not values:
        raise ValueError(f"{name} must not be empty")

def assess_analogy_transfer(proposal: AnalogyProposal) -> TransferAssessment:
    """Check declared gates; provisional is not a truth judgment."""
    if not isinstance(proposal, AnalogyProposal):
        raise ValueError("proposal must be AnalogyProposal")
    for name in ("proposal_id", "source_case_id", "target_case_id", "transferred_claim", "source_warrant", "target_warrant", "source_scope", "target_scope"):
        _nonempty(getattr(proposal, name), name)
    if proposal.source_case_id == proposal.target_case_id:
        raise ValueError("source and target cases must differ")
    for name in ("shared_features", "source_relation_signature", "target_relation_signature", "evidence_refs", "condition_refs", "counterexample_refs"):
        _refs(getattr(proposal, name), name, allow_empty=name in {"evidence_refs", "condition_refs", "counterexample_refs"})
    if not isinstance(proposal.reviewed, bool):
        raise ValueError("reviewed must be bool")
    for name in ("warrant_comparable", "relation_preserved", "scope_compatible", "conditions_compatible"):
        value = getattr(proposal, name)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"{name} must be bool or None")
    failed, unresolved = [], []
    for name in ("warrant_comparable", "relation_preserved", "scope_compatible"):
        value = getattr(proposal, name)
        if value is False: failed.append(name)
        elif value is None: unresolved.append(name)
    if not proposal.reviewed: status = TransferStatus.UNREVIEWED
    elif proposal.counterexample_refs: status = TransferStatus.COUNTEREXAMPLE_BLOCKED
    elif not proposal.evidence_refs: status = TransferStatus.MISSING_EVIDENCE
    elif "warrant_comparable" in failed: status = TransferStatus.WARRANT_MISMATCH
    elif "relation_preserved" in failed: status = TransferStatus.RELATION_MISMATCH
    elif "scope_compatible" in failed: status = TransferStatus.SCOPE_MISMATCH
    elif "conditions_compatible" in failed: status = TransferStatus.CONDITION_MISMATCH
    elif unresolved: status = TransferStatus.INDETERMINATE
    else: status = TransferStatus.PROVISIONAL_TRANSFER
    return TransferAssessment(proposal.proposal_id, status, tuple(failed), tuple(unresolved), len(proposal.evidence_refs), len(proposal.counterexample_refs))