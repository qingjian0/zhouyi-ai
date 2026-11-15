"""Explicit context-axis gate for cross-situation yixiang transfer.

This module checks caller-declared context axes only. It does not infer
historical meanings, authenticate evidence, or establish causality.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContextTransferDecision(str, Enum):
    SCOPE_SUPPORTED = "scope_supported"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class ContextualTransferContext:
    context_id: str
    axes: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class ContextualTransferAssessment:
    decision: ContextTransferDecision
    matched_axes: tuple[str, ...]
    mismatched_axes: tuple[str, ...]
    missing_axes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    scope_only: bool = True


def _validate_context(context: ContextualTransferContext) -> None:
    if not isinstance(context, ContextualTransferContext):
        raise ValueError("context must be ContextualTransferContext")
    if not isinstance(context.context_id, str) or not context.context_id.strip():
        raise ValueError("context_id is required")
    if not isinstance(context.axes, tuple):
        raise ValueError("axes must be a tuple")
    keys = []
    for pair in context.axes:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("each axis must be a (name, value) tuple")
        key, value = pair
        if not isinstance(key, str) or not key.strip():
            raise ValueError("axis names must be non-empty strings")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("axis values must be non-empty strings")
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise ValueError("axis names must be unique")
    if not isinstance(context.evidence_refs, tuple) or any(
        not isinstance(ref, str) or not ref.strip() for ref in context.evidence_refs
    ):
        raise ValueError("evidence_refs must be a tuple of non-empty strings")


def assess_contextual_transfer(
    source: ContextualTransferContext,
    target: ContextualTransferContext,
    *,
    required_axes: tuple[str, ...],
) -> ContextualTransferAssessment:
    """Require explicit equality on selected context axes; otherwise abstain.

    The caller chooses which axes matter for the particular transfer. This
    strict baseline intentionally does not guess whether a mismatch is
    transformable. A future mapping layer may justify controlled differences.
    """
    _validate_context(source)
    _validate_context(target)
    if not isinstance(required_axes, tuple) or not required_axes:
        raise ValueError("required_axes must be a non-empty tuple")
    if any(not isinstance(axis, str) or not axis.strip() for axis in required_axes):
        raise ValueError("required axis names must be non-empty strings")
    if len(required_axes) != len(set(required_axes)):
        raise ValueError("required_axes must be unique")

    source_axes = dict(source.axes)
    target_axes = dict(target.axes)
    matched, mismatched, missing = [], [], []
    for axis in required_axes:
        if axis not in source_axes or axis not in target_axes:
            missing.append(axis)
        elif source_axes[axis] == target_axes[axis]:
            matched.append(axis)
        else:
            mismatched.append(axis)

    reasons = []
    if not source.evidence_refs or not target.evidence_refs:
        reasons.append("MISSING_SIDE_SPECIFIC_EVIDENCE")
    if missing:
        reasons.append("REQUIRED_CONTEXT_AXIS_MISSING")
    if mismatched:
        reasons.append("REQUIRED_CONTEXT_AXIS_MISMATCH")
    decision = (
        ContextTransferDecision.ABSTAIN
        if reasons else ContextTransferDecision.SCOPE_SUPPORTED
    )
    return ContextualTransferAssessment(
        decision=decision,
        matched_axes=tuple(matched),
        mismatched_axes=tuple(mismatched),
        missing_axes=tuple(missing),
        reason_codes=tuple(reasons),
        scope_only=True,
    )
