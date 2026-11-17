# CSG-GCR Monotonic Partial Feasibility v0.1

Date: 2026-11-11
Status: research integration prototype; exact-head CI pending.

## Problem

The typed bridge currently generates bounded candidate sets first and invokes
typed unification after each set is emitted. This is correct as a final filter,
but it can spend search budget expanding prefixes that are already impossible.

## Safe pruning contract

A partial-feasibility predicate may prune a prefix only when its rejection is
monotonic: every superset of that prefix is also infeasible. The generic
coordinator exposes an optional callback and reports how many prefixes it
pruned. Callback results must be actual booleans. The callback contract is
explicitly the caller's responsibility; arbitrary non-monotonic predicates
must not be used.

The typed bridge enables only checks with this property:

- conflicting declarations for the same variable reference;
- one already-declared variable resolving to multiple member IDs;
- equality classes that already contain incompatible member identities;
- an already-active inequality whose endpoints are equal or resolve to the same member;
- empty intersection of already-declared temporal intervals;
- subtype hierarchy cycles;
- duplicate role names within one immutable hyperedge.

It deliberately does **not** prune:

- a member type that currently does not satisfy a variable type, because a
  later proposal may add a subtype edge;
- a missing required role, because a later hyperedge may provide it;
- an unbound required variable, because a later proposal may bind it;
- an unresolved variable relation whose endpoint has not yet been declared.

These omissions are intentional to avoid false negatives.

## Validation

- Coordinator tests compare complete candidate results with and without a
  monotonic callback and verify reduced expanded-state counts.
- Typed tests exhaustively enumerate subsets of a small proposal set and assert
  that no pruned subset becomes feasible after adding proposals.
- Differential tests compare pruned and unpruned typed results under a
  sufficiently large search budget.
- Exact-head CI is required before promotion.

## Boundaries

Partial pruning does not decide evidence truth, candidate ranking semantics,
candidate lifecycle, persistence, or cross-worldline authorization. It is a
search optimization only. E09, E12-A6 and ZPCM retain their ownership.
