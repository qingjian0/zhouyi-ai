"""Typed hyperedge bridge into the bounded CSG-GCR candidate search.

This adapter composes the existing typed unification kernel with the existing
bounded coordinator. It does not own evidence truth, candidate lifecycle, or
persistence. Typed feasibility is checked before a candidate set is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from prototype.csg_gcr_coordinator import (
    CandidateCoordinator,
    CandidateProposal,
    CoordinatedCandidate,
    CoordinationError,
    CoordinationReport,
    GlobalConstraints,
)
from prototype.typed_hypergraph_unifier import (
    HyperedgeProposal,
    UnificationConstraints,
    UnificationError,
    UnificationResult,
    VariableSpec,
    unify_hyperedges,
)


@dataclass(frozen=True)
class TypedCandidateProposal:
    proposal: CandidateProposal
    hyperedge: HyperedgeProposal
    variables: tuple[VariableSpec, ...]
    constraints: UnificationConstraints = UnificationConstraints()


@dataclass(frozen=True)
class TypedCoordinatedCandidate:
    coordinated: CoordinatedCandidate
    unification: UnificationResult


@dataclass(frozen=True)
class TypedCoordinationReport:
    candidates: tuple[TypedCoordinatedCandidate, ...]
    input_count: int
    expanded_states: int
    rejected_conflicts: int
    rejected_typed_sets: int
    status: str


def _validate_pair(item: TypedCandidateProposal) -> None:
    if not isinstance(item, TypedCandidateProposal):
        raise CoordinationError("all typed proposals must be TypedCandidateProposal")
    p, edge = item.proposal, item.hyperedge
    if not isinstance(p, CandidateProposal) or not isinstance(edge, HyperedgeProposal):
        raise CoordinationError("typed proposal requires CandidateProposal and HyperedgeProposal")
    if p.proposal_id != edge.edge_id:
        raise CoordinationError("proposal_id must equal hyperedge edge_id")
    if p.parent_state_ref != edge.parent_state_ref:
        raise CoordinationError("proposal and hyperedge parent state must match")
    if p.branch_id != edge.branch_id:
        raise CoordinationError("proposal and hyperedge branch ID must match")
    if p.bindings:
        raise CoordinationError("typed proposals cannot mix legacy string bindings")
    if tuple(p.evidence_refs) != tuple(edge.evidence_refs):
        raise CoordinationError("proposal and hyperedge evidence refs must match exactly")
    if not isinstance(item.variables, tuple) or any(
        not isinstance(value, VariableSpec) for value in item.variables
    ):
        raise CoordinationError("variables must be a tuple of VariableSpec")
    if not isinstance(item.constraints, UnificationConstraints):
        raise CoordinationError("constraints must be UnificationConstraints")


def _merge_contract(rows: tuple[TypedCandidateProposal, ...]):
    variables: dict[object, VariableSpec] = {}
    equal, not_equal, role_requirements, subtype_of = [], [], [], []
    for row in rows:
        for spec in row.variables:
            previous = variables.get(spec.ref)
            if previous is not None and previous != spec:
                raise UnificationError(f"conflicting variable declaration: {spec.ref}")
            variables[spec.ref] = spec
        c = row.constraints
        equal.extend(c.equal)
        not_equal.extend(c.not_equal)
        role_requirements.extend(c.role_requirements)
        subtype_of.extend(c.subtype_of)
    return (
        tuple(variables[key] for key in sorted(variables)),
        UnificationConstraints(
            equal=tuple(dict.fromkeys(equal)),
            not_equal=tuple(dict.fromkeys(not_equal)),
            role_requirements=tuple(dict.fromkeys(role_requirements)),
            subtype_of=tuple(dict.fromkeys(subtype_of)),
        ),
    )


class TypedCandidateCoordinator:
    """Apply typed hyperedge constraints inside bounded CSG-GCR search.

    The legacy coordinator enumerates candidate subsets under its explicit
    search/cost/cardinality budgets. This bridge requests at most max_states
    raw result sets, then rejects typed-infeasible sets and ranks only valid
    survivors. A truncated raw search remains BUDGET_EXHAUSTED even if some
    valid candidates were found.
    """

    def __init__(self, coordinator: CandidateCoordinator | None = None) -> None:
        self._coordinator = coordinator or CandidateCoordinator()

    def coordinate(
        self,
        proposals: Iterable[TypedCandidateProposal],
        constraints: GlobalConstraints = GlobalConstraints(),
    ) -> TypedCoordinationReport:
        if not isinstance(constraints, GlobalConstraints):
            raise CoordinationError("constraints must be GlobalConstraints")
        rows = tuple(proposals)
        for row in rows:
            _validate_pair(row)
        ids = [row.proposal.proposal_id for row in rows]
        if len(ids) != len(set(ids)):
            raise CoordinationError("typed proposal IDs must be unique")

        by_id = {row.proposal.proposal_id: row for row in rows}
        # Every typed candidate is represented by exactly one immutable edge.
        raw = self._coordinator.coordinate(
            (row.proposal for row in rows),
            replace(constraints, result_limit=constraints.max_states),
        )
        accepted = []
        rejected_typed = 0
        for candidate in raw.candidates:
            selected = tuple(by_id[proposal_id] for proposal_id in candidate.proposal_ids)
            try:
                variables, merged_constraints = _merge_contract(selected)
                result = unify_hyperedges(
                    (row.hyperedge for row in selected),
                    variables,
                    merged_constraints,
                )
            except UnificationError:
                rejected_typed += 1
                continue
            # The unifier is the authority for typed evidence provenance.
            if result.evidence_refs != candidate.evidence_refs:
                raise CoordinationError("typed and coordinator evidence provenance diverged")
            accepted.append(TypedCoordinatedCandidate(candidate, result))

        accepted.sort(key=lambda item: (
            -item.coordinated.score,
            item.coordinated.cost,
            len(item.coordinated.proposal_ids),
            item.coordinated.proposal_ids,
        ))
        return TypedCoordinationReport(
            candidates=tuple(accepted[:constraints.result_limit]),
            input_count=raw.input_count,
            expanded_states=raw.expanded_states,
            rejected_conflicts=raw.rejected_conflicts,
            rejected_typed_sets=rejected_typed,
            status=(
                "BUDGET_EXHAUSTED" if raw.status == "BUDGET_EXHAUSTED"
                else "COMPLETE" if accepted
                else "NO_FEASIBLE_SET"
            ),
        )
