"""Guarded operationalization of the inference moves named in Mozi, Xiaoqu.

The seven terms describe differentiated components of argumentation, not seven truth guarantees.
This module records scope and blocks common illicit transfers; it does not
claim to settle disputed philological interpretations of the chapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class XiaoquTerm(str, Enum):
    HUO = "huo"     # 或: qualification / non-exhaustiveness
    JIA = "jia"     # 假: hypothetical supposition
    XIAO = "xiao"   # 效: model or standard
    PI = "pi"       # 辟: illustrate by citing another thing
    MOU = "mou"     # 侔: parallel phrasing/propositions
    YUAN = "yuan"   # 援: appeal by symmetry
    TUI = "tui"     # 推: extend by a claimed sameness


# Backward-compatible name: the seven terms are not all the same kind of move.
InferenceMove = XiaoquTerm


class ConclusionKind(str, Enum):
    TAXONOMIC = "taxonomic"
    STRUCTURAL = "structural"
    NORMATIVE = "normative"
    CAUSAL = "causal"
    PRACTICAL = "practical"


class RelationStatus(str, Enum):
    SAME = "same"
    DIFFERENT = "different"
    UNKNOWN = "unknown"


class TransferDecision(str, Enum):
    SCOPE_RECORDED = "scope_recorded"
    ABSTAIN = "abstain"
    REFUSE = "refuse"


@dataclass(frozen=True)
class MoziTransferClaim:
    claim_id: str
    term: XiaoquTerm
    conclusion_kind: ConclusionKind
    source_case: str
    target_case: str
    shared_basis: Tuple[str, ...]
    material_differences: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    supporting_refs: Tuple[str, ...]
    challenging_refs: Tuple[str, ...] = ()
    predicate_relation: RelationStatus = RelationStatus.UNKNOWN
    causal_basis_relation: RelationStatus = RelationStatus.UNKNOWN
    challenge_search_performed: bool = False
    universal_conclusion: bool = False


@dataclass(frozen=True)
class MoziTransferAssessment:
    claim_id: str
    decision: TransferDecision
    reason_codes: Tuple[str, ...]
    move_is_truth_guarantee: bool = False
    causal_conclusion: str = "not_established"


def _validate(claim: MoziTransferClaim) -> None:
    if not isinstance(claim.claim_id, str) or not claim.claim_id.strip():
        raise ValueError("claim_id is required")
    for field in ("term", "conclusion_kind", "predicate_relation", "causal_basis_relation"):
        expected = {
            "term": XiaoquTerm,
            "conclusion_kind": ConclusionKind,
            "predicate_relation": RelationStatus,
            "causal_basis_relation": RelationStatus,
        }[field]
        if not isinstance(getattr(claim, field), expected):
            raise ValueError(f"{field} must use its enum")
    for field in ("source_case", "target_case"):
        value = getattr(claim, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
    for field in ("shared_basis", "material_differences", "scope_conditions",
                  "supporting_refs", "challenging_refs"):
        value = getattr(claim, field)
        if not isinstance(value, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError(f"{field} must be a tuple of non-empty strings")
    for field in ("challenge_search_performed", "universal_conclusion"):
        if not isinstance(getattr(claim, field), bool):
            raise ValueError(f"{field} must be bool")


def assess_mozi_transfer(claim: MoziTransferClaim) -> MoziTransferAssessment:
    """Assess whether a transfer is sufficiently scoped to be recorded."""
    _validate(claim)
    reasons = []
    if not claim.shared_basis:
        reasons.append("NO_EXPLICIT_SHARED_BASIS")
    if not claim.scope_conditions:
        reasons.append("SCOPE_CONDITIONS_MISSING")
    if not claim.material_differences:
        reasons.append("MATERIAL_DIFFERENCES_NOT_RECORDED")
    if claim.predicate_relation == RelationStatus.UNKNOWN:
        reasons.append("PREDICATE_RELATION_UNIDENTIFIED")
    if not claim.supporting_refs:
        reasons.append("SUPPORTING_EVIDENCE_MISSING")
    if claim.predicate_relation == RelationStatus.DIFFERENT:
        reasons.append("PREDICATE_SCOPE_MISMATCH")
    if claim.conclusion_kind == ConclusionKind.CAUSAL:
        if claim.causal_basis_relation == RelationStatus.DIFFERENT:
            reasons.append("SAME_RESULT_DIFFERENT_CAUSE")
        elif claim.causal_basis_relation == RelationStatus.UNKNOWN:
            reasons.append("CAUSAL_BASIS_UNIDENTIFIED")
    if claim.universal_conclusion and not claim.challenge_search_performed:
        reasons.append("UNIVERSAL_CLAIM_WITHOUT_COUNTEREXAMPLE_SEARCH")
    if claim.challenging_refs:
        reasons.append("CHALLENGING_EVIDENCE_REQUIRES_SCOPE_REFINEMENT")

    if "NO_EXPLICIT_SHARED_BASIS" in reasons:
        decision = TransferDecision.REFUSE
    elif reasons:
        decision = TransferDecision.ABSTAIN
    else:
        decision = TransferDecision.SCOPE_RECORDED

    return MoziTransferAssessment(
        claim_id=claim.claim_id,
        decision=decision,
        reason_codes=tuple(reasons),
        move_is_truth_guarantee=False,
        causal_conclusion="not_established",
    )
