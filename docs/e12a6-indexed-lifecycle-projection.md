# E12-A6 indexed lifecycle projection

## Authority

`prototype/zpcm_memory.py` owns a derived SQLite index named
`e12a6_lifecycle_event_projection`. The authoritative event body and digest
remain in `memory_events`; the projection stores only event identity metadata.

## Indexed identity

Each lifecycle row is indexed by:

- scope
- event kind
- entity ID (candidate, evidence, action, or receipt)
- entity version
- event sequence

The insert trigger keeps the projection in the same SQLite transaction as the
authoritative event append. Existing rows are backfilled with a set-based
`INSERT ... SELECT`, avoiding a Python list proportional to history size.

## Read contract

`get_lifecycle_projection_event()` resolves an event ID through the entity
index, then calls `get_domain_event()`. The latter enforces the configured
payload-byte limit and verifies the digest against the authoritative event.

`iter_lifecycle_projection()` yields metadata pages only. It does not fetch or
materialize event bodies.

## Deliberate limitation

The current `PersistentLifecycleLedger._restore()` still replays into
`LifecycleLedger`, whose candidate, evidence, and action collections grow with
history. This projection is groundwork for a subsequent SQLite-backed state
reader and validator; it is not yet the bounded-memory lifecycle implementation.
