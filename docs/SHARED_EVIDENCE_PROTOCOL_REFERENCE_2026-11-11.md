# Shared Evidence Protocol Reference v0.1

Status: experimental reference implementation on an isolated research branch. It is not yet integrated into E09/E10, not a production event store, and not a security boundary.

## Purpose

Turn the temporal and lineage invariants in PR #53 into executable conformance tests without forcing E09, E10, and E11 to share their hypothesis representations.

## Implementation choice

Use Python's standard-library SQLite as the first durable local store:

- `BEGIN IMMEDIATE` serializes local writers and makes sequence allocation plus event append transactional.
- `journal_mode=WAL` and `synchronous=FULL` establish a local durability baseline.
- An idempotency table binds an episode-scoped key to the event fingerprint and original receipt.
- The fingerprint covers event type, payload schema, canonical payload, actor role, causation references, and integrity metadata. Same key/same envelope returns the original receipt; same key/different envelope raises `IdempotencyConflict`.
- A prediction commit requires a prior observation event. Unique partial indexes enforce one observation ID, one prediction per observation, one prediction ID, one reveal per prediction, and one structure-version ID within an episode.
- Structure versions require existing parent versions and already revealed support evidence.
- Revision events require already revealed trigger evidence and known before/after structure versions.
- Replay returns the append order; reopening the database reconstructs the same event sequence and digests.

## Event envelope

The persisted row contains:

- `protocol_version`, `episode_id`, `sequence_no`, `event_id`, `event_type`
- `actor_role`, `causation_refs`, `payload_schema`
- canonical `payload_json`, `payload_digest`, `integrity_metadata`, `created_at`

The payload digest is a mutation-detection fingerprint, **not** a signature, authenticated provenance, or proof of source identity. The timestamp is audit metadata, not the ordering authority; `sequence_no` is the episode-local order.

## Minimal usage

```python
from prototype.shared_evidence_protocol import SQLiteEvidenceStore

store = SQLiteEvidenceStore("research-events.sqlite3")
store.append_event(
    episode_id="episode-1",
    event_id="observation-event-1",
    event_type="observation",
    idempotency_key="observation-request-1",
    payload={"observation_id": "observation-1", "payload_ref": "visible-observation"},
)
receipt = store.commit_prediction(
    episode_id="episode-1",
    event_id="prediction-event-1",
    idempotency_key="prediction-request-1",
    payload={
        "prediction_id": "prediction-1",
        "observation_id": "observation-1",
        "model_version": "model-v0",
        "decision_status": "PREDICT",
        "prediction": "candidate-A",
    },
)
# The commit method returns only after its SQLite transaction commits.
reveal = store.reveal_evidence(
    episode_id="episode-1",
    event_id="reveal-event-1",
    idempotency_key="reveal-request-1",
    payload={"prediction_id": "prediction-1", "target_or_feedback": "target-A"},
)
events = store.replay_episode("episode-1")
store.close()
```

## Conformance coverage

The unit tests cover:

1. prediction commit requires a prior observation; reveal cannot precede a committed prediction;
2. identical retry returns the original receipt;
3. conflicting retry is rejected;
4. idempotency fingerprint includes event type/schema;
5. idempotency fingerprint includes actor role;
6. one prediction per observation;
7. prediction IDs are unique within an episode;
8. stale expected sequence rejection;
9. one reveal per prediction;
10. revision evidence must already be revealed;
11. structure parent must already exist;
12. restart/replay preserves sequence, event IDs, and digests;
13. returned structure snapshots are detached data.

Run:

```bash
python -m unittest tests.test_shared_evidence_protocol -v
```

## Explicit limitations

- Single-process reference API. SQLite coordinates local database writers, but this wrapper's thread lock and connection model are not a multi-host protocol.
- No evaluator/learner process separation. Hidden labels and source provenance must remain in an external evaluator service/process; do not put them into learner-facing payloads.
- No source authentication, signing, authorization, or key management.
- No schema upcaster/migration registry yet; `payload_schema` is recorded for forward compatibility but old schemas are not transformed.
- No hash chain or external tamper-evident anchoring.
- No event compaction, snapshot checkpointing, retention/deletion policy, or privacy model.
- No measured latency/memory telemetry. Caller-provided cost fields are not accepted as measured facts by this store.
- No E09/E10 adapter and no learner implementation.

## Next acceptance gate

1. Add process-isolated evaluator/learner canary harness.
2. Add schema registry and deterministic upcaster tests.
3. Add concurrent-writer and crash-injection tests on supported platforms.
4. Run the same conformance suite against E09 and E10 adapters.
5. Compare replay/refit/incremental arms under equal measured compute.

Do not call the protocol integrated or production-ready until those gates pass.
