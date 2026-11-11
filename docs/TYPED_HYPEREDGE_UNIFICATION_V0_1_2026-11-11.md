# Typed hyperedge unification v0.1

Date: 2026-11-11  
Status: dependency-free reference implementation  
Parent integration: PR #208 (CSG-GCR bounded coordinator)

## Purpose

This slice adds a typed unification kernel for a set of immutable hyperedge
proposals. It is intentionally separate from the current string-key binding
coordinator: typed unification must prove its own schema and conflict semantics
before it is adapted into the coordinator's candidate search.

## Contract

- `VariableRef(namespace, name)`: explicit identity scope. Identical names in
  different namespaces are not implicitly unified.
- `VariableSpec(ref, value_type, required)`: declared variable type and
  whether an unbound variable invalidates the proposal set.
- `RoleBinding(role, variable, member_id, member_type)`: one hyperedge role
  bound to one typed member.
- `RoleRequirement`: required/optional relation role and optional allowed
  member types.
- `VariableRelation`: explicit equality or inequality between variable refs.
- `subtype_of`: caller-supplied child-to-parent type edges. Compatibility is
  transitive; cycles are rejected.

## Hard invariants

1. All hyperedges must share one parent state reference.
2. Every used variable must be declared.
3. A member type must be assignable to its variable's declared value type.
4. Required relation roles must be present; constrained role types must match.
5. Explicit equality merges variable identities and requires one member ID.
6. Explicit inequality prohibits the resolved variables from sharing a member.
7. Required variables cannot remain unbound.
8. Hyperedge temporal intervals must have a non-empty common intersection.
9. Evidence references are unioned and retained independently of member or
   semantic identity; no evidence-independence claim is inferred.

## Output and explainability

The immutable result carries edge IDs, branch IDs, unified variable classes,
resolved member/type pairs, the common temporal interval, all evidence refs,
and a deterministic trace of accepted edges and variable constraints.

## Deliberate non-goals

This is not yet a dynamic hypergraph store, a learned type ontology, a global
search algorithm, a branch-delta merge engine, or an E09/E12-A6 adapter. It
does not write evidence, decide truth, deduplicate evidence, or own candidate
lifecycle. The current CSG-GCR coordinator is not yet wired to call this kernel;
the next gate is a typed proposal adapter plus differential tests against the
legacy key/value path.

## Validation

The focused suite exercises cross-edge variable reuse, explicit equality and
inequality, role completeness, subtype transitivity, parent isolation,
temporal intersection, provenance preservation, and invalid type cycles.
