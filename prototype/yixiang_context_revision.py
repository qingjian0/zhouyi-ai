"""Audit explicit context revisions in analogy reasoning.

This module validates declared bookkeeping only. It does not decide whether a
context change is philosophically, textually, or empirically justified.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class RevisionKind(str, Enum):
    EXPAND = "expand"
    CONTRACT = "contract"
    REVISE = "revise"


class RevisionStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    MISSING_TRIGGER_EVIDENCE = "missing_trigger_evidence"
    INVALID_VERSION = "invalid_version"
    UNDECLARED_CHANGE = "undeclared_change"
    INVALID_REVISION_KIND = "invalid_revision_kind"
    STALE_CLAIMS = "stale_claims"
    CONTEXT_EXPANDED = "context_expanded"
    CONTEXT_CONTRACTED = "context_contracted"
    CONTEXT_REVISED = "context_revised"
    NO_OP = "no_op"


@dataclass(frozen=True)
class ContextSnapshot:
    context_id: str
    version: int
    domain: str
    goal: str
    active_dimensions: Tuple[str, ...]
    excluded_dimensions: Tuple[str, ...]
    assumptions: Tuple[str, ...]


@dataclass(frozen=True)
class ContextRevision:
    revision_id: str
    before: ContextSnapshot
    after: ContextSnapshot
    kind: RevisionKind
    trigger_evidence_refs: Tuple[str, ...]
    rationale: str
    affected_claim_ids: Tuple[str, ...]
    revalidated_claim_ids: Tuple[str, ...]
    added_dimensions: Tuple[str, ...]
    retired_dimensions: Tuple[str, ...]
    added_assumptions: Tuple[str, ...]
    retired_assumptions: Tuple[str, ...]
    changed_axes: Tuple[str, ...]
    reviewed: bool


@dataclass(frozen=True)
class RevisionAssessment:
    revision_id: str
    status: RevisionStatus
    undeclared_changes: Tuple[str, ...]
    stale_claim_ids: Tuple[str, ...]
    added_dimensions: Tuple[str, ...]
    retired_dimensions: Tuple[str, ...]
    semantic_validity_established: bool = False
    adjudication: str = "human_review_required"


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")


def _unique_text(values: Tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field} must be tuple")
    for value in values:
        _require_text(value, field)
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must contain unique values")


def _snapshot(snapshot: ContextSnapshot, field: str) -> None:
    if not isinstance(snapshot, ContextSnapshot):
        raise ValueError(f"{field} must be ContextSnapshot")
    for name in ("context_id", "domain", "goal"):
        _require_text(getattr(snapshot, name), f"{field}.{name}")
    if not isinstance(snapshot.version, int) or isinstance(snapshot.version, bool) or snapshot.version < 0:
        raise ValueError(f"{field}.version must be a non-negative integer")
    for name in ("active_dimensions", "excluded_dimensions", "assumptions"):
        _unique_text(getattr(snapshot, name), f"{field}.{name}")


def assess_context_revision(revision: ContextRevision) -> RevisionAssessment:
    """Audit revision bookkeeping; never certify the truth of a revised analogy."""
    if not isinstance(revision, ContextRevision):
        raise ValueError("revision must be ContextRevision")
    _require_text(revision.revision_id, "revision_id")
    _snapshot(revision.before, "before")
    _snapshot(revision.after, "after")
    _require_text(revision.rationale, "rationale")
    for name in (
        "trigger_evidence_refs", "affected_claim_ids", "revalidated_claim_ids",
        "added_dimensions", "retired_dimensions", "added_assumptions",
        "retired_assumptions", "changed_axes",
    ):
        _unique_text(getattr(revision, name), name)
    if not isinstance(revision.kind, RevisionKind):
        raise ValueError("kind must be RevisionKind")
    if not isinstance(revision.reviewed, bool):
        raise ValueError("reviewed must be bool")

    before, after = revision.before, revision.after
    if before.context_id != after.context_id:
        raise ValueError("context_id must remain stable across a revision")

    added_dimensions = tuple(sorted(set(after.active_dimensions) - set(before.active_dimensions)))
    retired_dimensions = tuple(sorted(set(before.active_dimensions) - set(after.active_dimensions)))
    added_assumptions = tuple(sorted(set(after.assumptions) - set(before.assumptions)))
    retired_assumptions = tuple(sorted(set(before.assumptions) - set(after.assumptions)))
    changed_axes = tuple(
        axis for axis, old, new in (
            ("domain", before.domain, after.domain),
            ("goal", before.goal, after.goal),
        ) if old != new
    )

    undeclared = []
    for label, actual, declared in (
        ("added_dimensions", added_dimensions, revision.added_dimensions),
        ("retired_dimensions", retired_dimensions, revision.retired_dimensions),
        ("added_assumptions", added_assumptions, revision.added_assumptions),
        ("retired_assumptions", retired_assumptions, revision.retired_assumptions),
        ("changed_axes", changed_axes, revision.changed_axes),
    ):
        if set(actual) != set(declared):
            undeclared.append(label)

    changed = bool(added_dimensions or retired_dimensions or added_assumptions or retired_assumptions or changed_axes)
    stale = tuple(sorted(set(revision.affected_claim_ids) - set(revision.revalidated_claim_ids)))

    if not revision.reviewed:
        status = RevisionStatus.UNREVIEWED
    elif before.version + 1 != after.version:
        status = RevisionStatus.INVALID_VERSION
    elif not revision.trigger_evidence_refs:
        status = RevisionStatus.MISSING_TRIGGER_EVIDENCE
    elif undeclared:
        status = RevisionStatus.UNDECLARED_CHANGE
    elif not changed:
        status = RevisionStatus.NO_OP
    elif revision.kind == RevisionKind.EXPAND and (retired_dimensions or retired_assumptions or changed_axes or not (added_dimensions or added_assumptions)):
        status = RevisionStatus.INVALID_REVISION_KIND
    elif revision.kind == RevisionKind.CONTRACT and (added_dimensions or added_assumptions or changed_axes or not (retired_dimensions or retired_assumptions)):
        status = RevisionStatus.INVALID_REVISION_KIND
    elif revision.kind == RevisionKind.REVISE and not changed:
        status = RevisionStatus.INVALID_REVISION_KIND
    elif stale:
        status = RevisionStatus.STALE_CLAIMS
    elif revision.kind == RevisionKind.EXPAND:
        status = RevisionStatus.CONTEXT_EXPANDED
    elif revision.kind == RevisionKind.CONTRACT:
        status = RevisionStatus.CONTEXT_CONTRACTED
    else:
        status = RevisionStatus.CONTEXT_REVISED

    return RevisionAssessment(
        revision_id=revision.revision_id,
        status=status,
        undeclared_changes=tuple(undeclared),
        stale_claim_ids=stale,
        added_dimensions=added_dimensions,
        retired_dimensions=retired_dimensions,
    )
