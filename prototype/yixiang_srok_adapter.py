"""Compile explicit Yixiang/XSL role transforms into SROK composition operators.

This is a bounded hypothesis proposer, not an analogy-discovery oracle. XSL
supplies an explicit versioned role permutation; SROK explores compatible
typed role assignments over a caller-supplied workspace. Every result remains
HYPOTHESIS_ONLY until independently checked against evidence and scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Iterable

from prototype.srok0_kernel import (
    Node as SrokNode,
    OperatorSpec,
    RoleSpec,
    SearchReport,
    SparseRoleComposer,
)
from prototype.yixiang_analogy import Relation
from prototype.yixiang_role_transform import (
    RoleTransform,
    TransformApplication,
    apply_role_transform,
)


@dataclass(frozen=True)
class CompiledYixiangOperator:
    operator_spec: OperatorSpec
    source_argument_positions: tuple[int, ...]
    transform_id: str
    transform_version: str
    transform_evidence_refs: tuple[str, ...] = ()
    semantic_status: str = "HYPOTHESIS_ONLY"


@dataclass(frozen=True)
class YixiangCompositionResult:
    application: TransformApplication
    compiled_operator: CompiledYixiangOperator
    search: SearchReport
    semantic_status: str = "HYPOTHESIS_ONLY"
    source_relation_evidence_refs: tuple[str, ...] = ()


def compile_yixiang_operator(
    relation: Relation,
    transform: RoleTransform,
    workspace_nodes: Iterable[SrokNode],
    *,
    max_candidates_per_role: int = 32,
    max_expansions: int = 10_000,
) -> CompiledYixiangOperator:
    """Compile an explicit argument permutation into typed SROK role slots."""
    if not isinstance(relation, Relation):
        raise ValueError("relation must be a Relation")
    if not isinstance(transform, RoleTransform):
        raise ValueError("transform must be a RoleTransform")
    if relation.relation_type != transform.source_relation_type:
        raise ValueError("source relation type does not match transform")
    if len(relation.arguments) != transform.arity:
        raise ValueError("relation arity does not match transform")

    rows = tuple(workspace_nodes)
    if any(not isinstance(node, SrokNode) for node in rows):
        raise ValueError("workspace_nodes must contain SROK Node values")
    by_id = {node.node_id: node for node in rows}
    if len(by_id) != len(rows):
        raise ValueError("workspace node IDs must be unique")
    missing = tuple(node_id for node_id in relation.arguments if node_id not in by_id)
    if missing:
        raise ValueError("source relation references nodes missing from workspace")

    roles = []
    for output_position, source_position in enumerate(transform.argument_permutation):
        source_node = by_id[relation.arguments[source_position]]
        roles.append(RoleSpec(
            name=f"target_arg_{output_position}_from_source_arg_{source_position}",
            allowed_types=frozenset({source_node.node_type}),
        ))

    spec = OperatorSpec(
        name=f"yixiang:{transform.transform_id}@{transform.version}",
        relation_type=transform.target_relation_type,
        roles=tuple(roles),
        max_candidates_per_role=max_candidates_per_role,
        max_expansions=max_expansions,
    )
    return CompiledYixiangOperator(
        operator_spec=spec,
        source_argument_positions=transform.argument_permutation,
        transform_id=transform.transform_id,
        transform_version=transform.version,
        transform_evidence_refs=transform.evidence_refs,
    )


def propose_yixiang_compositions(
    relation: Relation,
    transform: RoleTransform,
    workspace_nodes: Iterable[SrokNode],
    *,
    node_scores: Mapping[str, float] | None = None,
    limit: int = 16,
    max_candidates_per_role: int = 32,
    max_expansions: int = 10_000,
    source_relation_evidence_refs: Iterable[str] = (),
) -> YixiangCompositionResult:
    """Apply XSL's explicit transform, then search bounded SROK role bindings."""
    rows = tuple(workspace_nodes)
    compiled = compile_yixiang_operator(
        relation,
        transform,
        rows,
        max_candidates_per_role=max_candidates_per_role,
        max_expansions=max_expansions,
    )
    application = apply_role_transform(relation, transform)

    relation_refs = tuple(sorted(set(source_relation_evidence_refs)))
    if any(not isinstance(ref, str) or not ref.strip() for ref in relation_refs):
        raise ValueError("source_relation_evidence_refs must contain non-empty event refs")
    scores = node_scores or {}
    unknown_scores = set(scores) - {node.node_id for node in rows}
    if unknown_scores:
        raise ValueError("node_scores references unknown workspace nodes")
    scored_rows = tuple(
        SrokNode(
            node_id=node.node_id,
            node_type=node.node_type,
            tags=node.tags,
            score=scores.get(node.node_id, node.score),
            evidence_ids=node.evidence_ids,
        )
        for node in rows
    )
    search = SparseRoleComposer(scored_rows).compose(
        compiled.operator_spec,
        limit=limit,
    )
    return YixiangCompositionResult(
        application=application,
        compiled_operator=compiled,
        search=search,
        source_relation_evidence_refs=relation_refs,
    )
