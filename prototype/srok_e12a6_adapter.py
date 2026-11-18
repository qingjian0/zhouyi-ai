"""Project SROK compositions into the authoritative E12-A6 lifecycle.

SROK proposes a structure; E12-A6 owns its lifecycle. Ranking scores are kept
as uncalibrated metadata and are never converted into confidence/uncertainty.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from prototype.cpg_interop import canonical_json, digest_json
from prototype.e12a6_interop_adapter import E12A6AdapterResult, adapt_candidate
from prototype.e12a6_lifecycle_contract import Candidate, CandidateState
from prototype.srok0_kernel import ComposedCandidate, Node


@dataclass(frozen=True)
class SROKLifecycleProjection:
    native_candidate: Candidate
    interchange: E12A6AdapterResult
    raw_score: float
    score_semantics: str = "uncalibrated_ranking_score"


def adapt_composed_candidate(
    composed: ComposedCandidate,
    nodes_by_id: Mapping[str, Node],
    *,
    scope: str,
    grammar_version: str,
    estimated_cost: float = 0.0,
    version: int = 1,
) -> SROKLifecycleProjection:
    """Create an OBSERVED E12-A6 candidate and read-only CPG-EI projection.

    The caller must add the native candidate to LifecycleLedger, then use an
    explicit PROPOSE action to transition it to PROPOSED. Evidence references
    are preserved but not authenticated or inserted into E12-A6 by this
    adapter. A raw SROK score is a ranking value, not a probability.
    """
    if not isinstance(composed, ComposedCandidate):
        raise TypeError("composed must be a SROK ComposedCandidate")
    if not isinstance(nodes_by_id, Mapping):
        raise TypeError("nodes_by_id must be a mapping")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("scope must be a non-empty string")
    if not isinstance(grammar_version, str) or not grammar_version.strip():
        raise ValueError("grammar_version must be a non-empty string")
    if not isinstance(composed.score, (int, float)) or isinstance(composed.score, bool) or not math.isfinite(composed.score):
        raise ValueError("composed score must be a finite number")
    if not isinstance(composed.relation_type, str) or not composed.relation_type.strip():
        raise ValueError("composed candidate requires a relation type")
    if not isinstance(composed.role_bindings, tuple) or len(composed.role_bindings) < 2:
        raise ValueError("composed candidate requires at least two ordered role bindings")

    role_names = [role for role, _ in composed.role_bindings]
    member_ids = [node_id for _, node_id in composed.role_bindings]
    if any(not isinstance(value, str) or not value.strip() for value in role_names + member_ids):
        raise ValueError("role names and member IDs must be non-empty strings")
    if len(role_names) != len(set(role_names)):
        raise ValueError("role names must be unique")
    if len(member_ids) != len(set(member_ids)):
        raise ValueError("member IDs must be unique")
    if not isinstance(composed.evidence_ids, tuple):
        raise ValueError("evidence_ids must be a tuple")
    if any(not isinstance(value, str) or not value.strip() for value in composed.evidence_ids):
        raise ValueError("evidence IDs must be non-empty strings")
    if len(composed.evidence_ids) != len(set(composed.evidence_ids)):
        raise ValueError("evidence IDs must be unique")

    bound_nodes = []
    for node_id in member_ids:
        node = nodes_by_id.get(node_id)
        if not isinstance(node, Node) or node.node_id != node_id:
            raise ValueError(f"missing or invalid SROK node: {node_id}")
        bound_nodes.append(node)

    definition = {
        "relation_type": composed.relation_type,
        "role_bindings": [
            {"role": role, "node_id": node_id, "node_type": node.node_type}
            for (role, node_id), node in zip(composed.role_bindings, bound_nodes)
        ],
    }
    canonical_expression = canonical_json(definition)
    candidate_id = "srok0:" + digest_json(definition)
    native = Candidate(
        candidate_id=candidate_id,
        version=version,
        canonical_expression=canonical_expression,
        proposer_family="srok0",
        supporting_families=("srok0",),
        input_types=tuple(node.node_type for node in bound_nodes),
        operator=composed.relation_type,
        conditions=(),
        uncertainty=1.0,
        complexity=len(composed.role_bindings),
        proposal_cost=estimated_cost,
        parent_refs=(),
        evidence_ids=composed.evidence_ids,
        state=CandidateState.OBSERVED,
    )
    interchange = adapt_candidate(
        native, scope=scope, grammar_version=grammar_version
    )
    return SROKLifecycleProjection(
        native_candidate=native,
        interchange=interchange,
        raw_score=float(composed.score),
    )
