# Trusted Evidence Broker Contract v0.1 (2026-11-11)

Status: research contract only. This is not an implemented security boundary.

## 1. Purpose

The v0.3 event store now has evaluator-only events, learner projections and policy-gated, label-free challenge releases. These controls improve protocol correctness, but do not isolate processes: the SQLite file still contains evaluator labels, and Python role strings are caller-controlled data.

The next boundary is a trusted Evidence Broker. It is the sole owner of the SQLite connection and event-log filesystem permissions. Learner, evaluator and policy-authority processes communicate through separate authenticated capabilities and narrow typed operations. No client receives a database path, connection, cursor, raw event API or evaluator projection unless it holds the evaluator capability.

## 2. Threat model

Protected assets:
- raw Gate-Final, Locked-Test and Post-deploy labels and evaluator provenance;
- candidate-set freezes, prediction commits and evaluation attestations;
- policy authorization material and release budgets;
- event-log integrity, ordering, idempotency and replay state.

Threats:
- compromised learner attempts to read labels, query arbitrary event types, forge actor roles, enumerate other tracks, or submit arbitrary lifecycle/revision events;
- extra JSON keys such as target, label, expected answer or source evaluation ID smuggled into otherwise valid requests;
- compromised evaluator releases challenges outside policy or exceeds budgets;
- replay, idempotency-key collision, concurrent writes and crash after commit/before response;
- accidental evaluator metadata or hidden sequence gaps in learner responses.

Out of scope: a compromised host kernel/root administrator, Byzantine multi-host consensus, proof that labels are scientifically correct, and confidentiality from the trusted evaluator itself.

## 3. Process topology

    Learner process -- learner capability --------+
                                                   |
    Evaluator process -- evaluator capability ----+--> Trusted Evidence Broker
                                                   |      - owns SQLite handle
    Policy authority -- policy capability --------+      - validates schemas
                                                          - enforces budgets
                                                          - serializes writes
                                                          - builds projections
                                                                 |
                                                   private DB + WAL; service-only

The broker is the only process with filesystem access to the database, WAL and backup files. Learner/evaluator clients must not share its OS account, mount the database volume, inherit file descriptors, or receive backup paths.

Preferred local deployment: Unix-domain socket with OS peer credentials and restrictive permissions. Remote deployment, if later needed, uses mutually authenticated TLS and short-lived scoped credentials. Authentication is performed by the broker; fields such as actor_role, learner_track and policy_authority are not credentials.

## 4. Capability model

Capabilities are broker-issued and bound to principal, permitted operations, learner track (where applicable), episode scope, expiry and credential/key identifier.

| Capability | Permitted operations | Forbidden |
|---|---|---|
| Learner | read learner snapshot; receive/acknowledge minimal challenge; submit typed prediction commit; ingest permitted TRAIN/SUPPORT | raw event query; evaluator projection; evaluation reveal; arbitrary append; policy changes |
| Evaluator | read frozen evaluation inputs; append matching evaluation reveal; read evaluator audit projection | directly modify learner support; alter frozen candidates; mint learner credentials |
| Policy authority | register immutable release policy; authorize minimal challenge release | rewrite learner state; change labels |
| Broker operator | lifecycle, backup and key rotation under audit | silently rewrite event history |

Track identity comes from the authenticated capability, not a client-selected request field. Cross-track access is denied by default. Shared scope requires a separate capability and explicit audit event.

## 5. Public operation contract

All requests use versioned strict schemas; unknown keys are rejected recursively. Mutations include request ID and idempotency key. The broker binds each key to authenticated principal, operation and canonical request digest.

Learner API:
- get_snapshot(episode_id, opaque_cursor?) -> LearnerSnapshot
- get_pending_challenges(episode_id) -> ChallengeSignal[]
- acknowledge_challenge(challenge_id, request_id) -> AckReceipt
- commit_prediction(PredictionCommit) -> CommitReceipt
- ingest_support(VisibleSupportEvidence) -> IngestReceipt

LearnerSnapshot is a freshly serialized allowlist DTO. It contains only learner-visible observations, predictions, TRAIN/SUPPORT and explicitly authorized feedback, learner-visible candidate definitions/lifecycle state, an opaque cursor and minimal challenge signals. It excludes raw event envelopes, evaluator IDs, hidden split roles, evaluator provenance, hidden labels, policy internals, global sequence gaps attributable to hidden events and evaluator-only causal references.

A challenge requests reconsideration or new evidence; it is not a label or training target. Receiving or acknowledging one cannot itself update model parameters or candidate support.

Evaluator API:
- get_evaluation_input(freeze_id) -> FrozenEvaluationInput
- record_evaluation(EvaluationResult) -> EvaluationReceipt
- get_evaluator_audit(episode_id, cursor?) -> EvaluatorAuditPage

The broker validates that freeze and prediction commit pre-exist and match episode, track, role and candidate digest. Evaluation payloads never route through learner feedback methods.

Policy API:
- register_release_policy(PolicyDefinition, signed_authorization) -> PolicyReceipt
- release_challenge(ReleaseDecision, signed_authorization) -> ChallengeReceipt

The broker validates signer/principal, role and challenge-kind allowlists, episode/track binding, source evaluation and prediction causality, unique challenge ID, one release per source evaluation by default, and a cumulative budget that cannot be reset by creating a new policy version.

## 6. Data-flow invariants

1. Authenticate and authorize capability before resolving protected references.
2. Validate strict schemas and reject unknown fields before append.
3. TRAIN/SUPPORT is learner-visible only when split role and provenance policy permit it.
4. Gate-Final, Locked-Test and Post-deploy raw labels are evaluator-only at storage, API and process levels.
5. Freeze is durable before prediction commit; commit is durable before reveal.
6. Evaluator reveal cannot invoke learner feedback, candidate revision or support ingestion.
7. Challenge release is a separate minimal event; it contains no label, target, expected answer or raw evaluator reference in learner-facing DTOs.
8. Challenge delivery is at-least-once with stable ID; acknowledgement is idempotent and does not imply successful reconsideration.
9. A crash after commit but before response is resolved by retrying the same principal-bound idempotency key and returning the original receipt.
10. Replay validates every event; a digest detects changes but is not authentication or authorization.

## 7. Cursor and side-channel policy

A learner cursor is an opaque broker-issued token, not the global SQLite sequence. It must not reveal the count or timing of hidden evaluator events. Internally the broker may use global sequence positions; externally learner pagination uses per-track visibility cursors or opaque continuation tokens.

Normalize authorization failures and avoid exposing whether a hidden evaluation ID exists. Response size and timing may also leak activity; do not claim timing-side-channel resistance in v0.1.

## 8. Storage and operational controls

- Database, WAL, shared-memory and backup files are accessible only to the broker service account.
- Learner/evaluator processes use distinct OS identities or containers with no shared DB mount.
- Client packages do not receive SQLiteEvidenceStore, database paths or raw append methods.
- Secrets stay outside the repository and event payloads.
- Broker startup performs migration and replay verification before serving requests.
- Backups preserve the same access boundary; restore is followed by full replay/digest verification.
- Audit logs record principal, capability, operation, request digest, receipt/event IDs and denial class, but never copy raw labels into learner-visible logs.

## 9. Failure semantics

| Failure | Required behavior |
|---|---|
| Authentication/capability failure | deny before protected lookup; no append |
| Track/episode mismatch | deny without revealing hidden-object existence |
| Unknown schema key | reject entire request |
| Idempotency key reused with different digest | conflict; preserve original event |
| Concurrent sequence conflict | retry internally or return retryable conflict |
| Commit succeeds, response lost | same-key retry returns original receipt |
| Projection rebuild fails after commit | return recovery-required receipt; rebuild before next read |
| Replay integrity failure | fail closed; serve no learner/evaluator reads |
| Evaluator unavailable | continue only with already authorized visible state |
| Policy authority unavailable | no new challenge release |

## 10. Adversarial acceptance tests

Before claiming isolation, tests must show:
- learner OS identity cannot open DB/WAL/backup files;
- learner API has no raw-event or evaluator-projection operation;
- forged actor_role fields do not grant evaluator/policy authority;
- extra label/evaluator keys are rejected recursively;
- learner cannot enumerate another track or infer hidden object existence through errors;
- evaluator API cannot revise learner candidates;
- challenge budget is cumulative across policy versions/episodes as configured;
- a source evaluation produces at most one challenge by default;
- concurrent duplicate writes preserve one receipt and one event;
- crash after commit/before response is safe under idempotent retry;
- restart/replay produces stable learner DTOs with no hidden payload or hidden sequence-gap leakage;
- process-level tests use distinct OS identities/credentials, not mocked role strings alone.

## 11. Implementation sequence

1. Freeze DTO schemas and operation allowlists in a versioned protocol module.
2. Implement a broker facade that owns the store and exposes typed operations; mark it as an in-process test adapter, not a security boundary.
3. Implement Unix-domain socket server/client with OS peer-credential authentication and separate service/learner/evaluator identities.
4. Add broker-side principal-to-capability mapping and signed policy authorization.
5. Run CI integration tests with broker and clients as separate processes; assert filesystem permissions.
6. Connect E09ChallengeInbox to a reconsideration controller that can request probes but cannot access labels.
7. Only after these tests pass, describe evaluator/learner isolation as implemented.

## 12. Current status

- v0.3 event semantics and learner/evaluator projections: experimental implementation in the PR stack.
- Label-free challenge release and inbox: implemented; latest PR #132 full workflow passed.
- Trusted broker contract: specified here.
- Broker facade, IPC server, OS identities and capability authentication: not implemented.
- Real process/file isolation: not implemented.
- Active-probe/reconsideration controller: not implemented.

Correct current claim: **the protocol has safer evaluator/learner projections and a constrained challenge-signal path; it does not yet provide a trusted process boundary.**
