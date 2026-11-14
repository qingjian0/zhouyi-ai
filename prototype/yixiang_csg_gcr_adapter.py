"""Evidence-preserving bridge from Yixiang/SROK hypotheses into typed CSG-GCR.

SROK alternatives from one search are mutually exclusive hypotheses, not facts.
Transform-prior references are kept as derivation metadata and are never
misrepresented as observational evidence. E09/E12-A6/ZPCM remain separate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from prototype.csg_gcr_coordinator import CandidateProposal, GlobalConstraints
from prototype.typed_csg_gcr import (
    TypedCandidateCoordinator,
    TypedCandidateProposal,
    TypedCoordinationReport,
)
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal,
    RoleBinding,
    VariableRef,
    VariableSpec,
)
from prototype.yixiang_srok_adapter import YixiangCompositionResult


@dataclass(frozen=True)
class YixiangCsgGcrResult:
    proposals: tuple[TypedCandidateProposal, ...]
    coordination: TypedCoordinationReport
    transform_evidence_refs: tuple[str, ...]
    semantic_status: str = "HYPOTHESIS_ONLY"


def _proposal_id(transform_id: str, version: str, relation_type: str,
                 bindings: tuple[tuple[str, str], ...]) -> str:
    payload = json.dumps(
        [transform_id, version, relation_type, bindings],
        ensure_ascii=False, separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"yx-{digest}"


def compile_yixiang_typed_proposals(
    result: YixiangCompositionResult,
    *,
    parent_state_ref: str,
    branch_id: str,
) -> tuple[TypedCandidateProposal, ...]:
    """Compile each SROK assignment as a separate, mutually-exclusive hypothesis."""
    if not isinstance(result, YixiangCompositionResult):
        raise ValueError("result must be YixiangCompositionResult")
    for value, field in ((parent_state_ref, "parent_state_ref"), (branch_id, "branch_id")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")

    operator = result.compiled_operator.operator_spec
    role_types = {}
    for role in operator.roles:
        if len(role.allowed_types) != 1:
            raise ValueError("compiled Yixiang roles must have exactly one grounded member type")
        role_types[role.name] = next(iter(role.allowed_types))

    rows = []
    for candidate in result.search.candidates:
        bindings = tuple(sorted(candidate.role_bindings))
        if not bindings:
            raise ValueError("SROK candidate must contain at least one role binding")
        if {role for role, _ in bindings} != set(role_types):
            raise ValueError("SROK candidate roles do not match the compiled operator")
        if candidate.relation_type != operator.relation_type:
            raise ValueError("SROK candidate relation type differs from compiled operator")

        proposal_id = _proposal_id(
            result.compiled_operator.transform_id,
            result.compiled_operator.transform_version,
            candidate.relation_type,
            bindings,
        )
        variables = []
        role_bindings = []
        for role, member_id in bindings:
            member_type = role_types[role]
            variable = VariableRef(f"yixiang:{proposal_id}", role)
            variables.append(VariableSpec(variable, member_type))
            role_bindings.append(RoleBinding(role, variable, member_id, member_type))

        evidence_refs = tuple(sorted(set(candidate.evidence_ids).union(
            result.source_relation_evidence_refs
        )))
        edge = HyperedgeProposal(
            edge_id=proposal_id,
            parent_state_ref=parent_state_ref,
            branch_id=branch_id,
            relation_type=candidate.relation_type,
            roles=tuple(role_bindings),
            evidence_refs=evidence_refs,
        )
        rows.append((proposal_id, candidate, edge, tuple(variables), evidence_refs))

    # Every result in one SROK search is an alternative assignment. Explicit
    # symmetric exclusions prevent CSG-GCR from combining alternatives as facts.
    all_ids = tuple(row[0] for row in rows)
    proposals = []
    for proposal_id, candidate, edge, variables, evidence_refs in rows:
        excludes = tuple(sorted(item for item in all_ids if item != proposal_id))
        proposal = CandidateProposal(
            proposal_id=proposal_id,
            parent_state_ref=parent_state_ref,
            branch_id=branch_id,
            bindings=(),
            evidence_refs=evidence_refs,
            excludes=excludes,
            score=float(candidate.score),
            cost=max(1, len(candidate.role_bindings)),
            candidate_kind=(
                "YIXIANG_HYPOTHESIS_ONLY:"
                f"{result.compiled_operator.transform_id}@"
                f"{result.compiled_operator.transform_version}"
            ),
        )
        proposals.append(TypedCandidateProposal(
            proposal, edge, variables, semantic_status="HYPOTHESIS_ONLY",
        ))
    return tuple(proposals)


def coordinate_yixiang_compositions(
    result: YixiangCompositionResult,
    *,
    parent_state_ref: str,
    branch_id: str,
    constraints: GlobalConstraints = GlobalConstraints(),
    coordinator: TypedCandidateCoordinator | None = None,
) -> YixiangCsgGcrResult:
    """Run bounded typed CSG-GCR over Yixiang hypotheses; never advances lifecycle."""
    proposals = compile_yixiang_typed_proposals(
        result, parent_state_ref=parent_state_ref, branch_id=branch_id,
    )
    report = (coordinator or TypedCandidateCoordinator()).coordinate(
        proposals, constraints,
    )
    return YixiangCsgGcrResult(
        proposals=proposals,
        coordination=report,
        transform_evidence_refs=tuple(sorted(set(
            result.compiled_operator.transform_evidence_refs
        ))),
    )
