"""Ontology-aware relation transfer adapter with fail-closed evidence gates.

The legacy yixiang assessor remains the authority for role coverage, context,
polarity/order, evidence, invariants, defeaters, and causal-transfer boundaries.
This adapter only relaxes literal predicate/direction equality when the
versioned relation ontology explicitly declares symmetry or inverse semantics.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

from prototype.relation_algebra import (
    Edge,
    RelationOntology,
    RelationScore,
    compare_relations,
)
from prototype.yixiang_relation_invariants import (
    InvariantDecision,
    RelationTransferAssessment,
    RelationTransferContract,
    assess_relation_transfer,
)


@dataclass(frozen=True)
class AlgebraicTransferAssessment:
    assessment: RelationTransferAssessment
    relation_score: RelationScore | None


def _add_reason(
    assessment: RelationTransferAssessment,
    reason: str,
    *,
    reject: bool = False,
) -> RelationTransferAssessment:
    reasons = assessment.reason_codes
    if reason not in reasons:
        reasons = reasons + (reason,)
    decision = (
        InvariantDecision.REJECT
        if reject or "CRITICAL_INVARIANT_NOT_PRESERVED" in reasons
        else InvariantDecision.ABSTAIN
    )
    return replace(assessment, decision=decision, reason_codes=reasons)


def _edge_metadata_preserved(
    contract: RelationTransferContract,
    ontology: RelationOntology,
) -> bool:
    mapping = dict(contract.role_mapping)
    if set(mapping) != set(contract.source.roles):
        return False
    if set(mapping.values()) != set(contract.target.roles):
        return False

    source = Counter(
        (
            ontology.normalize(Edge(
                mapping[edge.subject_role],
                mapping[edge.object_role],
                edge.predicate,
            )),
            edge.polarity,
            edge.order,
        )
        for edge in contract.source.edges
    )
    target = Counter(
        (
            ontology.normalize(Edge(
                edge.subject_role,
                edge.object_role,
                edge.predicate,
            )),
            edge.polarity,
            edge.order,
        )
        for edge in contract.target.edges
    )
    return source == target


def assess_relation_transfer_with_algebra(
    contract: RelationTransferContract,
    ontology: RelationOntology,
) -> AlgebraicTransferAssessment:
    """Assess a transfer under explicit relation algebra and legacy safety gates.

    Only an exact F1=1.0 match can clear the legacy literal-predicate mismatch.
    Role coverage and normalized edge polarity/order must also be preserved.
    Ontology errors abstain; a valid but incomplete relation match rejects.
    """
    base = assess_relation_transfer(contract)
    # A partial role map is an abstention gate, not evidence of a bad relation.
    if "ROLE_MAPPING_INCOMPLETE" in base.reason_codes:
        return AlgebraicTransferAssessment(base, None)
    if not isinstance(ontology, RelationOntology):
        failed = _add_reason(base, "RELATION_ONTOLOGY_EVALUATION_FAILED")
        return AlgebraicTransferAssessment(failed, None)

    try:
        score = compare_relations(
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
        failed = _add_reason(base, "RELATION_ONTOLOGY_EVALUATION_FAILED")
        return AlgebraicTransferAssessment(failed, None)

    if score.f1 != 1.0:
        failed = _add_reason(
            base, "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH", reject=True
        )
        return AlgebraicTransferAssessment(failed, score)

    # Relation algebra models predicates and endpoints. Preserve the richer
    # Yixiang polarity/order semantics as an independent exact gate.
    try:
        metadata_preserved = _edge_metadata_preserved(contract, ontology)
    except (TypeError, ValueError):
        metadata_preserved = False
    if not metadata_preserved:
        failed = _add_reason(
            base, "RELATION_EDGE_METADATA_MISMATCH", reject=True
        )
        return AlgebraicTransferAssessment(failed, score)

    if "RELATION_TOPOLOGY_OR_DIRECTION_MISMATCH" not in base.reason_codes:
        return AlgebraicTransferAssessment(base, score)

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
        score,
    )
