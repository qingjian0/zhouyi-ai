# E09 Shared Evidence Protocol v0.3 integration

Date: 2026-11-11  
Status: implementation slice; pending exact-head CI.

## Compatibility

The SQLite store continues to write v0.2 by default. Callers must explicitly request `protocol_version="0.3"` for the strict cross-track contract. Existing v0.1/v0.2 event rows remain replayable and are not silently upgraded or assigned fabricated scope/split metadata.

## v0.3 causal binding

For a strict prediction cycle:

1. `observation` carries `observation_id`, `query_id`, `scope` and `split`.
2. `prediction_commit` repeats the same query/scope/split tuple and must reference a prior v0.3 observation with an exact match.
3. The committed event receipt exposes the immutable event-envelope digest. Protocol version is included in the idempotency fingerprint, so a v0.2 retry cannot silently replay as v0.3.
4. The prediction event carries `interop_commit_digest`, computed from the canonical CPG-EI `PredictionCommit` DTO.
5. `evidence_reveal` repeats query/scope/split and learner track, carries `commit_digest` equal to the CPG-EI semantic digest, and carries `event_digest` equal to the SQLite event-envelope digest.
6. The store validates both digests independently. A reveal cannot bind to a legacy event, another scope, another split, another query, a different semantic prediction or a different durable event.

Allowed split labels are `SUPPORT`, `GATE_DEV`, `GATE_FINAL` and `LOCKED_TEST`. Labels are metadata and validation inputs, not an authentication boundary.

## E09 adapter behavior

The E09 adapter now requires an explicit scope and records query/scope/split on observations and commits. It maps each E09 prediction to the shared CPG-EI `PredictionCommit` DTO and each reveal to `EvidenceReveal`, validates the DTO binding, and persists both the semantic commit digest and the independent SQLite event-envelope digest.

Only `SUPPORT` reveals are passed to the E09 learner's update path. Gate and locked-test reveals are persisted but not delivered to the learner, and therefore cannot trigger an E09 revision through this adapter. This is a code-path safeguard inside one trusted process, not process isolation.

## Remaining security and recovery work

- Evaluator/learner process separation and authenticated evidence transport remain unimplemented.
- The runner still cannot reconstruct its in-memory state from the SQLite event log after restart.
- The adapter still requires a fresh episode; live resume is not claimed.
- Scope and split values are supplied by the trusted caller; source identity is not cryptographically authenticated.
- Durable reveal append followed by learner update still has a cross-system crash window. A transactional outbox or deterministic state reconstruction is required before claiming crash-safe exactly-once learning.

## Tests

New tests cover strict commit/reveal binding, wrong digest rejection, mismatched split rejection, legacy-to-v0.3 binding rejection, and withholding locked-test labels from the learner. The existing v0.2 tests remain unchanged to protect backward compatibility.


## E09 incremental learner conflict correction

CI exposed a semantic inconsistency in the incremental conjunction learner: a directly contested input could still receive a prediction from a broader clean pattern. The learner now abstains when the queried input itself has contradictory labels, even if broader patterns would otherwise produce one label. The bootstrap-conflict test was updated to assert the same quarantine rule. This is a conservative identifiability policy, not a performance optimization.


## Additional CI-found defects corrected

- The E09 evidence-ledger adjudication summary treated a set of contested keys as a mapping and failed when producing the summary. It now reads labels from the canonical label index.
- The incremental learner's full-recompute oracle now includes the explicit directly-contested-query abstention rule, so the test compares equivalent semantics rather than the older, weaker rule.


## Context binding correction and evaluator-side scoring

The shared `PredictionCommit` and `EvidenceReveal` DTOs now carry optional `episode_id`, `learner_track`, and split context (plus the prediction's model version). Existing constructors remain source-compatible, while the E09 v0.3 adapter populates these fields. The generic reveal validator now rejects cross-episode, cross-track, and cross-split bindings when context is present. The SQLite protocol independently enforces the same context against durable events.

A separate `E09EvaluatorProjection` now computes split-aware coverage and selective accuracy directly from the durable event projection. It has no learner mutation API. In particular, LOCKED_TEST labels can be scored by the evaluator projection while the learner's own prequential score remains unchanged. This remains a same-process reference projection; it is not yet an OS/process security boundary.

The CPG-EI inference status vocabulary also distinguishes `ABSTAINED` from `UNKNOWN`: a deliberate refusal to commit a hypothesis is not the same as a state for which the engine has no result.
