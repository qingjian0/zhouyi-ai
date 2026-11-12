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

## Exact-head validation

- Runtime HEAD: `00ba6a48fad8967afc2af7367a992a9e78c82e05`.
- Full validation: [workflow #43264128911](https://github.com/qingjian0/zhouyi-ai/actions/runs/43264128911), success.
- RSS sweep: [workflow #43264128876](https://github.com/qingjian0/zhouyi-ai/actions/runs/43264128876), success.
- Artifact: `e12a6-restore-rss-00ba6a48fad8967afc2af7367a992a9e78c82e05`.

## Measured restore RSS

The isolated benchmark builds each fixture before launching a fresh restore
subprocess. It reports RSS before ZPCM initialization, after ZPCM
initialization, after E12-A6 replay, and the OS peak counter.

| Lifecycle events | Fixture DB | RSS after restore | Restored candidates | Indexed events |
|---:|---:|---:|---:|---:|
| 1,000 | 1.90 MiB | 24.97 MiB | 1,000 | 1,000 |
| 10,000 | 17.55 MiB | 27.45 MiB | 10,000 | 10,000 |
| 50,000 | 87.74 MiB | 27.45 MiB | 50,000 | 50,000 |
| 100,000 | 175.90 MiB | 27.40 MiB | 100,000 | 100,000 |
| 500,000 | 901.86 MiB | 27.49 MiB | 500,000 | 500,000 |

At 50K events, the prior in-memory restore baseline (PR #349) was 70.69 MB
(about 67.42 MiB); this branch measured 28.78 MB (about 27.45 MiB), an
observed reduction of approximately 59.3%. From 10K through 500K events,
post-restore RSS remained within approximately 0.1 MiB of 27.4–27.5 MiB.

These are observed GitHub Actions Linux/Python 3.11.18 results, not a hard
memory guarantee. The 500K fixture occupies about 902 MiB on disk; the result
is bounded in-process replay-state memory, not bounded storage consumption.

### Measurement caveat

For the 100K and 500K rows, the reported post-restore `/proc/self/status`
VmRSS is slightly higher than the `resource.getrusage().ru_maxrss` value
reported by the same child process. Since a high-water RSS counter should not
be below a contemporaneous RSS sample, the peak-counter field needs an
instrumentation audit. The post-restore VmRSS values and complete replay
counts remain directly reported by the artifact; do not use the peak field
as an acceptance metric until reconciled.

## Remaining acceptance gates

- Measure startup latency and write-path/query cost at 1K/10K/50K/100K/500K.
- Add disk-full and scratch-database initialization-failure cleanup tests.
- Exercise process termination and concurrent-adapter stress.
- Confirm scratch-file cleanup on normal close and all failure paths.
- Audit the `ru_maxrss` versus `VmRSS` discrepancy and use a consistent
  process/cgroup measurement source.
- Continue to keep explicit `ledger`/ `snapshot()` materialization outside
  bounded-memory claims.

This is an intermediate engineering step. It does not replace semantic event
replay with SQL triggers, skip replay validation on startup, or establish
bounded memory for every ordinary write/query path.
