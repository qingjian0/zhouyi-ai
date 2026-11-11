# Shared Evidence Protocol v0.3 RFC

Date: 2026-11-11  
Status: Research RFC; proposal only, not an implementation  
Parent integration baseline: `research/csl-e12-e09-integration-smoke-2026-11-11`  
Scope: E09 shared evidence ledger + E12-A6 lifecycle contract + future CSL projection

## 1. Problem statement

Protocol v0.2 has five event types: `observation`, `prediction_commit`, `evidence_reveal`, `structure_version`, and `revision`.

Its `structure_version.support_evidence_ids` currently accepts only IDs of prior `evidence_reveal` events. That is correct for evidence whose label becomes visible after a prediction, but it cannot represent already-visible TRAIN/bootstrap support without inventing a prediction/reveal pair. Such fabricated pairs would falsify the causal history.

E12-A6 also has lifecycle transitions that are not structure revisions. Recording every transition as a `structure_version` would conflate candidate state with candidate definition/version. Finally, a semantic revision is compound: old candidate state changes, a child version is created, and a revision record binds before/after versions to challenge evidence. Separate appends can leave a partial durable history.

## 2. Non-goals and invariants

This RFC does not create a second lifecycle state machine, distributed event broker, authenticated actor identity, evaluator/learner process isolation, or a claim of crash-resumable learning.

Normative invariants:

1. Event history is append-only. Existing v0.1/v0.2 rows, payload bytes, and digests are never rewritten.
2. Evidence provenance and visibility time are explicit. A visible TRAIN record is not represented as a delayed reveal.
3. A lifecycle action is not itself a structure version.
4. A revision's complete durable representation is atomic.
5. Every reference resolves to an earlier event in the same episode unless a schema explicitly defines a pre-episode immutable external reference.
6. A failed append batch leaves no event, idempotency row, sequence allocation, or projection mutation behind.
7. Unknown required event types or unsupported payload schema versions fail closed.
8. `learner_track` remains a namespace/data field, not an authenticated principal.

## 3. Versioning

- `PROTOCOL_VERSION = "0.3"` for newly appended events after implementation.
- Preserve the event row's existing `protocol_version`, `payload_schema`, and `payload_digest` semantics.
- New payload schemas: `evidence_ingest@1`, `lifecycle_action@1`.
- Existing schemas remain readable without migration: v0.1 implicit learner-track upcast remains a read-time projection only; v0.2 events retain their original bytes and digest.
- A store must advertise supported protocol and payload-schema versions before an adapter starts. A writer must not silently downgrade an event whose semantics are unavailable in the target store.

## 4. Event: evidence_ingest

Purpose: register evidence that is already visible to the learner at ingestion time, principally TRAIN support and explicitly declared pre-episode bootstrap evidence.

Required payload:

```json
{
  "evidence_id": "stable-evidence-id",
  "observation_ref": "observation-event-id-or-null",
  "split_role": "TRAIN",
  "outcome_ref": "immutable-outcome-or-payload-reference",
  "source_provenance": {
    "source_kind": "dataset|bootstrap|measurement",
    "source_id": "stable-source-id"
  },
  "learner_track": "e12",
  "visibility": {
    "kind": "ingest_time",
    "sequence_no": 12
  }
}
```

Rules:

- `evidence_id` is unique within an episode and is distinct from `event_id`.
- `split_role` is restricted initially to `TRAIN` or `BOOTSTRAP`. The latter is legal only when the episode declaration explicitly enables pre-episode bootstrap evidence.
- `GATE_FINAL`, `LOCKED_TEST`, and `POST_DEPLOY` are forbidden for ingest. Their labels must enter through the existing prediction-commit/evidence-reveal causal path.
- If `observation_ref` is non-null, it must resolve to an earlier observation event.
- `visibility.sequence_no` is assigned by the store, not trusted from caller input. The schema example is illustrative; the persisted envelope must bind visibility to the actual append sequence.
- `outcome_ref` is an immutable reference or canonical payload digest, not an implicit permission to expose evaluator-held labels.
- `learner_track` must be non-empty. Track scoping is enforced on evidence use where applicable.

### Evidence reference semantics

`structure_version.support_evidence_ids` may refer to:
- an earlier `evidence_ingest.evidence_id` whose role is permitted by the consuming structure policy; or
- an earlier `evidence_reveal.event_id` (legacy v0.2 behavior).

`revision.trigger_evidence_ids` remains restricted to `evidence_reveal.event_id` with role `LOCKED_TEST` or `POST_DEPLOY`. TRAIN evidence may support a candidate but cannot be relabeled as a post-deployment challenge.

Do not overload one string namespace: validators must resolve the ID against event type and reject ambiguous collisions. Prefer typed references in future payloads, e.g. `{ "kind": "ingested", "id": "..." }` and `{ "kind": "revealed", "id": "..." }`; retain the legacy string form only for v0.2 compatibility.

## 5. Event: lifecycle_action

Purpose: persist E12-A6 lifecycle decisions without creating fake structure versions.

Required payload:

```json
{
  "action_id": "episode/track/candidate/action",
  "action_type": "PROPOSE",
  "candidate_id": "primitive-17",
  "candidate_version": 1,
  "from_state": null,
  "to_state": "PROPOSED",
  "evidence_refs": [],
  "cost": 0.25,
  "note": "candidate generated by proposer family A",
  "candidate_lineage_refs": []
}
```

Initial `action_type` vocabulary must be mapped exactly from E12-A6's `ActionType` enum at implementation time. Do not invent aliases or silently normalize unknown values. Payload records the actual E12 state names (e.g. `OBSERVED`, `PROPOSED`, `DISCRIMINATION_PENDING`, `TRAIN_SUPPORTED`, `GATE_VALIDATED`, `REUSED`, `CHALLENGED`, `REVISED`, `SPECIALIZED`, `RETIRED`, `REVALIDATION_PENDING`) rather than CSL presentation labels such as `ACTIVE` or `SUSPENDED`.

Rules:

- State transition legality is delegated to the existing E12-A6 transition validator. The protocol validator checks envelope integrity, event ordering, references, and role compatibility; it must not fork E12 transition logic.
- `evidence_refs` must resolve to earlier evidence events and preserve typed provenance.
- An action's `candidate_version` and lineage references must resolve to the matching structure-version identity where one exists.
- `action_id` is unique within `episode_id + learner_track`; duplicate action IDs with identical content are idempotent, conflicting content is rejected.
- Lifecycle events are append-only audit facts. A current-state projection is derived by replay, not stored as an independently authoritative mutable state.

## 6. Atomic append_events API

Proposed API:

```python
append_events(
    *,
    episode_id: str,
    events: Sequence[EventSpec],
    idempotency_key: str,
    expected_sequence: int | None = None,
) -> tuple[EventReceipt, ...]
```

Each `EventSpec` contains `event_id`, `event_type`, `payload`, `actor_role`, `causation_refs`, `payload_schema`, and `integrity_metadata`. The batch-level idempotency key is scoped to the episode. A deterministic per-event fingerprint is computed from the complete event envelope, including type, schema, payload, actor role, causation refs, and integrity metadata.

Transaction algorithm:

1. Validate batch shape and reject duplicate event IDs, duplicate idempotency keys, unsupported types/schemas, and malformed payloads before opening the write transaction.
2. Acquire the store lock and execute `BEGIN IMMEDIATE`.
3. Resolve batch idempotency. An exact whole-batch retry returns the original ordered receipts with `replayed=True`; a changed batch under the same key raises `IdempotencyConflict`. Never partially replay a batch.
4. Check `expected_sequence` against the durable episode tail.
5. Build a validation overlay containing durable prior events plus earlier events in this batch. Validate all forward references, uniqueness constraints, evidence roles, track compatibility, and E12 lifecycle transitions against this overlay.
6. Assign contiguous sequence numbers in input order and insert all event rows plus all idempotency rows.
7. Commit once. On any exception, rollback the entire transaction and return no receipt.
8. Only after commit, update in-memory projections. If projection application fails, mark the adapter unhealthy and reconstruct from the durable log before accepting more work.

Single-event `append_event` remains source-compatible and delegates to `append_events` with a one-event batch. This prevents two transaction implementations from drifting.

### Batch event ordering for an E12 semantic revision

A compound revision batch must be validated and persisted as one unit. Proposed logical order:

1. New `structure_version` event with parent version references resolving to already durable versions.
2. `lifecycle_action` event(s) recording the old candidate's transition to `REVISED` and the new version's transition to `REVALIDATION_PENDING`.
3. `revision` event binding before/after version IDs and LOCKED_TEST/POST_DEPLOY trigger evidence.

The implementation must verify that the exact E12-A6 `create_revision` semantics and action ordering match the real contract. If the current contract requires a different order, adapt the batch order without weakening atomicity. A batch cannot refer forward to an event that appears later in the same batch unless a narrowly specified two-phase reference rule is introduced; the initial implementation should reject such forward references.

## 7. Replay and projection

Replay consumes the ordered immutable event stream and rebuilds:
- evidence identity, provenance, split role, and visibility;
- structure versions and parent lineage;
- E12 candidate state transitions using the shared E12 validator/reducer;
- revisions and before/after version links;
- per-track projections and deterministic projection digests.

Replay must not:
- infer missing labels;
- convert TRAIN ingest into a reveal;
- treat a prediction as a reveal;
- infer `ACTIVE`/ `SUSPENDED` lifecycle states that E12 does not own;
- mutate historical events to make them fit the current schema.

A projection digest should be computed from canonical sorted projection data, excluding volatile runtime values. Reopening the same database and replaying the same episode must yield the same digest. Replay determinism is not equivalent to full crash-resumable learning: learner optimizer/state restoration, external data availability, and adapter recovery need separate contracts and tests.

## 8. E12 adapter boundary

The E12 adapter should:
1. call the existing E12-A6 action validator before proposing a lifecycle event;
2. serialize the validated action and candidate/version lineage;
3. append the complete event batch atomically;
4. apply the committed action to the in-memory ledger only after durable commit;
5. fail closed and rebuild from durable events if projection application fails.

Do not introduce a CSL-owned parallel state machine. CSL may expose derived views, but the canonical transition semantics remain E12-A6 until a separately reviewed migration explicitly changes ownership.

## 9. Required tests

### Compatibility
- v0.1 replay upcast remains read-only and digest-preserving.
- v0.2 observation/commit/reveal/structure/revision fixtures replay unchanged.
- Existing E09 adapter behavior and event ordering remain unchanged.
- Existing `append_event` call sites continue to pass.

### Evidence semantics
- TRAIN ingest can support a structure version without a fake prediction/reveal.
- BOOTSTRAP ingest is rejected unless explicitly declared by episode metadata.
- LOCKED_TEST/GATE_FINAL/POST_DEPLOY ingest is rejected.
- A revision cannot cite TRAIN ingest as trigger evidence.
- Structure support can cite prior ingest or prior reveal with correct typed resolution.
- Unknown, ambiguous, cross-episode, forward, and wrong-track evidence references are rejected.

### Atomicity and idempotency
- Valid multi-event batch receives contiguous sequence numbers.
- Failure on the final event rolls back every prior event and idempotency row.
- Exact retry returns original receipts without duplicate events.
- Same batch key with altered order, payload, actor, schema, or causation refs conflicts.
- Duplicate event/action IDs and duplicate evidence IDs are rejected.
- Stale expected sequence rejects the whole batch.
- Independent SQLite connections serialize concurrent batches without interleaving.

### Lifecycle and replay
- E12-A6 legal and illegal transitions are tested against the original contract.
- Revision batch preserves old/new candidate lineage and exact before/after references.
- Crash/reopen replay produces a deterministic projection digest.
- Projection failure after commit causes fail-closed recovery from the durable log.
- Replay of legacy v0.1/v0.2 fixtures does not fabricate v0.3 lifecycle events.

## 10. Acceptance gates

Do not claim protocol v0.3 complete until all of the following hold:

- Existing full test suite passes unchanged.
- New focused tests cover every required test family above.
- E09 and E12 adapter integration tests pass on one checkout.
- Fault injection proves whole-batch rollback and exact retry behavior.
- Replay digest matches before/after reopen for seeded episodes.
- A compatibility report documents v0.1/v0.2 read behavior and v0.3 write behavior.
- CI is green on a Draft PR based on the E12+E09 integration smoke commit.

Until then, the accurate status is: **v0.3 proposed; v0.2 remains the only implemented protocol version**.


## 11. Contract alignment correction (2026-11-11)

A direct inspection of `prototype/e12a6_lifecycle_contract.py` found that its enum wire values are **lower-case**, not the upper-case display names used in some earlier prose above. The implementation must serialize the exact values below:

- `SplitRole`: `support`, `train`, `gate_dev`, `gate_final`, `locked_test`, `post_deploy`.
- `CandidateState`: `observed`, `proposed`, `discrimination_pending`, `train_supported`, `gate_validated`, `reused`, `challenged`, `revised`, `specialized`, `retired`, `revalidation_pending`.
- `ActionType`: `propose`, `request_discrimination`, `train_support`, `gate_validate`, `reuse`, `challenge`, `revise`, `specialize`, `retire`, `request_revalidation`, `register_revision`, `revalidate`, `measure`, `compose`, `predict`, `abstain`.

There is no `BOOTSTRAP` member in the current `SplitRole` enum. Bootstrap status must therefore be represented as provenance/episode metadata while retaining a valid existing split role (normally `train` or `support`), or be introduced through a separately versioned E12 contract change. Do not silently extend the enum in the protocol adapter.

The exact E12 revision order is also now pinned by source inspection:
1. Apply `revise` to the challenged parent, moving it to `revised`.
2. Create the child candidate in `observed` with parent lineage.
3. Apply `register_revision` to the child, moving it to `revalidation_pending`.

A v0.3 revision batch must persist the corresponding parent lifecycle action, child structure-version event, child lifecycle action, and revision record in one SQLite transaction. The RFC's earlier illustrative order is superseded by this section.
