# E09 Evaluator/Learner Isolation and Crash-Recovery Design

Date: 2026-11-11  
Status: design gate for the next implementation slice; not implemented by PR #149.

## 1. Trust domains

The runtime must have three distinct roles:

- **Evaluator** owns targets, labels, locked-test truth, source provenance and final scoring.
- **Learner** owns model state and receives only evidence authorized for its role.
- **Coordinator** owns episode sequencing, prediction commits, event IDs, idempotency and delivery acknowledgements. It must not infer or fabricate labels.

The current SQLite `actor_role` column is descriptive metadata. It is not authorization, identity authentication or a process boundary.

## 2. Evidence visibility

| Split | Learner | Selector | Evaluator |
|---|---:|---:|---:|
| SUPPORT | Yes | Yes | Yes |
| GATE_DEV | No | Yes | Yes |
| GATE_FINAL | No | No | Yes |
| LOCKED_TEST | No | No | Yes |

The v0.3 E09 adapter currently enforces the learner column in its trusted in-process code path. A malicious or compromised process can bypass this. The table becomes a security property only after the evaluator controls the reveal channel and the learner has no route to the evaluator's raw label store.

## 3. Process boundary

Recommended local reference topology:

```text
Evaluator process (separate OS identity)
  - private label store
  - split policy
  - source provenance
  - signed reveal envelope
             |
             | authenticated local IPC
             v
Coordinator process
  - SQLite append-only event log
  - scope/query/commit binding
  - idempotency and sequence control
             |
             | learner-scoped IPC
             v
Learner process (restricted OS identity)
  - model and candidate state only
  - SUPPORT-only reveal consumer
  - no evaluator database mount
  - no shared writable label files
```

For a meaningful local boundary, use separate OS identities, restrictive filesystem permissions, a narrow Unix-domain socket or named-pipe API, authenticated peer credentials, and a message allowlist. Merely launching two Python processes under the same user with a shared working directory is not sufficient isolation.

The learner must reject any reveal envelope whose split is not SUPPORT. The coordinator must also enforce the same rule; defense in depth is required.

## 4. Signed reveal envelope

The next protocol extension should carry:
- episode ID and monotonically increasing event sequence;
- immutable event ID and idempotency key;
- prediction ID and learner-track ID;
- CPG-EI semantic `commit_digest`;
- SQLite durable `event_digest`;
- query ID, scope and split;
- canonical outcome JSON;
- evaluator key ID and signature over the canonical envelope.

The signature authenticates the envelope origin. It does not make a false label true; truth adjudication remains an evaluator/data-governance concern. Key rotation and revocation must be explicit.

## 5. Crash recovery and delivery semantics

Do not promise distributed exactly-once execution. Use **at-least-once delivery plus idempotent application**:

1. Coordinator durably appends the reveal event.
2. Coordinator places its event ID in a learner inbox/outbox table.
3. Learner applies the event only if its ID is not already in the durable applied-event set.
4. Learner writes a new model snapshot and the applied-event cursor atomically to a durable checkpoint.
5. Coordinator records the acknowledgement.
6. On restart, the learner restores the last complete checkpoint and replays only later authorized SUPPORT events.

A model update and its applied-event cursor must be committed atomically. Otherwise a crash between model mutation and acknowledgement can duplicate a non-idempotent update.

## 6. Snapshot and input-data requirements

The current E09 adapter persists an initial structure snapshot and a new snapshot after each revision, but it does not implement restore. The event log also stores only an input digest/reference for observations, not the raw input tuple. Therefore a pending prediction cannot be reconstructed from the event log alone.

A resumable design needs:
- versioned learner snapshot schemas and tested `from_snapshot` constructors;
- snapshot digest and parent snapshot reference;
- a private, access-controlled input payload vault keyed by content digest, or an explicitly documented non-resumable policy for pending observations;
- persisted prediction inputs or a safe reference to them;
- pending prediction, reveal, revision and applied-event cursors;
- deterministic replay tests across process restart and interrupted writes.

Do not place raw locked-test labels in the learner-readable event projection. The evaluator may store a sealed payload or a private reference, while the learner-facing log contains only the authorized projection.

## 7. Acceptance tests

Before claiming process isolation or crash-safe resume:

- learner OS identity cannot read evaluator label files or database;
- GATE_DEV, GATE_FINAL and LOCKED_TEST reveal payloads cannot cross the learner IPC boundary;
- tampered signatures, wrong key IDs, stale sequence numbers and mismatched commit digests are rejected;
- duplicate delivery does not apply an update twice;
- forced termination at every write/ack boundary restores a deterministic model state;
- replayed predictions and revisions match the uninterrupted reference run;
- missing private input payloads fail closed rather than fabricating input values;
- locked-test labels never appear in learner logs, snapshots, metrics or error messages.

## 8. Current implementation boundary

PR #149 implements v0.3 query/scope/split binding, dual semantic/event digests, and a SUPPORT-only learner update path in a single trusted process. It does **not** implement OS-level isolation, signed reveal envelopes, an inbox/outbox, learner snapshot restoration, or crash-safe resume. Those remain separate acceptance gates.
