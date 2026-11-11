"""Explicit adapter from SROK local compositions to CSG proposals."""
from __future__ import annotations

from collections.abc import Mapping

from prototype.csg_gcr_coordinator import CandidateProposal, CoordinationError
from prototype.srok0_kernel import ComposedCandidate


def proposal_from_srok(
    candidate: ComposedCandidate,
    *,
    proposal_id: str,
    parent_state_ref: str,
    branch_id: str,
    role_variables: Mapping[str, str],
    cost: int = 1,
    requires: tuple[str, ...] = (),
    excludes: tuple[str, ...] = (),
) -> CandidateProposal:
    """Map SROK role bindings to caller-declared shared variables.

    Role names are not assumed to be globally identical variables. The caller
    must explicitly map each role to a variable name; equal variable names
    across proposals are then unified by CSG-GCR.
    """
    if not isinstance(candidate, ComposedCandidate):
        raise CoordinationError("candidate must be a ComposedCandidate")
    roles = {role for role, _ in candidate.role_bindings}
    if set(role_variables) != roles:
        raise CoordinationError("role_variables must map every SROK role exactly once")
    bindings = []
    for role, node_id in candidate.role_bindings:
        variable = role_variables[role]
        if not isinstance(variable, str) or not variable.strip():
            raise CoordinationError("variable names must be non-empty strings")
        bindings.append((variable, node_id))
    if len({key for key, _ in bindings}) != len(bindings):
        # A single candidate may bind the same variable through multiple roles
        # only when those roles resolve to the same node.
        merged = {}
        for key, value in bindings:
            if key in merged and merged[key] != value:
                raise CoordinationError("one variable resolves to conflicting SROK members")
            merged[key] = value
        bindings = list(merged.items())
    return CandidateProposal(
        proposal_id=proposal_id,
        parent_state_ref=parent_state_ref,
        branch_id=branch_id,
        bindings=tuple(sorted(bindings)),
        evidence_refs=candidate.evidence_ids,
        requires=requires,
        excludes=excludes,
        score=candidate.score,
        cost=cost,
        candidate_kind=candidate.relation_type,
    )
