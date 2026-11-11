# Durable Execution Challenge and Replay Guard (P1.6.4)

## Purpose

P1.6.3 signs per-execution sandbox evidence, but its verifier is stateless.
A correctly signed attestation could be submitted more than once unless the
challenge is issued and consumed through a durable, atomic replay guard.

## Challenge lifecycle

1. The trusted orchestrator issues a fresh 256-bit random nonce for one
   execution, binding it to the exact manifest digest, patch digest, target
   branch, runner ID, immutable image digest, and a short expiry.
2. The trusted supervisor receives the challenge and configures/verifies the
   required controls for that exact execution.
3. The supervisor signs a P1.6.3 attestation containing the same bindings and
   nonce. The attestation expiry cannot extend beyond the challenge expiry.
4. The verifier checks the HMAC and all P1.6.3 bindings.
5. The SQLite store atomically marks the nonce consumed under
   `BEGIN IMMEDIATE`. A second consumer is rejected, including across store
   instances reopening the same database.

## Persistence and concurrency

- A primary-key constraint makes nonce issuance unique.
- A transaction serializes concurrent consumers before checking and updating
  `consumed_at`.
- The SQLite file must live on durable storage with restrictive filesystem
  permissions and backups appropriate to the execution controller.
- This implementation is a single-host replay ledger. It is not a distributed
  consensus service and does not provide cross-host atomicity on arbitrary
  network filesystems.
- Deleting or rolling back the database can re-enable replay. Treat the ledger
  as security-critical state; do not restore an older snapshot without
  invalidating all outstanding challenges and keys.

## Trust boundary

The store does not enforce sandbox controls and does not prove supervisor
honesty. It must be called only after cryptographic verification succeeds.
The HMAC key must remain outside this database and must never be logged or
stored in the repository. Nonce issuance must occur in a trusted orchestrator;
agent-controlled callers must not choose arbitrary nonces.

## Not implemented

- No real supervisor, container lifecycle, OS sandbox, runtime watchdog, or
  continuous enforcement.
- No distributed nonce ledger, hardware-backed key, or asymmetric signing.
- No automatic recovery policy after database loss or rollback.
- No cleanup of expired challenge rows; retention policy is a separate
  operational decision.

## Validation

Tests cover successful one-time consumption, replay rejection, persistence
across store reopen, signature failure without consumption, binding mismatch,
expiry, challenge-window enforcement, nonce collision, and invalid TTL/input.
