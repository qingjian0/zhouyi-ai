"""Taxonomic scope gate inspired by Mozi Jingxia and Xunzi Zhengming.

It prevents predicates from being transferred across category levels without
explicit membership, scope, and inheritance evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class TaxonomicRelation(str, Enum):
    SAME_LEVEL = "same_level"
    SOURCE_SUBCLASS_OF_TARGET = "source_subclass_of_target"
    TARGET_SUBCLASS_OF_SOURCE = "target_subclass_of_source"
    SIBLING_CATEGORIES = "sibling_categories"


class PredicateScope(str, Enum):
    UNIVERSAL = "universal"
    CLASS_SPECIFIC = "class_specific"
    SUBCLASS_SPECIFIC = "subclass_specific"
    INDIVIDUAL_SPECIFIC = "individual_specific"
    CONTEXTUAL = "contextual"


class TaxonomicDecision(str, Enum):
    SCOPE_RECORDED = "scope_recorded"
    ABSTAIN = "abstain"
    REJECT = "reject"


@dataclass(frozen=True)
class TaxonomicTransferClaim:
    claim_id: str
    source_category: str
    target_category: str
    relation: TaxonomicRelation
    predicate: str
    predicate_scope: PredicateScope
    shared_basis: Tuple[str, ...]
    membership_evidence: Tuple[str, ...]
    scope_conditions: Tuple[str, ...]
    inheritance_evidence: Tuple[str, ...] = ()
    counterexample_refs: Tuple[str, ...] = ()
    counterexample_search_performed: bool = False


@dataclass(frozen=True)
class TaxonomicAssessment:
    claim_id: str
    decision: TaxonomicDecision
    reason_codes: Tuple[str, ...]
    predicate_inheritance_authorized: bool = False


def _validate(claim: TaxonomicTransferClaim) -> None:
    if not isinstance(claim.claim_id, str) or not claim.claim_id.strip():
        raise ValueError("claim_id is required")
    for field, expected in (
        ("relation", TaxonomicRelation),
        ("predicate_scope", PredicateScope),
    ):
        if not isinstance(getattr(claim, field), expected):
            raise ValueError(f"{field} must use its enum")
    for field in ("source_category", "target_category", "predicate"):
        value = getattr(claim, field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} is required")
    for field in ("shared_basis", "membership_evidence", "scope_conditions",
                  "inheritance_evidence", "counterexample_refs"):
        value = getattr(claim, field)
        if not isinstance(value, tuple) or any(
            not isinstance(x, str) or not x.strip() for x in value
        ):
            raise ValueError(f"{field} must be a tuple of non-empty strings")
    if not isinstance(claim.counterexample_search_performed, bool):
        raise ValueError("counterexample_search_performed must be bool")


def assess_taxonomic_transfer(claim: TaxonomicTransferClaim) -> TaxonomicAssessment:
    _validate(claim)
    reasons = []
    if not claim.shared_basis:
        reasons.append("SHARED_BASIS_MISSING")
    if not claim.membership_evidence:
        reasons.append("CATEGORY_MEMBERSHIP_UNGROUNDED")
    if not claim.scope_conditions:
        reasons.append("SCOPE_CONDITIONS_MISSING")

    if claim.relation == TaxonomicRelation.SOURCE_SUBCLASS_OF_TARGET:
        if claim.predicate_scope in (
            PredicateScope.CLASS_SPECIFIC,
            PredicateScope.SUBCLASS_SPECIFIC,
            PredicateScope.INDIVIDUAL_SPECIFIC,
            PredicateScope.CONTEXTUAL,
        ):
            reasons.append("NON_UNIVERSAL_PREDICATE_CANNOT_BE_PROMOTED_UPWARD")
        if claim.predicate_scope == PredicateScope.UNIVERSAL and not claim.inheritance_evidence:
            reasons.append("UNIVERSAL_SCOPE_EVIDENCE_MISSING")
        if not claim.counterexample_search_performed:
            reasons.append("UPWARD_GENERALIZATION_REQUIRES_COUNTEREXAMPLE_SEARCH")
        if claim.counterexample_refs:
            reasons.append("COUNTEREXAMPLE_REQUIRES_SCOPE_REFINEMENT")

    elif claim.relation == TaxonomicRelation.TARGET_SUBCLASS_OF_SOURCE:
        if claim.predicate_scope in (
            PredicateScope.INDIVIDUAL_SPECIFIC,
            PredicateScope.CONTEXTUAL,
        ):
            reasons.append("PREDICATE_NOT_INHERITABLE_TO_SUBCLASS")
        if not claim.inheritance_evidence:
            reasons.append("DOWNWARD_INHERITANCE_EVIDENCE_MISSING")

    elif claim.relation == TaxonomicRelation.SIBLING_CATEGORIES:
        if not claim.inheritance_evidence:
            reasons.append("SIBLING_TRANSFER_REQUIRES_SHARED_RULE_EVIDENCE")
        if claim.predicate_scope != PredicateScope.UNIVERSAL:
            reasons.append("SIBLING_TRANSFER_REQUIRES_UNIVERSAL_PREDICATE")

    if "SHARED_BASIS_MISSING" in reasons:
        decision = TaxonomicDecision.REJECT
    elif reasons:
        decision = TaxonomicDecision.ABSTAIN
    else:
        decision = TaxonomicDecision.SCOPE_RECORDED

    return TaxonomicAssessment(
        claim_id=claim.claim_id,
        decision=decision,
        reason_codes=tuple(reasons),
        predicate_inheritance_authorized=(
            decision == TaxonomicDecision.SCOPE_RECORDED
            and claim.relation == TaxonomicRelation.TARGET_SUBCLASS_OF_SOURCE
        ),
    )
