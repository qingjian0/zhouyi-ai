"""Evidence-gated analogy transfer for classical yixiang research.

This module evaluates the completeness and internal consistency of a proposed
source-to-target analogy. It does not discover analogies, authenticate texts,
or prove empirical causality. It deliberately avoids a scalar similarity score.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class TransferKind(str, Enum):
    ATTRIBUTE = "attribute"
    FUNCTION = "function"
    STRUCTURE = "structure"
    PROCESS = "process"
    SPATIAL = "spatial"
    TEMPORAL = "temporal"
    NORMATIVE = "normative"
    CAUSAL = "causal"
    SYMBOLIC = "symbolic"
    RHETORICAL = "rhetorical"


class AnalogyDecision(str, Enum):
    ACCEPT_SCOPED = "accept_scoped"
    CANDIDATE_ONLY = "candidate_only"
    ABSTAIN = "abstain"
    REJECT = "reject"


@dataclass(frozen=True)
class AnalogyTransfer:
    transfer_id: str
    source_case_ref: str
    target_case_ref: str
    transfer_kind: TransferKind
    source_relation: str
    target_relation: str
    shared_basis: Tuple[str, ...]
    relevance_argument: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    critical_differences: Tuple[str, ...]
    source_evidence_refs: Tuple[str, ...]
    target_evidence_refs: Tuple[str, ...]
    counterexamples_tested: Tuple[str, ...]
    unresolved_defeaters: Tuple[str, ...] = ()
    causal_evidence_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalogyAssessment:
    transfer_id: str
    decision: AnalogyDecision
    reason_codes: Tuple[str, ...]
    permitted_claim: str


def _check_text_tuple(name: str, values: Tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise ValueError(f"{name} must be a tuple of non-empty strings")


def assess_analogy_transfer(item: AnalogyTransfer) -> AnalogyAssessment:
    """Assess analogy hygiene; a positive result is scoped, not universal."""
    if not isinstance(item.transfer_id, str) or not item.transfer_id.strip():
        raise ValueError("transfer_id is required")
    for name in (
        "source_case_ref", "target_case_ref", "source_relation", "target_relation"
    ):
        value = getattr(item, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    if not isinstance(item.transfer_kind, TransferKind):
        raise ValueError("transfer_kind must use TransferKind")
    for name in (
        "shared_basis", "relevance_argument", "scope_conditions",
        "critical_differences", "source_evidence_refs", "target_evidence_refs",
        "counterexamples_tested", "unresolved_defeaters", "causal_evidence_refs",
    ):
        _check_text_tuple(name, getattr(item, name))

    reasons = []
    if item.source_relation != item.target_relation:
        return AnalogyAssessment(
            item.transfer_id, AnalogyDecision.REJECT,
            ("RELATION_STRUCTURE_MISMATCH",),
            "不得迁移该关系；只能保留为表面类比或修辞材料。",
        )
    if not item.shared_basis:
        return AnalogyAssessment(
            item.transfer_id, AnalogyDecision.REJECT,
            ("NO_SHARED_RELATIONAL_BASIS",),
            "没有可声明的共同关系依据，不得作推理迁移。",
        )
    if not item.relevance_argument:
        reasons.append("RELEVANCE_OF_SHARED_BASIS_UNJUSTIFIED")
    if not item.scope_conditions:
        reasons.append("SCOPE_CONDITIONS_MISSING")
    if not item.critical_differences:
        reasons.append("CRITICAL_DIFFERENCES_NOT_RECORDED")
    if not item.source_evidence_refs or not item.target_evidence_refs:
        reasons.append("SIDE_SPECIFIC_EVIDENCE_MISSING")
    if not item.counterexamples_tested:
        reasons.append("NO_COUNTEREXAMPLE_TEST")
    if item.unresolved_defeaters:
        reasons.append("UNRESOLVED_DEFEATER_PRESENT")
    if item.transfer_kind == TransferKind.CAUSAL and not item.causal_evidence_refs:
        reasons.append("CAUSAL_TRANSFER_WITHOUT_CAUSAL_EVIDENCE")

    if reasons:
        decision = AnalogyDecision.ABSTAIN
        permitted = "仅可登记为待审类比候选，不得将源域结论断言为目标域事实。"
    else:
        decision = AnalogyDecision.ACCEPT_SCOPED
        permitted = "仅在已记录的共同关系、证据和适用条件内接受迁移；不得外推到未测试范围。"
    return AnalogyAssessment(item.transfer_id, decision, tuple(reasons), permitted)
