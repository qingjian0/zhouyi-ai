# CSG-GCR typed hyperedge bridge v0.1

Date: 2026-11-11
Base: PR #208 head `5f886df80bd89f2bcefdaddaf6f62a33fdff3ab2`
Status: integration prototype; CI and full validation pending

## Purpose

Connect the standalone typed hyperedge unification kernel to the bounded
CSG-GCR candidate subset search without replacing either kernel or changing
E09/E12-A6/ZPCM ownership.

## Execution path

`TypedCandidateProposal` pairs one immutable legacy coordinator proposal
with one `HyperedgeProposal`, its variable declarations and explicit typed
constraints. The bridge validates identity alignment, invokes the existing
bounded CSG-GCR search, and applies typed unification to each candidate set
before it is emitted as a typed result.

## Invariants

- Proposal ID, edge ID, parent state and branch ID must match exactly.
- Typed proposals cannot mix legacy string-key bindings.
- Evidence refs must match between the proposal and typed edge; the unifier
  independently unions provenance and the bridge checks equality with the
  coordinator result.
- Variable declarations with the same namespaced ref must be identical.
- Equality, inequality, role requirements and subtype constraints are merged
  deterministically and passed to the existing typed unifier.
- Parent-state isolation, cost/cardinality limits and bounded search remain
  owned by the existing CSG-GCR coordinator.
- A raw search budget exhaustion remains `BUDGET_EXHAUSTED`, even if valid
  candidates were found before truncation.

## Important limitation

The current bounded coordinator does not prune typed-infeasible partial sets
during DFS. The bridge checks typed feasibility on completed candidate sets.
This is correct as a filter for emitted candidates but can spend search budget
on combinations that will later be rejected. A future optimization may add a
pure, monotonic partial-feasibility callback to the coordinator after proving
that the callback cannot reject a partial set that becomes valid when extended.

The bridge also does not implement semantic deduplication, branch-delta merge,
Pareto/diversity selection, E09 commits, E12-A6 lifecycle transitions, or ZPCM
persistence. Branch IDs remain lineage labels; they do not prove branch
compatibility or authorize cross-worldline transfer.

## Acceptance

Focused tests cover typed composition, type conflict, temporal conflict,
declaration conflict, legacy/typed contract separation, parent isolation,
budget propagation and provenance preservation. Full repository CI must pass
on the exact PR head before this prototype is considered integrated.
