# CSG-GCR → E09 → E12-A6 → ZPCM end-to-end lifecycle v0.1

## Scope

This integration test validates a complete single-branch candidate lifecycle using the real typed CSG-GCR adapter, strict E09 SQLite event chain, PersistentLifecycleLedger, and ZPCM event replay.

## Verified path

1. Typed CSG-GCR produces an OBSERVED candidate with three evidence references.
2. E09 verifies SUPPORT, GATE_FINAL, and LOCKED_TEST observation → prediction commit → reveal chains.
3. The ingestion adapter requires explicit world-family context and atomically registers the candidate plus redacted evidence DTOs.
4. E12-A6 validates OBSERVED → PROPOSED → DISCRIMINATION_PENDING → TRAIN_SUPPORTED → GATE_VALIDATED → CHALLENGED.
5. TRAIN_SUPPORT consumes only the SUPPORT-derived TRAIN evidence; GATE_VALIDATE consumes GATE_FINAL; CHALLENGE consumes LOCKED_TEST.
6. ZPCM persists every registration/action event. A fresh PersistentLifecycleLedger reconstructs the exact candidate state, evidence roles, and action history by replay.

A separate negative test proves GATE_DEV cannot satisfy GATE_FINAL validation and that a rejected transition creates no durable lifecycle event.

## Data and authority boundaries

- E09 retains raw labels. E12-A6 and ZPCM receive opaque evidence references only.
- E12-A6 is the only lifecycle state machine.
- ZPCM is the durable event history and replay authority.
- CSG-GCR supplies typed structure and uncalibrated ranking metadata.
- Cross-branch candidates remain blocked until E09 authorization issuer verification exists.

## Limits

This is a deterministic trusted single-process SQLite reference integration test. It does not establish distributed transactions, OS-level process isolation, authenticated IPC, production deployment readiness, or scientific validity of the candidate semantics.
