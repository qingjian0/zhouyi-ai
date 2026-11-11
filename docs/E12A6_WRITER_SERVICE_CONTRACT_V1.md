# E12-A6 Receipt-Authorized Writer Service v1

Status: implemented reference service facade; OS/process isolation and network IPC are not included.

## Request flow

The writer service accepts only a narrow cross-branch candidate submission:

1. Authenticate the caller's transport credential into a server-derived workload identity.
2. Require the candidate_submitter role and the exact lifecycle scope.
3. Verify the signed E09 JSON receipt against a pinned verifier key and server-owned clock.
4. Derive the internal VerifiedBranchMergeAuthorization capability only after receipt verification.
5. Run TypedCandidateCoordinator inside the writer process using the supplied typed proposals, base state and branch snapshots.
6. Require a unique selected proposal set, then adapt the recomputed result into an E12-A6 OBSERVED candidate.
7. Compare the recomputed parent, branch set, authorization reference, authorization evidence subset and complete candidate evidence set against the signed receipt.
8. Register redacted evidence, candidate and authorization-consumed event in one ZPCM SQLite transaction.

The writer has no E09 database dependency. Evidence DTOs arrive only inside the verifier-signed receipt. Raw E09 labels remain in the E09 store.

## Security properties

- Callers cannot pass a VerifiedBranchMergeAuthorization Python object.
- The writer does not trust a caller-precomputed MergeResult; it reruns typed coordination and branch merge validation.
- Role and scope claims come from the configured authenticator, not request fields.
- The receipt is checked for Ed25519 signature, fixed audience, verifier identity, expiry, parent, exact branches, authorization evidence and all candidate evidence.
- The persistent ledger consumes receipt ID and nonce atomically with candidate/evidence writes.
- Same-receipt retries within the receipt TTL are idempotent; cross-candidate receipt reuse is rejected.

## Remaining production gates

- Host this service in a dedicated process with exclusive write permission to the E12-A6/ZPCM database.
- Use authenticated IPC (mTLS or equivalent workload identity) and isolate E09 verifier, E09 authority and E12 writer under separate OS identities.
- Hold verifier signing keys in HSM/KMS and pin verifier public keys out of band.
- Persist the authenticated submitter identity in the lifecycle audit event.
- Add external monotonic checkpoints and restore-time anti-rollback verification.
- Add service-level concurrency/load tests and process-crash integration tests.

This module is a reference service boundary, not a defense against malicious code with access to the same Python process or database file.
