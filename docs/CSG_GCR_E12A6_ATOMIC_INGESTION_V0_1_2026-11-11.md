# CSG-GCR atomic ingestion into E12-A6 and ZPCM v0.1

## Purpose

Provide one fail-closed ingestion operation from a typed CSG-GCR result into the persistent E12-A6 lifecycle. The operation resolves every declared proposal evidence reference against E09, then atomically appends all E12-A6 evidence registrations and the candidate registration in one ZPCM transaction.

## Execution order

1. Reject candidates spanning more than one branch. Cross-branch ingestion remains blocked until E09 can authenticate BranchMergeAuthorization issuer credentials.
2. Adapt the typed CSG-GCR result into an E12-A6 OBSERVED candidate.
3. Require an explicit world-family value for every candidate evidence reference.
4. Resolve each reference through the strict E09 observation → prediction commit → reveal verifier.
5. Stage a copy of the E12-A6 ledger; register all redacted evidence DTOs and the candidate on the staged ledger.
6. Append the evidence events and candidate event as one SQLite transaction in ZPCM.
7. Swap the staged ledger only after the entire batch commits.

Any invalid evidence reference, split mismatch, missing world-family context, stale sequence, or failed append leaves both the live E12-A6 ledger and the ZPCM lifecycle event stream unchanged.

## Atomic batch semantics

ZPCM accepts only all-new or all-replayed batches. A mixed prior/new batch is rejected as a partial-bundle conflict. The entire batch is enclosed by BEGIN IMMEDIATE; a failed insert rolls back every event. Repeated complete ingestion returns the original event receipts without adding new events.

## Ownership boundaries

- CSG-GCR supplies typed candidate structure and ranking metadata only.
- E09 verifies reveal evidence and owns raw target payloads/split visibility.
- E12-A6 validates candidate/evidence registration and remains the sole lifecycle state machine.
- ZPCM persists the ordered lifecycle event bundle and provides replay.

Raw target_or_feedback is never copied into the E12-A6 evidence DTO or ZPCM lifecycle events. Branch-delta and authorization provenance remains on the candidate, but cross-branch candidates are rejected until authorization issuer verification exists.

## Limits

Trusted single-process SQLite reference implementation. No distributed consensus, process isolation, authenticated E09 operator identity, or transactional cross-process outbox is claimed.
