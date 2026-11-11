# E12-A6 → CPG-EI v1 lifecycle adapter

Date: 2026-11-11  
Status: draft adapter slice stacked on E12-A20 interop.

## Ownership

E12-A6 remains the sole owner of candidate lifecycle state and transitions. The adapter does not mirror its state machine, mutate its ledger, or define a second lifecycle enum.

## Projection

The adapter maps one immutable E12-A6 `Candidate` version into:
- `CandidateProposal`: immutable candidate reference, explicit caller-supplied scope and grammar version, semantic definition digest, evidence references, proposal cost and complexity;
- `StructureVersion`: candidate identity/version, parent lineage, and evidence lineage.

The semantic digest covers the canonical expression, ordered input types, operator and conditions. It deliberately excludes mutable lifecycle state, uncertainty, proposal cost and supporting-family metadata so that changing lifecycle bookkeeping does not silently redefine the candidate's semantics.

## Explicit boundaries

- Scope and grammar version are required adapter inputs because E12-A6's native candidate object does not own these cross-track fields.
- Evidence and parent references are canonicalized; duplicate references are rejected rather than silently hidden.
- Candidate state remains in the E12-A6 ledger. The projection is read-only.
- This adapter does not convert E12-A6 evidence into E09 durable reveal events; that requires a verified join to a committed prediction and the shared protocol's episode/event IDs.

## Validation

Focused tests cover projection, explicit scope/grammar, duplicate reference rejection, semantic digest changes, and lifecycle-state non-mutation. The original E12-A6 lifecycle tests are retained unchanged.
