# CSG-GCR Branch Delta v0.1

Date: 2026-11-11
Status: deterministic integration prototype; validation pending.

## Contract

A branch is an immutable reference to one parent state plus an append-only
sequence of typed edits. It does not clone the parent workspace:

`W_i = W_parent + Delta_i`

Each event carries a stable event ID, operation, target, expected before-hash,
new value, evidence references, causal predecessor, and monotonically
increasing branch-local version. Snapshots declare exact read/write sets,
parent reference, canonical hash of the exact parent state, base version,
evidence union, and lineage. Merge rejects a state whose canonical digest does
not match the declared parent hash.

## Merge policy

- Parent state reference and base version must match exactly.
- Identical event replay (same event ID and same content) is idempotent.
- Reusing an event ID with different content is a conflict.
- Same-target writes are conflicts; no last-writer-wins or score-based choice.
- Write/read dependency overlap is a conflict.
- Expected before-hash mismatch is STALE.
- Missing/duplicate evidence or inconsistent read/write declarations are rejected.
- Disjoint, valid edits are applied in deterministic version/event-ID order.

## Ownership boundaries

This prototype validates structural mergeability only. It does not decide
semantic equivalence, branch compatibility, cross-worldline transfer,
evidence truth, candidate lifecycle, or persistence. E09 remains evidence
authority, E12-A6 remains lifecycle authority, and ZPCM remains the durable
event-history authority. Branch IDs are lineage labels, not authorization.

## Validation

Focused tests cover disjoint edits, parent/version isolation, write/write
conflict, write/read conflict, stale hashes, idempotent replay, event-ID
collision, invalid write-set declarations, and add-existing conflicts.
Full CI on the exact PR head is required before promotion.
