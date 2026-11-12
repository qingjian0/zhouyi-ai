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
- Every scratch-state mutation is wrapped in a SQLite write transaction. If a
  mutation fails after the authoritative event append, the adapter rebuilds
  scratch state from the event log; if rebuilding fails, it fails closed.
- Multi-event candidate/evidence bundle application uses the same transaction
  and recovery boundary, so a partial bundle is never exposed as current state.
- PersistentLifecycleLedger.close() removes the temporary database
  deterministically; context-manager exit also closes it. A finalizer remains
  as a fallback for abandoned instances.

## Exact-head validation

- Current runtime HEAD: `16784d50ad0f310f0768c87a4cb094c5a15bbc8f`.
- Earlier full validation before transaction/recovery changes: [workflow #43264128911](https://github.com/qingjian0/zhouyi-ai/actions/runs/43264128911), success.
- Earlier RSS sweep: [workflow #43264128876](https://github.com/qingjian0/zhouyi-ai/actions/runs/43264128876), success.
- Current exact-head full validation: [workflow #43266082592](https://github.com/qingjian0/zhouyi-ai/actions/runs/43266082592), running.
- Current exact-head RSS sweep: [workflow #43266082577](https://github.com/qingjian0/zhouyi-ai/actions/runs/43266082577), running.

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

The table above is historical output from the earlier benchmark revision.
That revision mixed `/proc/self/status` VmRSS with `resource.getrusage()` peak
RSS and exposed an accounting discrepancy. The current benchmark reads both
current RSS (`VmRSS`) and high-water RSS (`VmHWM`) from `/proc/self/status`.
The new exact-head sweep is pending; the historical table must not be treated
as the result of the current instrumentation.

## Remaining acceptance gates

- Measure startup latency and write-path/query cost at 1K/10K/50K/100K/500K.
- Add disk-full and scratch-database initialization-failure cleanup tests.
- Exercise process termination and concurrent-adapter stress.
- Confirm scratch-file cleanup on normal close and all failure paths.
- Re-run and publish the VmRSS/VmHWM-consistent RSS sweep.
- Continue to keep explicit `ledger`/ `snapshot()` materialization outside
  bounded-memory claims.

This is an intermediate engineering step. It does not replace semantic event
replay with SQL triggers, skip replay validation on startup, or establish
bounded memory for every ordinary write/query path.


## Restore-latency instrumentation

The benchmark now reports `restore_duration_seconds` and
`restore_events_per_second` around `PersistentLifecycleLedger` construction.
This separates E12-A6 semantic replay time from fixture generation and ZPCM
initialization. Throughput is descriptive for the tested synthetic event mix;
it is not a production SLA or a claim that every lifecycle event has equal cost.
