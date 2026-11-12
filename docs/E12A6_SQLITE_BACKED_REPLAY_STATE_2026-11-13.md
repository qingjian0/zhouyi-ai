# E12-A6 SQLite-backed replay state — 2026-11-13

## Purpose

This branch keeps E12-A6's authoritative event-by-event semantic replay while
moving the accumulating compatibility ledger collections to a temporary
SQLite database. Candidate/evidence mappings, action history, and action-ID
membership use disk-backed collections with bounded 128-row iteration.

## Safety and lifecycle

- The ZPCM append-only event log remains authoritative.
- Replay still validates event schema, sequence, candidate/evidence references,
  lifecycle transitions, revision reconstruction, and authorization receipt
  bindings.
- The temporary replay database is scratch state only; it is not a checkpoint
  and is not used as an authority source.
- PersistentLifecycleLedger.ledger and snapshot() are explicit full
  materialization boundaries.
- PersistentLifecycleLedger.close() removes the temporary database
  deterministically; context-manager exit also closes it. A finalizer remains
  as a fallback for abandoned instances.

## Measurement

The branch enables the existing isolated E12-A6 RSS benchmark workflow. It
constructs fixtures outside the measured subprocess and reports RSS before
ZPCM initialization, after initialization, after lifecycle replay, and peak
RSS. It also reports restored candidate counts and indexed event counts.

The previous in-memory restore baseline (PR #349, 2026-11-12) measured:
- 1,000 events: 25.09 MB after restore
- 10,000 events: 34.17 MB after restore
- 50,000 events: 70.69 MB after restore

These are baseline measurements, not results for this SQLite-backed branch.
No memory reduction or bounded-RSS claim is made until the branch's own
exact-head benchmark artifact is inspected.

## Acceptance gates still open

- Exact-head full validation.
- Exact-head RSS benchmark comparison at 1K/10K/50K events.
- 100K/500K scale tests before making large-history claims.
- Temp-file cleanup under normal close, process termination, disk-full, and
  concurrent adapter stress.
- A separate review of startup latency and write-path query cost.

This is an intermediate engineering step. It does not replace semantic event
replay with SQL triggers or skip replay validation on startup.