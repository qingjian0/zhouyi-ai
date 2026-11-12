"""Typed hyperedge bridge into the bounded CSG-GCR candidate search.

This adapter composes the existing typed unification kernel with the existing
bounded coordinator. It does not own evidence truth, candidate lifecycle, or
persistence. Typed feasibility is checked before a candidate set is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from prototype.csg_branch_delta import (
    BranchMergeAuthorization,
    BranchSnapshot,
    MergeResult,
    MergeStatus,
    canonical_hash,
    merge_branch_deltas,
    validate_merge_authorization,
    validate_snapshot,
)

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
    VariableRef,
    VariableSpec,
    unify_hyperedges,
)


@dataclass(frozen=True)
class TypedCandidateProposal:
    proposal: CandidateProposal
    hyperedge: HyperedgeProposal
    variables: tuple[VariableSpec, ...]
    constraints: UnificationConstraints = UnificationConstraints()
    semantic_status: str = "CANDIDATE"


@dataclass(frozen=True)
class TypedCoordinatedCandidate:
    coordinated: CoordinatedCandidate
    unification: UnificationResult
    branch_merge: MergeResult | None = None
    branch_merge_authorization_ref: str | None = None
    branch_merge_authorization_evidence_refs: tuple[str, ...] = ()
    branch_merge_evidence_refs: tuple[str, ...] = ()
    semantic_status: str = "CANDIDATE"


@dataclass(frozen=True)
class TypedCoordinationReport:
    candidates: tuple[TypedCoordinatedCandidate, ...]
    input_count: int
    expanded_states: int
    rejected_conflicts: int
    rejected_typed_sets: int
    status: str
    pruned_partial_sets: int = 0
    rejected_branch_merges: int = 0


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
    if item.semantic_status not in ("CANDIDATE", "HYPOTHESIS_ONLY"):
        raise CoordinationError("semantic_status must be CANDIDATE or HYPOTHESIS_ONLY")


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


def _partial_typed_feasible(rows: tuple[TypedCandidateProposal, ...]) -> bool:
    """Return False only for typed contradictions that no extension can repair.

    Deliberately does not prune unresolved role requirements or type mismatches:
    a later proposal may supply a missing role or add a subtype edge. It does
    prune immutable variable declaration conflicts, member identity conflicts,
    empty temporal intersections, subtype cycles, and already-resolved
    equality/inequality contradictions.
    """
    try:
        variables, constraints = _merge_contract(rows)
        starts = []
        ends = []
        member_ids: dict[VariableRef, set[str]] = {}
        for row in rows:
            edge = row.hyperedge
            if (edge.active_from is not None and edge.active_until is not None
                    and edge.active_from >= edge.active_until):
                return False
            if edge.active_from is not None:
                starts.append(edge.active_from)
            if edge.active_until is not None:
                ends.append(edge.active_until)
            roles = [binding.role for binding in edge.roles]
            if len(roles) != len(set(roles)):
                return False
            for binding in edge.roles:
                member_ids.setdefault(binding.variable, set()).add(binding.member_id)
        if any(len(values) > 1 for values in member_ids.values()):
            return False
        if starts and ends and max(starts) >= min(ends):
            return False

        # A cycle in the currently declared subtype graph cannot be removed
        # by extending that graph.
        parents: dict[str, set[str]] = {}
        for child, parent in constraints.subtype_of:
            parents.setdefault(child, set()).add(parent)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return False
            if node in visited:
                return True
            visiting.add(node)
            for parent in parents.get(node, ()):
                if not visit(parent):
                    return False
            visiting.remove(node)
            visited.add(node)
            return True

        if any(not visit(node) for node in tuple(parents)):
            return False

        # Only evaluate equality/inequality relations whose endpoints are
        # already declared. Missing endpoints may be declared by a future row.
        roots = {ref: ref for ref in (spec.ref for spec in variables)}

        def find(ref: VariableRef) -> VariableRef:
            while roots[ref] != ref:
                roots[ref] = roots[roots[ref]]
                ref = roots[ref]
            return ref

        for relation in constraints.equal:
            if relation.left in roots and relation.right in roots:
                left, right = find(relation.left), find(relation.right)
                if left != right:
                    low, high = sorted((left, right))
                    roots[high] = low
        members_by_root: dict[VariableRef, set[str]] = {}
        for ref, values in member_ids.items():
            members_by_root.setdefault(find(ref), set()).update(values)
        if any(len(values) > 1 for values in members_by_root.values()):
            return False

        for relation in constraints.not_equal:
            if relation.left in roots and relation.right in roots:
                left_root, right_root = find(relation.left), find(relation.right)
                if left_root == right_root:
                    return False
                if members_by_root.get(left_root, set()).intersection(
                        members_by_root.get(right_root, set())):
                    return False
        return True
    except (AttributeError, UnificationError, TypeError, ValueError):
        return False


class TypedCandidateCoordinator:
    """Apply typed hyperedge constraints inside bounded CSG-GCR search.

    The coordinator prunes only monotonic contradictions in typed prefixes.
    The final unifier remains the authority for complete-set feasibility.
    A truncated raw search remains BUDGET_EXHAUSTED even if valid candidates
    were found. Set enable_partial_pruning=False for differential-oracle tests.
    """

    def __init__(self, coordinator: CandidateCoordinator | None = None, *,
                 enable_partial_pruning: bool = True) -> None:
        if not isinstance(enable_partial_pruning, bool):
            raise CoordinationError("enable_partial_pruning must be bool")
        self._coordinator = coordinator or CandidateCoordinator()
        self._enable_partial_pruning = enable_partial_pruning

    def coordinate(
        self,
        proposals: Iterable[TypedCandidateProposal],
        constraints: GlobalConstraints = GlobalConstraints(),
        *,
        base_state: Mapping[str, object] | None = None,
        branch_snapshots: Iterable[BranchSnapshot] = (),
        branch_merge_authorization: BranchMergeAuthorization | None = None,
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
        snapshots = tuple(branch_snapshots)
        snapshot_by_branch: dict[str, BranchSnapshot] = {}
        if snapshots:
            if base_state is None or not isinstance(base_state, Mapping):
                raise CoordinationError("branch snapshots require an explicit base_state mapping")
            if any(not isinstance(key, str) or not key.strip() for key in base_state):
                raise CoordinationError("base_state keys must be non-empty strings")
            try:
                base_digest = canonical_hash(base_state)
            except ValueError as exc:
                raise CoordinationError("base_state must be finite JSON-compatible data") from exc
            for snapshot in snapshots:
                if not isinstance(snapshot, BranchSnapshot):
                    raise CoordinationError("branch_snapshots must contain BranchSnapshot")
                if snapshot.branch_id in snapshot_by_branch:
                    raise CoordinationError("branch snapshot IDs must be unique")
                try:
                    validate_snapshot(snapshot)
                except ValueError as exc:
                    raise CoordinationError(f"invalid branch snapshot: {exc}") from exc
                snapshot_by_branch[snapshot.branch_id] = snapshot
            proposal_branches = {row.proposal.branch_id for row in rows}
            if set(snapshot_by_branch) != proposal_branches:
                raise CoordinationError("provide exactly one branch snapshot for every proposal branch")
            for row in rows:
                snapshot = snapshot_by_branch[row.proposal.branch_id]
                if snapshot.parent_state_ref != row.proposal.parent_state_ref:
                    raise CoordinationError("branch snapshot parent does not match its proposal")
                if snapshot.parent_state_hash != base_digest:
                    raise CoordinationError("branch snapshot digest does not match supplied base_state")
            if len(snapshot_by_branch) > 1:
                if branch_merge_authorization is None:
                    raise CoordinationError("cross-branch composition requires an E09 authorization receipt")
                parent_refs = {row.proposal.parent_state_ref for row in rows}
                if len(parent_refs) != 1:
                    raise CoordinationError("cross-branch composition requires one shared parent state")
                try:
                    validate_merge_authorization(
                        branch_merge_authorization,
                        next(iter(parent_refs)),
                        tuple(sorted(snapshot_by_branch)),
                    )
                except ValueError as exc:
                    raise CoordinationError(str(exc)) from exc
        elif base_state is not None or branch_merge_authorization is not None:
            raise CoordinationError("base_state and merge authorization require branch_snapshots")

        def selected_branch_snapshots(selected_proposals: tuple[CandidateProposal, ...]):
            return tuple(snapshot_by_branch[branch_id] for branch_id in sorted({
                proposal.branch_id for proposal in selected_proposals
            }))

        # Every typed candidate is represented by exactly one immutable edge.
        def partial_feasibility(selected_proposals: tuple[CandidateProposal, ...]) -> bool:
            selected_rows = tuple(by_id[item.proposal_id] for item in selected_proposals)
            if not _partial_typed_feasible(selected_rows):
                return False
            if snapshots:
                merge = merge_branch_deltas(base_state, selected_branch_snapshots(selected_proposals))
                if merge.status not in (MergeStatus.MERGED, MergeStatus.NO_OP):
                    return False
            return True

        raw = self._coordinator.coordinate(
            (row.proposal for row in rows),
            replace(constraints, result_limit=constraints.max_states),
            partial_feasibility=partial_feasibility if (
                self._enable_partial_pruning and (snapshots or rows)
            ) else None,
        )
        accepted = []
        rejected_typed = 0
        rejected_branch_merges = 0
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
            branch_merge = None
            authorization_ref = None
            authorization_evidence_refs: tuple[str, ...] = ()
            branch_evidence_refs: tuple[str, ...] = ()
            if snapshots:
                branch_merge = merge_branch_deltas(
                    base_state, selected_branch_snapshots(tuple(row.proposal for row in selected))
                )
                if branch_merge.status not in (MergeStatus.MERGED, MergeStatus.NO_OP):
                    rejected_branch_merges += 1
                    continue
                selected_snapshots = selected_branch_snapshots(
                    tuple(row.proposal for row in selected)
                )
                branch_evidence_refs = tuple(sorted({
                    ref for snapshot in selected_snapshots for ref in snapshot.evidence_refs
                }))
                if len({row.proposal.branch_id for row in selected}) > 1:
                    authorization_ref = branch_merge_authorization.authorization_ref
                    authorization_evidence_refs = branch_merge_authorization.evidence_refs
            semantic_status = (
                "HYPOTHESIS_ONLY"
                if any(row.semantic_status == "HYPOTHESIS_ONLY" for row in selected)
                else "CANDIDATE"
            )
            accepted.append(TypedCoordinatedCandidate(
                candidate, result, branch_merge, authorization_ref,
                authorization_evidence_refs, branch_evidence_refs, semantic_status,
            ))

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
            pruned_partial_sets=raw.pruned_partial_sets,
            rejected_branch_merges=rejected_branch_merges,
        )
