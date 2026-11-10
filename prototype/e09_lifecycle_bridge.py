"""Adapter from E09 evidence records to the E02-C lifecycle proposal API.

This adapter does not discover members or infer a relation. The caller must
supply the proposed member/role mapping and held-out validation measurement.
It only enforces evidence provenance and contested-record exclusion.
"""
from __future__ import annotations

from prototype.e02_edge_lifecycle import EdgeProposal
from prototype.e09_evidence_ledger import EvidenceLedger, EvidenceError


def proposal_from_ledger(
    ledger: EvidenceLedger,
    *,
    edge_id: str,
    members: tuple[str, ...],
    roles: tuple[str, ...],
    relation_type: str,
    positive_label: object,
    validation_gain: float,
    cost: float,
    min_independent_sources: int = 3,
) -> EdgeProposal:
    """Build a lifecycle proposal from uncontested labeled evidence.

    Positive support requires distinct, non-empty source IDs. Negative records
    become counterexamples. Contested inputs are excluded from both sets.
    Evidence sample IDs remain attached for auditability.
    """
    if min_independent_sources < 1:
        raise ValueError("min_independent_sources must be positive")
    adjudication = ledger.adjudication()
    contested_inputs = {
        tuple(item["inputs"]) for item in adjudication["contested"]
    }
    records = [
        record for record in ledger.records()
        if record.example.inputs not in contested_inputs
    ]
    support = [
        record for record in records if record.example.label == positive_label
    ]
    counter = [
        record for record in records if record.example.label != positive_label
    ]
    source_ids = {record.source_id for record in support if record.source_id.strip()}
    if len(source_ids) < min_independent_sources:
        raise EvidenceError(
            "insufficient distinct positive source IDs: "
            f"{len(source_ids)} < {min_independent_sources}"
        )
    if any(not record.source_id.strip() for record in support):
        raise EvidenceError(
            "positive support contains records without source_id; "
            "cannot certify independent support"
        )
    support_ids = tuple(record.sample_id for record in support)
    counterexample_ids = tuple(record.sample_id for record in counter)
    if set(support_ids) & set(counterexample_ids):
        raise EvidenceError("sample IDs overlap between support and counterexamples")
    return EdgeProposal(
        edge_id=edge_id,
        members=members,
        roles=roles,
        relation_type=relation_type,
        support_ids=support_ids,
        counterexample_ids=counterexample_ids,
        validation_gain=validation_gain,
        cost=cost,
    )
