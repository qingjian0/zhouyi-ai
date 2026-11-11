# CSL dependency projection in Shared Evidence Protocol v0.3

Implementation slice: `dependency_added@1`.

## Durable event contract

The first persisted dependency event is intentionally same-track and candidate-only. Its exact payload is:

```json
{
  "dependent_version_id": "consumer@1",
  "dependency_version_id": "primitive@1",
  "learner_track": "e12",
  "role": "uses",
  "impact_policy": "blocking",
  "evidence_refs": []
}
```

Both endpoints must be prior `structure_version` records with `kind=candidate`, and both must have an E12 lifecycle binding under the exact learner track. Evidence references must resolve to prior ingested/revealed evidence and may not cross tracks. The first implementation has implicit LOCAL scope; cross-track/SHARED edges are not accepted.

The writer validates exact payload keys, typed role and impact policy, candidate identity, track ownership, evidence references, duplicate edge identity, self-edge, and DAG acyclicity before inserting the event. Validation runs inside the existing `BEGIN IMMEDIATE` batch transaction; a rejected event consumes no sequence number.

## Projection and replay

`EpisodeProjection.dependencies` is rebuilt from ordered durable events. Each edge records its event and sequence identity, both candidate version IDs, learner track, semantic role, impact policy, and evidence references. Dependency data is included in `EpisodeProjection.to_dict()` and therefore the projection digest.

Replay repeats endpoint, track, evidence, duplicate, and cycle checks. It does not trust a cached graph or an independent graph-status event stream. Existing event digest verification protects the durable payload; close/reopen reconstructs the same dependency list and digest.

## Derived status and impact queue

E12 CandidateState remains authoritative. The projection treats `gate_validated`, `reused`, and `specialized` as dependency-eligible states (ACTIVE/PROVISIONAL view). A transition from one of these states to a non-eligible state is an invalidation trigger. No new authoritative CSL lifecycle state is persisted.

Impact policy is orthogonal to dependency role:

- `blocking`: queue an eligible direct consumer and continue through its dependents.
- `review`: queue the eligible direct consumer, but stop propagation at that consumer.
- `advisory`: retain the edge but do not queue or propagate through it.

Queue entries are derived from all recorded invalidation triggers, current per-track E12 states, and dependency edges. They are deterministic and track-local. If a candidate later returns to an eligible state, it is no longer returned as a stale queue item. The queue is a read-only worklist: it does not create `request_revalidation`, `challenge`, `revise`, or `revalidate` actions.

## Validation scope

Regression tests cover durable edge append, projection digest, SQLite close/reopen parity, unknown endpoint rejection, unbound-track rejection, cycle rejection without sequence consumption, and lifecycle-driven BLOCKING/REVIEW/ADVISORY behavior on a three-node dependency chain.

This remains a single-process SQLite reference implementation. It does not provide cross-track sharing, distributed consensus, authorization, learner crash-resume, or automatic revalidation execution.
