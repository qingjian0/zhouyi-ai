# v0.3 Policy-Gated Minimal Challenge Release

Status: protocol implementation slice; not a database or process security boundary.

## Purpose

An evaluator may need to tell a learner that a committed prediction deserves reconsideration without disclosing the hidden target label. The release path therefore carries a minimal challenge descriptor, not the evaluation payload.

## Event order

1. Persist the candidate structures.
2. Persist `candidate_set_freeze`.
3. Persist the matching `prediction_commit`.
4. Persist evaluator-only `evaluation_reveal`.
5. A policy authority persists an immutable `challenge_release_policy`.
6. A release-policy executor appends `challenge_release` only when the source evaluation, learner track, evaluation role, challenge kind, and release budget satisfy that policy.

## Policy contract

A policy binds:
- policy ID and learner track;
- sorted allowed evaluation roles;
- sorted allowed challenge kinds;
- a positive per-policy release budget;
- a digest over the complete policy contract.

The policy must be written with `actor_role=policy_authority`. The release event must be written with `actor_role=release_policy`. These role strings are protocol assertions, not cryptographic identities; deployment must authenticate these principals outside this SQLite reference store.

## Minimal learner-visible payload

The learner projection receives only:
- `challenge_id`;
- `observation_id`;
- `challenge_kind` (one of `RECONSIDER`, `INSUFFICIENT_EVIDENCE`, `BOUNDARY_CASE`, `INVARIANCE_CHECK`).

It does not receive source evaluation ID, prediction ID, evaluator role, policy internals, target, expected answer, label digest, or evaluator provenance. The durable event schema is exact-key allowlisted, so adding a target/label field is rejected.

The challenge kind is deliberately non-answer-bearing. It signals a type of review, not whether the prediction was correct or what the correct answer is.

## Replay invariants

Replay rechecks:
- policy digest and policy uniqueness;
- release actor role;
- source evaluation and prediction linkage;
- learner-track match;
- evaluation-role and challenge-kind authorization;
- source observation identity;
- challenge digest;
- unique challenge ID and per-policy release budget.

The learner projection invokes evaluator replay validation but returns only the minimal allowlisted challenge descriptor.

## Explicit limits

- The SQLite log still contains raw evaluation labels.
- The policy/actor role strings are not authenticated credentials.
- A process with raw database access can bypass projections.
- This is not a differential privacy mechanism, secure enclave, or formal noninterference proof.
- The current challenge is a review signal, not supervised training feedback. It must not be passed to E09 `reveal_feedback`, `PrequentialRunner.reveal`, or E12 support evidence.
- A future trusted service must own the database connection, authenticate evaluator/policy/learner principals, enforce release policy, and expose only the narrow learner projection.
