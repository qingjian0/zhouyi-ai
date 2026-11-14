# E12-A6 and ZPCM lifecycle persistence v0.1

## Purpose

Persist the authoritative E12-A6 candidate lifecycle in ZPCM without moving lifecycle authority into ZPCM or creating a second state machine.

## Ownership

- E12-A6 LifecycleLedger validates candidate/evidence registration and every lifecycle transition. It remains the only lifecycle state machine.
- ZPCM stores immutable, ordered lifecycle event records, detects event-ID/content conflicts, enforces an expected stream cursor, verifies payload digests, and replays the complete scoped event stream.
- PersistentLifecycleLedger is the transaction boundary and replay adapter. It stages a deep copy, asks E12-A6 to validate the mutation, persists the event, and only then swaps the staged ledger into memory.

ZPCM does not decide whether a transition is legal. Replay reconstructs a fresh E12-A6 ledger and re-applies every event through its existing contract.

## Event contract

Schema: e12a6-lifecycle-event-v1

Event kinds:
- candidate_registered
- evidence_registered
- action_applied
- revision_created

Each record is appended to the existing ZPCM memory_events table with event type e12a6_lifecycle. Event IDs are deterministic within the scope. Payload hashes cover the complete versioned envelope. Reusing an event ID with different content is rejected. A scoped expected-sequence cursor rejects stale writers. Replay is ordered and unbounded by semantic-memory retrieval budgets; it verifies every stored digest before returning records.

## Mutation and crash consistency

1. Deep-copy the current E12-A6 ledger.
2. Apply the proposed operation to the copy. Invalid transitions fail before persistence.
3. Append the versioned event to ZPCM in a SQLite BEGIN IMMEDIATE transaction.
4. Swap the staged ledger into the live adapter only after the append commits.

If append fails, the live in-memory ledger is unchanged. If the process terminates after the database commit but before the in-memory swap, the next adapter construction replays the durable event and validates it through E12-A6. The persistent event is the recovery point; there is no claim of distributed consensus or multi-process transactionality.

## Deliberate limits

- Single-process reference adapter using the existing SQLite ZPCM implementation.
- Does not authenticate E09 evidence or branch-merge authorization issuers.
- Does not replace E09 commit/reveal or import hidden labels into ZPCM.
- Does not use bounded semantic-memory retrieval as an event replay source.
- Does not persist arbitrary Python objects; only the explicit v1 DTO schema is accepted.
- Existing ZPCM memory and assertion events remain unchanged.

## Validation

Tests cover exact state restoration after reopen, idempotent action retry, action-ID content conflicts, invalid transition rejection before append, append failure atomicity, crash-after-append recovery, stale stream cursors, scope isolation, and digest tampering.


## Evidence payload minimization

The persistence adapter does not serialize Evidence.outcome or Evidence.provenance verbatim. These fields are replaced in the lifecycle stream with opaque evidence/provenance references derived from the evidence ID. Split role, episode, observation, model-version, timing, and identity metadata remain available to E12-A6. This prevents a lifecycle persistence event from becoming a second channel for raw LOCKED_TEST or POST_DEPLOY labels. E09 remains the authority for the underlying evidence payload.
