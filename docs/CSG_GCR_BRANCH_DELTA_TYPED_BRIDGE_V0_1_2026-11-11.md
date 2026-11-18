# Typed CSG-GCR Branch Delta Bridge v0.1

Date: 2026-11-11
Status: integration prototype; exact-head CI pending.

## Purpose

Connect the typed candidate coordinator to the Branch Delta kernel so a
candidate composed from branch proposals can carry a deterministic,
validated resulting state without cloning the parent workspace.

The caller supplies:
- the exact base state mapping;
- one BranchSnapshot per proposal branch;
- an explicit BranchMergeAuthorization when more than one branch is composed.

Each snapshot must name the same parent state as its proposal and carry the
canonical SHA-256 digest of the supplied base state. The adapter validates
snapshot shape, branch identity, parent identity and digest before search.

## Authorization boundary

Cross-branch composition requires a BranchMergeAuthorization value containing
an authorization reference, parent-state scope, allowed branch IDs, and
evidence references. The adapter checks that the receipt scope covers the
selected branches. It does **not** authenticate the issuer or decide evidence
truth: the value must originate from an E09-validated authorization path.
A branch ID alone never authorizes transfer.

## Search and merge behavior

- Typed monotonic feasibility remains an early search filter.
- Branch delta merge validation is also applied to partial branch selections;
  irreversible write/write, read/write, stale-parent, and event conflicts
  prune that prefix.
- Complete candidate sets are revalidated by the Branch Delta kernel.
- Accepted typed candidates carry the MergeResult and authorization reference.
- Conflicts are rejected; there is no last-writer-wins behavior.
- Candidate lifecycle and durable event persistence remain outside this
  adapter: E12-A6 and ZPCM retain their ownership.

## Tests

Focused tests cover:
- authorized disjoint branch edits producing one merged candidate state;
- missing cross-branch authorization rejection;
- same-target cross-branch write conflict pruning;
- parent digest mismatch rejection;
- existing typed-unification and monotonic-pruning oracle tests.

## Limitations

This is a deterministic structural bridge, not an E09 implementation. The
authorization object is a scoped receipt contract, not cryptographic proof of
issuer authenticity. E09 must supply and validate it in the full runtime.
