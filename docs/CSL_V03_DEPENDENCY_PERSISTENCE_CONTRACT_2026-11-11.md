# CSL dependency persistence contract for v0.3

## Decision

The first durable adapter must derive dependency-node status from the existing E12-A6 CandidateState. It must not introduce a second authoritative lifecycle state machine.

The v0.3 store already persists immutable `structure_version` records, while learner-track ownership is established in `lifecycle_action` records. A candidate version is globally represented by `version_id = candidate_id@version`, but its E12 lifecycle projection is isolated per `learner_track`. Therefore the dependency-node identity must remain the composite:

`(version_id, learner_track)`

Never collapse the track dimension or infer it from a candidate ID.

## Derived status view

The dependency adapter should expose a read-only CSL status view derived from E12 state:

| E12 CandidateState | CSL dependency view | Impact treatment |
|---|---|---|
| observed, proposed, discrimination_pending, train_supported | PROPOSED | not an active dependent |
| gate_validated, reused | ACTIVE | eligible for revalidation queue |
| challenged | CHALLENGED | not queued as active; stale edge remains |
| revised | REVISED | not queued as active; stale edge remains |
| specialized | PROVISIONAL | eligible for revalidation queue |
| retired | RETIRED | excluded from queue |
| revalidation_pending | SUSPENDED | excluded from active queue |

This is a projection mapping only. E12 CandidateState and its transition table remain the sole authority. A future mapping revision must be versioned and tested against the actual E12 contract.

## First event slice

Add one typed event type: `dependency_added`, payload schema `dependency_added@1`.

Required payload fields:
- `dependent_version_id`
- `dependency_version_id`
- `learner_track`
- `role`
- `impact_policy`
- `evidence_refs` (array; may be empty)

Initial scope is intentionally same-track only. Both version IDs must resolve to prior `structure_version` records of kind `candidate`, and both must already be present in that learner track's E12 projection. Cross-track/shared dependencies are deferred until explicit share authorization and ownership semantics exist; the in-memory graph's SHARED flag is not sufficient authorization.

Each evidence reference must resolve through the existing typed evidence resolver and belong to the same learner track. No free-form or dangling evidence IDs.

## Validation and replay

- Extend the v0.3 event allowlist and payload schema checks for the new event.
- Validate required fields, enums, uniqueness, and exact version/track references before insert.
- Validate DAG acyclicity before append; a rejected edge must not consume an event sequence.
- Replay dependency events in sequence order after the prerequisite candidate/track bindings exist.
- Derive node status from replayed E12 CandidateState; do not persist independent graph status transitions.
- Derive stale edges and the revalidation queue deterministically from dependency edges, current E12 states, and the explicit edge impact policy.
- Include dependency projection data in `EpisodeProjection.to_dict()` and its digest.
- SQLite close/reopen must reproduce the same dependency edges, status view, queue, and digest.
- Tampering with a dependency event payload or its track/version reference must fail replay.
- Keep the existing post-commit `ProjectionRecoveryRequired` contract; do not report rollback after durable commit.

## E12 action boundary

A dependency impact queue is a derived worklist, not an E12 lifecycle action. The adapter must not automatically issue `request_revalidation`, `challenge`, `revise`, or `revalidate`.

A later explicit orchestration layer may propose an E12 action, but it must satisfy the existing evidence split-role, candidate-track, transition-table, and lifecycle ownership checks. Acknowledging that a queue item was noticed must not be treated as proof of successful revalidation.

## Test matrix

1. Add edge between prior same-track candidate versions.
2. Reject unknown version ID, wrong candidate kind, unclaimed learner track, cross-track edge, and cross-track evidence.
3. Reject duplicate edge and cycle without consuming sequence.
4. Replay legacy episodes without dependency events unchanged.
5. Reopen SQLite and compare projection digest and queue.
6. Tamper with role, policy, version ID, track, and evidence ref; replay must fail.
7. Lifecycle transitions update derived dependency status and impact queue without adding a second status event stream.
8. BLOCKING, REVIEW, and ADVISORY policies remain independent of DependencyRole.
9. Multi-track same candidate version produces isolated dependency nodes and queues.
10. Projection failure after commit surfaces receipts and is recoverable by replay.

## Explicit non-goals

No distributed coordination, authentication, cross-track sharing, crash-resume of the learner, automatic E12 action execution, or evidence-label access beyond existing v0.3 rules.