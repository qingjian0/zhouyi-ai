# E12-A6 / E09 v0.3 Evaluation-Channel Separation Audit

Date: 2026-11-11  
Status: implementation contract addendum  
Base integration commit: `f982d12c555b2f2254248faa4371a7f3d1ab113c`  
Protocol v0.3 proposal: `ba24f96cddd351c62862310fe1435f3518fc4e2c`  
Scope: E12-A6 × E02-D lifecycle runner and E09 shared evidence adapter

## 1. Finding

The first v0.3 proposal correctly identified that pre-existing TRAIN support must not be fabricated as a post-prediction reveal. A deeper source audit found a second, more consequential mismatch: **Gate-Final and Locked-Test evidence are not ordinary learner feedback**.

The E12-A6 × E02-D runner currently:

- ingests TRAIN support into the in-memory lifecycle ledger without prediction/reveal steps;
- computes candidate predictions for Gate-Final queries, then creates `Evidence` records with synthetic `prediction_commit_step` and `label_visibility_step` values;
- freezes candidate acceptance before Locked-Test labels are exposed;
- records a Locked-Test counterexample as a lifecycle challenge when it contradicts an accepted candidate.

The runner does not currently persist those Gate-Final and Locked-Test prediction/reveal pairs through the shared SQLite protocol. Merely assigning integer step numbers does not create durable causal events.

The shared protocol v0.2 has only `evidence_reveal`. The E09 adapter invokes the learner's `runner.reveal(...)` after persisting that event. Reusing this event for Gate-Final or Locked-Test would conflate two different semantics:

1. feedback the learner is allowed to learn from;
2. evaluator labels used to select, score, or challenge a candidate, which must not automatically become learner-visible training data.

This is an integration contract gap, not evidence that the existing E12 runner's in-memory test is invalid.

## 2. Exact source locations

Pinned integration tree `f982d12c555b2f2254248faa4371a7f3d1ab113c` contains:

- `prototype/e12a6_e02_lifecycle_runner.py`
  - `run_episode` creates TRAIN evidence at the beginning of each episode.
  - Gate-Final evidence is created after candidate predictions, with synthetic commit/reveal step numbers.
  - Locked-Test evidence is created after the candidate decision is frozen, also with synthetic step numbers.
  - A contradictory Locked-Test result triggers `ActionType.CHALLENGE`.
- `prototype/e12a6_lifecycle_contract.py`
  - `Evidence` permits both causal step fields to be absent, which is appropriate for pre-existing TRAIN evidence.
  - `LifecycleLedger` enforces evidence-role requirements for candidate transitions.
- `prototype/shared_evidence_protocol.py`
  - `EVENT_TYPES` currently includes observation, prediction_commit, evidence_reveal, structure_version, and revision.
  - `evidence_reveal` requires a prior prediction commit on the same learner track.
  - `structure_version.support_evidence_ids` and revision triggers currently resolve only to evidence_reveal event IDs.
  - `replay_episode` returns the full episode event stream; there is no learner-safe projection API.
- `prototype/e09_shared_protocol_adapter.py`
  - `reveal` persists evidence_reveal and then calls the learner's `runner.reveal`.
  - `revise` creates a new structure version and revision record using that reveal as support.

## 3. Required semantic separation

Protocol v0.3 must distinguish three evidence channels:

| Channel | Meaning | Learner may consume as training? |
|---|---|---|
| `evidence_ingest` | Pre-existing visible TRAIN/SUPPORT material | Yes, subject to track and policy |
| `evidence_reveal` | Feedback deliberately released to the learner after its committed prediction | Yes, after release |
| `evaluation_reveal` | Evaluator-only Gate/Locked-Test label used for selection or scoring | No, not through the learner interface |

Do not overload `evidence_reveal` with a role flag and rely on every caller to remember not to train on it. Separate event types provide a stronger semantic default and make accidental learner ingestion easier to detect.

## 4. Proposed evaluation event contract

Reuse `prediction_commit` for the prediction record, with explicit metadata that the prediction belongs to an evaluation split. The commit payload must include:

```json
{
  "prediction_id": "eval-prediction-17",
  "observation_id": "eval-observation-17",
  "model_version": "candidate-set-v3",
  "learner_track": "e12",
  "decision_status": "PREDICT",
  "evaluation_role": "GATE_FINAL",
  "candidate_set_digest": "digest-of-frozen-candidate-set"
}
```

Add `evaluation_reveal` as a distinct event type. Required payload:

```json
{
  "prediction_id": "eval-prediction-17",
  "learner_track": "e12",
  "evaluation_role": "GATE_FINAL",
  "target_or_feedback": "ground-truth-result",
  "candidate_set_digest": "same-frozen-candidate-set-digest"
}
```

Allowed roles are explicitly enumerated: `GATE_DEV`, `GATE_FINAL`, `LOCKED_TEST`, and `POST_DEPLOY_AUDIT`. Unknown roles fail closed.

Rules:

1. Every evaluation reveal must reference exactly one prior prediction commit on the same episode and learner track.
2. The referenced commit must carry the same evaluation role and frozen candidate-set digest.
3. A prediction ID may receive at most one evaluation reveal.
4. `GATE_FINAL` may be used by the evaluator to accept/reject candidate sets, but its label must not enter the learner's update function.
5. `LOCKED_TEST` is released only after the candidate set and all selection decisions are frozen. It cannot influence candidate selection or hyperparameter choice.
6. A Locked-Test counterexample may produce an evaluator-authored lifecycle challenge event, but it must not be appended as learner-visible support.
7. `POST_DEPLOY_AUDIT` may trigger a policy-controlled challenge/revision workflow; whether it is later released as feedback is an explicit separate action.
8. Evaluation labels are never accepted by `evidence_ingest` and never qualify as ordinary `evidence_reveal` support.
9. Candidate-set digest must be stable across all predictions within one evaluation batch. A changed candidate set requires a new evaluation batch/commit context.
10. The protocol validates references and roles; the independent evaluator validates that labels and split assignments are truthful.

## 5. Learner-safe and evaluator projections

A raw append-only event log is not itself a learner API.

Introduce explicit projections:

- `replay_evaluator_episode(episode_id)`: returns the complete event history, including evaluation labels, and is callable only by the trusted evaluator/runtime boundary.
- `replay_learner_episode(episode_id, learner_track)`: returns only the learner's authorized projection:
  - learner-visible observations;
  - that track's prediction commits;
  - TRAIN evidence ingested for that track;
  - ordinary evidence reveals explicitly released to that track;
  - structure versions and revisions authorized for that track.
  - It must omit all `evaluation_reveal` payloads, all other tracks' private payloads, and evaluator-only provenance.

Projection filtering is defense-in-depth, not process security. If learner code can open the SQLite database directly, it can bypass the projection. For a real trust boundary:

1. keep the database handle in a trusted service/runner process;
2. give learner code only a narrow request/response interface;
3. never mount the evaluator database file into the learner process;
4. test that learner IPC payloads contain no evaluator labels, truth objects, generator state, or hidden source IDs;
5. treat actor_role strings as audit metadata, not authentication.

A future multi-process implementation may use separate learner and evaluator databases with a one-way release protocol. Do not claim this isolation until implemented and tested.

## 6. Lifecycle persistence

The E12-A6 lifecycle ledger remains the authority for domain transition legality. The shared protocol persists accepted transitions.

A persisted `lifecycle_action` must include:

- action ID and exact ActionType;
- learner track;
- candidate ID and immutable candidate version;
- from/to lifecycle state;
- evidence references with an explicit evidence kind;
- evaluator/learner actor metadata;
- the pinned E12-A6 contract version;
- digest of the validated domain action.

The protocol must reject a lifecycle action if:

- the referenced candidate version is absent;
- the action evidence is not yet available;
- the evidence role is incompatible with the action;
- the track does not match;
- the event sequence violates the required causal order;
- the action/state pair is not in the pinned E12-A6 transition table.

Do not let a generic protocol enum silently expand E12-A6's state machine. If an evaluator-only Locked-Test counterexample challenges a candidate, record that the challenge is evaluator-authored and cite the evaluation reveal, while keeping that reveal out of learner support.

## 7. Required conformance tests

### Channel separation

1. TRAIN evidence can be ingested before any prediction commit.
2. GATE_FINAL cannot be ingested through `evidence_ingest`.
3. LOCKED_TEST cannot be ingested through `evidence_ingest`.
4. An ordinary `evidence_reveal` requires a prior learner prediction commit.
5. An `evaluation_reveal` requires a prior evaluation prediction commit.
6. Evaluation role mismatch between commit and reveal is rejected.
7. Candidate-set digest mismatch is rejected.
8. Duplicate evaluation reveal is rejected.

### Leakage prevention

9. `replay_learner_episode` never returns evaluation_reveal payloads.
10. Mutating a Gate-Final label cannot change any learner-visible input before/after evaluation selection.
11. Mutating a Locked-Test label cannot change candidate generation, candidate selection, or any pre-test learner decision.
12. Locked-Test is unavailable to selection code until the candidate-set freeze marker is durable.
13. Evaluator-only source provenance never appears in learner-facing IPC messages.
14. Cross-track evaluation labels never appear in another track's learner projection.

### Lifecycle and atomicity

15. A Gate-Final failure can reject a candidate without training on the Gate-Final label.
16. A Locked-Test counterexample can challenge a candidate without becoming support evidence.
17. A lifecycle action cannot cite an evaluation reveal as TRAIN support.
18. A lifecycle action referencing an evaluation reveal must preserve its evaluation role and evaluator provenance.
19. A failed multi-event evaluation batch leaves no partial commit/reveal pair.
20. Replaying the evaluator projection is deterministic and preserves the freeze boundary.

All tests should include a truth-mutation invariant: hold all learner-visible bytes fixed, mutate evaluator-only truth, and verify that all learner decisions before authorized feedback remain byte-equivalent.

## 8. Corrected implementation order

1. Implement protocol v0.3 event schema for `evidence_ingest` and tagged evidence references.
2. Add `evaluation_reveal` and explicit evaluation roles; do not overload E09's ordinary `evidence_reveal`.
3. Add evaluator and learner projections, with projection tests.
4. Add lifecycle-action persistence over the pinned E12-A6 validator.
5. Add atomic append batches for prediction/evaluation and revision transitions.
6. Adapt E12-A6 runner to persist actual observation and prediction commits before each Gate-Final/Locked-Test reveal. Remove synthetic step-number-only causal claims from the integration path.
7. Keep Gate-Final/Locked-Test evaluator labels outside E09's `runner.reveal` and outside learner support references.
8. Add mutation-based leakage tests and run the complete integration CI.
9. Only after those pass, compare E09 incremental learning against batch refit and measure whether any post-deploy feedback policy improves future episodes.

## 9. Decision

The v0.3 protocol proposal must be amended with a separate evaluator-only evaluation channel. The semantic invariant is:

**TRAIN is ingested; learner feedback is revealed; Gate/Locked-Test is evaluated. These are three different operations.**

This separation is necessary for scientifically meaningful claims about learning, generalization, and delayed counterexample handling. It does not by itself provide cryptographic integrity, process isolation, or resistance to a malicious learner with direct storage access.
