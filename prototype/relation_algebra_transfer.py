"""Bridge explicit relation algebra into evidence-scoped yixiang transfer.

The legacy transfer assessor intentionally compares literal predicates. This
adapter permits only ontology-declared symmetry/inverse equivalence while
retaining all role, context, invariant, and defeater gates.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from prototype.relation_algebra import Edge, RelationOntology, RelationScore, compare_relations
from prototype.yixiang_relation_invariants import (
    InvariantDecision,
    RelationTransferAssessment,
    RelationTransferContract,
    assess_relation_transfer,
)


@dataclass(frozen=True)
class AlgebraicTransferAssessment:
    assessment: RelationTransferAssessment
    relation_score: RelationScore


def _zero_score() -> RelationScore:
    return RelationScore(
        precision=0.0, recall=0.0, f1=0.0,
        matched=(), missing=(), unexpected=(),
        projected_source_count=0, target_count=0,
    )


def _fail_closed(
    assessment: RelationTransferAssessment,
    reason: str,
    *,
    reject: bool,
) -> RelationTransferAssessment:
    reasons = assessment.reason_codes
    if reason not in reasons:
        reasons = reasons + (reason,)
    decision = InvariantDecision.REJECT if reject else (
        InvariantDecision.ABSTAIN
        if assessment.decision != InvariantDecision.REJECT
        else InvariantDecision.REJECT
    )
    return replace(assessment, decision=decision, reason_codes=reasons)


def assess_relation_transfer_with_algebra(
    contract: RelationTransferContract,
    ontology: RelationOntology,
) -> AlgebraicTransferAssessment:
    """Assess transfer using declared relation semantics plus existing safety gates.

    A literal topology mismatch is cleared only when every mapped source edge
    matches a target edge under the supplied ontology (F1 == 1). An ontology
    error causes abstention, and a valid but incomplete relation match rejects
    the transfer; neither can inherit a permissive legacy decision.
    """
    base = assess_relation_transfer(contract)
    try:
        relation_score = compare_relations(
            source_relations=tuple(
                Edge(edge.subject_role, edge.object_role, edge.predicate)
                for edge in contract.source.edges
            ),
            target_relations=tuple(
                Edge(edge.subject_role, edge.object_role, edge.predicate)
                for edge in contract.target.edges
            ),
            mapping=dict(contract.role_mapping),
            ontology=ontology,
        )
    except (TypeError, ValueError):
        failed = _fail_closed(
            base, "RELATION_ONTOLOGY_EVALUATION_FAILED", reject=False
        )
        return AlgebraicTransferAssessment(failed, _zero_score())

    if relation_score.f1 != 1.0:
        failed = _fail_closed(
            base, "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH", reject=True
        )
        return AlgebraicTransferAssessment(failed, relation_score)

    if "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH" not in base.reason_codes:
        return AlgebraicTransferAssessment(base, relation_score)

    reasons = tuple(
        reason for reason in base.reason_codes
        if reason != "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH"
    )
    hard_reasons = {"CRITICAL_INVARIANT_NOT_PRESERVED"}
    decision = (
        InvariantDecision.REJECT if any(reason in hard_reasons for reason in reasons)
        else InvariantDecision.ABSTAIN if reasons
        else InvariantDecision.ACCEPT_SCOPED
    )
    return AlgebraicTransferAssessment(
        replace(base, decision=decision, reason_codes=reasons),
        relation_score,
    )
