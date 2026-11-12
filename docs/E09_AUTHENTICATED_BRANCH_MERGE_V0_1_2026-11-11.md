# E09 authenticated branch-merge authorization v0.1

## Problem

The earlier BranchMergeAuthorization value object checked only declared parent, branch IDs and evidence references. It did not authenticate the issuer. A caller could construct a structurally valid receipt and pass it to TypedCandidateCoordinator. Structural scope validation is not authorization.

## New E09 event contract

Strict E09 v0.3 adds `branch_merge_authorization` events. The event must be appended with actor role `authorizer` and contain:

- authorization_id (equal to the event ID)
- issuer_id
- scope and parent_state_ref
- exact branch_ids set
- evidence_refs
- timezone-aware issued_at and expires_at
- signature_algorithm and signature

The event's E09 envelope digest protects its immutable event representation. The signature covers canonical JSON containing episode_id, event_id and the complete payload excluding the signature field. Causation refs must exactly equal evidence_refs. Every cited evidence reveal must precede the grant and pass the existing strict E09 observation/commit/reveal verifier.

## Trust model

The resolver accepts an injected signature-verification callback backed by an out-of-band trusted issuer keyring, normally pinned public keys. The callback receives issuer_id, algorithm, canonical signed bytes and signature. The caller also supplies verifier_id to record which trusted keyring/configuration performed verification.

The repository deliberately does not ship private signing keys, a hard-coded issuer, or an insecure default verifier. A test callback validates wiring only; production must supply a real cryptographic verifier and managed issuer key rotation/revocation policy. E09's SHA-256 event envelope digest alone is not proof of issuer identity.

## Merge enforcement

- Plain BranchMergeAuthorization is an unverified claim and is rejected by validate_merge_authorization.
- Typed CSG-GCR cross-branch coordination requires VerifiedBranchMergeAuthorization.
- Persistent ingestion requires the verified authorization to match the candidate's exact parent state, branch set, authorization event reference and evidence provenance.
- Single-branch ingestion does not accept an unnecessary merge authorization.
- Expired, not-yet-valid, wrong-parent, wrong-scope, wrong-branch, missing-evidence, malformed or bad-signature grants fail closed.

## Remaining production gates

This is an in-process trust adapter over the single-process SQLite E09 reference store. It does not provide evaluator process isolation, hardware-backed keys, authenticated IPC, key rotation/revocation service, distributed consensus, or tamper-evident remote replication. Those must be addressed before production use.
