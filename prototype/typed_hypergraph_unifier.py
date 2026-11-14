"""Typed, provenance-preserving hyperedge variable unification.

A dependency-free reference implementation for CSG-GCR. It validates typed
role bindings and unifies explicitly shared variables without owning evidence
truth, candidate lifecycle, or persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class UnificationError(ValueError):
    """Invalid schema or an unsatisfied hard unification constraint."""


@dataclass(frozen=True, order=True)
class VariableRef:
    namespace: str
    name: str


@dataclass(frozen=True)
class VariableSpec:
    ref: VariableRef
    value_type: str
    required: bool = True


@dataclass(frozen=True)
class RoleBinding:
    role: str
    variable: VariableRef
    member_id: str
    member_type: str


@dataclass(frozen=True)
class HyperedgeProposal:
    edge_id: str
    parent_state_ref: str
    branch_id: str
    relation_type: str
    roles: tuple[RoleBinding, ...]
    evidence_refs: tuple[str, ...] = ()
    active_from: int | None = None
    active_until: int | None = None


@dataclass(frozen=True)
class RoleRequirement:
    relation_type: str
    role: str
    required: bool = True
    allowed_member_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class VariableRelation:
    left: VariableRef
    right: VariableRef


@dataclass(frozen=True)
class UnificationConstraints:
    equal: tuple[VariableRelation, ...] = ()
    not_equal: tuple[VariableRelation, ...] = ()
    role_requirements: tuple[RoleRequirement, ...] = ()
    # Each pair is (child_type, parent_type); compatibility is transitive.
    subtype_of: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class UnifiedVariable:
    refs: tuple[VariableRef, ...]
    value_type: str
    member_id: str
    member_type: str


@dataclass(frozen=True)
class UnificationResult:
    parent_state_ref: str
    edge_ids: tuple[str, ...]
    branch_ids: tuple[str, ...]
    variables: tuple[UnifiedVariable, ...]
    evidence_refs: tuple[str, ...]
    active_from: int | None
    active_until: int | None
    trace: tuple[str, ...]


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise UnificationError(f"{field} must be a non-empty string")


def _unique_text(values: Iterable[str], field: str) -> None:
    rows = tuple(values)
    for value in rows:
        _text(value, field)
    if len(rows) != len(set(rows)):
        raise UnificationError(f"{field} must not contain duplicates")


def _type_is_a(actual: str, expected: str, parents: dict[str, set[str]]) -> bool:
    if actual == expected:
        return True
    seen = set()
    pending = list(parents.get(actual, ()))
    while pending:
        current = pending.pop()
        if current == expected:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(parents.get(current, ()))
    return False


def unify_hyperedges(
    edges: Iterable[HyperedgeProposal],
    variables: Iterable[VariableSpec],
    constraints: UnificationConstraints = UnificationConstraints(),
) -> UnificationResult:
    """Unify a compatible set of typed hyperedges under explicit hard rules.

    Equalities merge variable identities; all bound members in an equality
    class must identify the same member. Inequalities prohibit those classes
    from resolving to the same member. Evidence references are unioned, never
    replaced by semantic identity or score.
    """
    edge_rows = tuple(edges)
    variable_rows = tuple(variables)
    if not edge_rows:
        raise UnificationError("at least one hyperedge is required")
    if not isinstance(constraints, UnificationConstraints):
        raise UnificationError("constraints must be UnificationConstraints")

    parent_refs = {edge.parent_state_ref for edge in edge_rows}
    if len(parent_refs) != 1:
        raise UnificationError("hyperedges from different parent states cannot unify")
    parent_state_ref = next(iter(parent_refs))
    _text(parent_state_ref, "parent_state_ref")

    edge_ids = [edge.edge_id for edge in edge_rows]
    _unique_text(edge_ids, "edge_id")
    variable_by_ref: dict[VariableRef, VariableSpec] = {}
    for spec in variable_rows:
        if not isinstance(spec, VariableSpec) or not isinstance(spec.ref, VariableRef):
            raise UnificationError("variables must be VariableSpec values")
        _text(spec.ref.namespace, "variable namespace")
        _text(spec.ref.name, "variable name")
        _text(spec.value_type, "variable value_type")
        if spec.ref in variable_by_ref:
            raise UnificationError(f"duplicate variable declaration: {spec.ref}")
        variable_by_ref[spec.ref] = spec

    parents: dict[str, set[str]] = {}
    for child, ancestor in constraints.subtype_of:
        _text(child, "subtype child")
        _text(ancestor, "subtype parent")
        if child == ancestor:
            raise UnificationError("a type cannot be its own parent")
        parents.setdefault(child, set()).add(ancestor)

    # Reject cyclic type declarations instead of making compatibility
    # dependent on traversal order.
    for child in parents:
        for ancestor in parents[child]:
            if _type_is_a(ancestor, child, parents):
                raise UnificationError("subtype hierarchy contains a cycle")

    requirements = {}
    for requirement in constraints.role_requirements:
        if not isinstance(requirement, RoleRequirement):
            raise UnificationError("role_requirements must contain RoleRequirement")
        _text(requirement.relation_type, "required relation_type")
        _text(requirement.role, "required role")
        _unique_text(requirement.allowed_member_types, "allowed_member_types")
        key = (requirement.relation_type, requirement.role)
        if key in requirements:
            raise UnificationError(f"duplicate role requirement: {key}")
        requirements[key] = requirement

    bindings: dict[VariableRef, list[tuple[str, str, str, str]]] = {
        ref: [] for ref in variable_by_ref
    }
    trace = []
    for edge in edge_rows:
        for field in ("edge_id", "parent_state_ref", "branch_id", "relation_type"):
            _text(getattr(edge, field), field)
        if edge.active_from is not None and (
            isinstance(edge.active_from, bool) or not isinstance(edge.active_from, int)
        ):
            raise UnificationError("active_from must be an integer or None")
        if edge.active_until is not None and (
            isinstance(edge.active_until, bool) or not isinstance(edge.active_until, int)
        ):
            raise UnificationError("active_until must be an integer or None")
        if (edge.active_from is not None and edge.active_until is not None
                and edge.active_from >= edge.active_until):
            raise UnificationError("hyperedge active interval must be non-empty")
        _unique_text(edge.evidence_refs, "evidence_refs")
        role_names = []
        for binding in edge.roles:
            if not isinstance(binding, RoleBinding):
                raise UnificationError("edge roles must contain RoleBinding")
            _text(binding.role, "role")
            _text(binding.member_id, "member_id")
            _text(binding.member_type, "member_type")
            if binding.variable not in variable_by_ref:
                raise UnificationError(f"undeclared variable: {binding.variable}")
            role_names.append(binding.role)
            spec = variable_by_ref[binding.variable]
            if not _type_is_a(binding.member_type, spec.value_type, parents):
                raise UnificationError(
                    f"member type {binding.member_type} is not compatible with "
                    f"{spec.value_type} for {binding.variable}"
                )
            req = requirements.get((edge.relation_type, binding.role))
            if req and req.allowed_member_types and not any(
                _type_is_a(binding.member_type, allowed, parents)
                for allowed in req.allowed_member_types
            ):
                raise UnificationError(
                    f"member type {binding.member_type} violates role "
                    f"{edge.relation_type}.{binding.role}"
                )
            bindings[binding.variable].append((
                binding.member_id, binding.member_type, edge.edge_id, binding.role
            ))
        _unique_text(role_names, f"roles in {edge.edge_id}")
        for (relation, role), req in requirements.items():
            if relation == edge.relation_type and req.required and role not in role_names:
                raise UnificationError(
                    f"required role {relation}.{role} missing from {edge.edge_id}"
                )
        trace.append(f"EDGE_ACCEPTED:{edge.edge_id}:{edge.relation_type}")

    # Deterministic union-find over declared variable references.
    roots = {ref: ref for ref in variable_by_ref}

    def find(ref: VariableRef) -> VariableRef:
        while roots[ref] != ref:
            roots[ref] = roots[roots[ref]]
            ref = roots[ref]
        return ref

    def union(left: VariableRef, right: VariableRef) -> None:
        if left not in roots or right not in roots:
            raise UnificationError("equality references an undeclared variable")
        a, b = find(left), find(right)
        if a == b:
            return
        # A declared value type must be comparable in the subtype lattice.
        ta, tb = variable_by_ref[a].value_type, variable_by_ref[b].value_type
        if not (_type_is_a(ta, tb, parents) or _type_is_a(tb, ta, parents)):
            raise UnificationError(f"incompatible variable types: {ta} and {tb}")
        low, high = sorted((a, b))
        roots[high] = low
        trace.append(f"VARIABLES_EQUAL:{a.namespace}.{a.name}:{b.namespace}.{b.name}")

    for relation in constraints.equal:
        union(relation.left, relation.right)

    groups: dict[VariableRef, list[VariableRef]] = {}
    for ref in variable_by_ref:
        groups.setdefault(find(ref), []).append(ref)

    for relation in constraints.not_equal:
        if relation.left not in roots or relation.right not in roots:
            raise UnificationError("inequality references an undeclared variable")
        if find(relation.left) == find(relation.right):
            raise UnificationError("a variable cannot be both equal and not_equal")

    unified = []
    resolved_member: dict[VariableRef, str] = {}
    for root, refs in sorted(groups.items()):
        rows = [row for ref in refs for row in bindings[ref]]
        required = any(variable_by_ref[ref].required for ref in refs)
        if required and not rows:
            raise UnificationError(
                "required variable is unbound: " + ",".join(
                    f"{ref.namespace}.{ref.name}" for ref in sorted(refs)
                )
            )
        member_ids = {row[0] for row in rows}
        if len(member_ids) > 1:
            raise UnificationError(
                "equal variables resolve to different members: "
                + ",".join(sorted(member_ids))
            )
        if not rows:
            continue
        member_id = next(iter(member_ids))
        member_types = {row[1] for row in rows}
        compatible_types = [
            candidate for candidate in member_types
            if all(_type_is_a(candidate, expected, parents)
                   for expected in member_types)
        ]
        if not compatible_types:
            raise UnificationError("equal variable bindings have incompatible member types")
        canonical_type = sorted(compatible_types)[0]
        refs_sorted = tuple(sorted(refs))
        for ref in refs:
            resolved_member[ref] = member_id
        declared_types = [variable_by_ref[ref].value_type for ref in refs]
        value_type = sorted(
            (candidate for candidate in set(declared_types)
             if all(_type_is_a(candidate, other, parents) for other in declared_types)),
            key=lambda value: (len(value), value),
        )
        if not value_type:
            raise UnificationError("unified variable declarations have no common type")
        unified.append(UnifiedVariable(
            refs=refs_sorted, value_type=value_type[0],
            member_id=member_id, member_type=canonical_type,
        ))
        trace.append(
            f"VARIABLE_RESOLVED:{','.join(ref.namespace + '.' + ref.name for ref in refs_sorted)}={member_id}"
        )

    for relation in constraints.not_equal:
        left, right = resolved_member.get(relation.left), resolved_member.get(relation.right)
        if left is not None and right is not None and left == right:
            raise UnificationError("not_equal variables resolve to the same member")
        trace.append(
            f"VARIABLES_NOT_EQUAL:{relation.left.namespace}.{relation.left.name}:"
            f"{relation.right.namespace}.{relation.right.name}"
        )

    starts = [edge.active_from for edge in edge_rows if edge.active_from is not None]
    ends = [edge.active_until for edge in edge_rows if edge.active_until is not None]
    active_from = max(starts) if starts else None
    active_until = min(ends) if ends else None
    if active_from is not None and active_until is not None and active_from >= active_until:
        raise UnificationError("hyperedge temporal scopes do not intersect")

    return UnificationResult(
        parent_state_ref=parent_state_ref,
        edge_ids=tuple(sorted(edge_ids)),
        branch_ids=tuple(sorted({edge.branch_id for edge in edge_rows})),
        variables=tuple(sorted(unified, key=lambda item: item.refs)),
        evidence_refs=tuple(sorted({
            ref for edge in edge_rows for ref in edge.evidence_refs
        })),
        active_from=active_from,
        active_until=active_until,
        trace=tuple(trace),
    )
