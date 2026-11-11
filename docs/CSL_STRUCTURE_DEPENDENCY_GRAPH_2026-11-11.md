# CSL Structure Dependency Graph — 2026-11-11

## Purpose
An explicit, version-addressed dependency DAG beside the E12-A6 lifecycle contract. It does not replace CandidateState, mutate E12 objects, or automatically revise dependent structures.

## Contract
- A node is an immutable structure version identified by (structure_id, version, learner_track).
- An edge points from dependent/consumer to prerequisite and carries a typed role, explicit scope, and optional evidence references.
- Local edges stay within one learner track. Cross-track reuse requires explicit SHARED scope and a prerequisite registered with shared=true. learner_track remains a namespace, not an authenticated principal.
- Self edges, dangling versions, duplicate edges, and cycles are rejected before an event is appended.
- Node status changes are append-only. A non-active prerequisite queues direct and transitive active/provisional dependents for revalidation. Dependents are not silently changed.
- Revalidation acknowledgement is explicit; it is not proof that revalidation succeeded.

## Replay
The graph is rebuilt from contiguous ordered events. Replay re-runs contract checks, reconstructs the reverse index and queue, and produces a deterministic SHA-256 digest over event log and derived state. The digest is an integrity fingerprint, not an authentication signature.

## Limitations
- In-memory reference implementation; not yet persisted in SQLite v0.3.
- No automatic E12 CandidateState mapping or lifecycle mutation.
- Evidence references are opaque IDs; no evidence-store foreign-key validation.
- No cross-process concurrency, authorization, distributed consensus, or crash-resume.
- All non-ACTIVE prerequisite states conservatively trigger impact analysis; domain-specific selective invalidation remains future work.

## Next experiments
1. Add typed dependency events to durable v0.3 storage without changing legacy semantics.
2. Verify dependency projection/replay parity across SQLite close/reopen.
3. Measure impact precision/recall on synthetic graphs with known affected descendants and unaffected sibling branches.
4. Connect queued items to explicit E12 request_revalidation actions only after evidence and track ownership checks.
5. Compare transitive invalidation with role-aware selective invalidation; report over-invalidation and missed-impact rates.
