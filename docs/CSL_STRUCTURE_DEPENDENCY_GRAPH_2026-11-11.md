# CSL Structure Dependency Graph — 2026-11-11

## Purpose
An explicit, version-addressed dependency DAG beside the E12-A6 lifecycle contract. It does not replace CandidateState, mutate E12 objects, or automatically revise dependent structures.

## Contract
- A node is an immutable structure version identified by (structure_id, version, learner_track).
- An edge points from dependent/consumer to prerequisite and carries a typed role, explicit scope, optional evidence references, and an independent impact policy.
- Local edges stay within one learner track. Cross-track reuse requires explicit SHARED scope and a prerequisite registered with shared=true. learner_track remains a namespace, not an authenticated principal.
- Self edges, dangling versions, duplicate edges, and cycles are rejected before an event is appended.
- Node status changes are append-only. Impact policy is independent of semantic role: BLOCKING queues and propagates, REVIEW queues only the direct consumer, and ADVISORY records stale dependency without queueing. The default remains BLOCKING for legacy constructor compatibility. Dependents are never silently changed.
- Revalidation acknowledgement is explicit; it is not proof that revalidation succeeded.

## Replay
The graph is rebuilt from contiguous ordered events. Replay re-runs contract checks, reconstructs the reverse index and queue, and produces a deterministic SHA-256 digest over event log and derived state. The digest is an integrity fingerprint, not an authentication signature.

## Limitations
- In-memory reference implementation; not yet persisted in SQLite v0.3.
- No automatic E12 CandidateState mapping or lifecycle mutation.
- Evidence references are opaque IDs; no evidence-store foreign-key validation.
- No cross-process concurrency, authorization, distributed consensus, or crash-resume.
- All non-ACTIVE prerequisite states conservatively trigger impact analysis; domain-specific selective invalidation remains future work.

## Selective invalidation semantics

The impact policy is deliberately orthogonal to DependencyRole: USES does not necessarily mean critical, and SUPPORTS does not necessarily mean optional. A policy change must be explicit and replayable. When a node is reached through multiple paths, a BLOCKING path continues propagation even if another path is only REVIEW. ADVISORY edges remain visible through stale-edge inspection but do not enter the revalidation queue.

This is an execution contract, not an inferred truth about causal impact. Evaluation must use synthetic DAGs with labelled impacted descendants, unaffected sibling branches, diamond/multiple-path structures, and policy perturbations. Report impact precision/recall, over-invalidation, missed impact, queue size, and revalidation cost. No policy directly mutates E12 CandidateState or creates E12 actions.

## Next experiments
1. Add typed dependency events to durable v0.3 storage without changing legacy semantics.
2. Verify dependency projection/replay parity across SQLite close/reopen.
3. Measure impact precision/recall on synthetic graphs with known affected descendants and unaffected sibling branches.
4. Connect queued items to explicit E12 request_revalidation actions only after evidence and track ownership checks.
5. Compare transitive invalidation with role-aware selective invalidation; report over-invalidation and missed-impact rates.
