# M2 Bounded Semantic-Unit Reader and MemoryPacket Integration

## Read path

`PersistentM2SemanticUnitReader` reads the append-only M2 semantic-unit event stream newest-first using ZPCM reverse keyset pagination. It does not instantiate the writer's corpus-sized in-memory history maps.

Candidate revisions are followed through immutable predecessor IDs to a root record. The newest lifecycle event for each root wins. A retraction marks that root as unavailable, so older candidate versions cannot reappear. EvidenceRefs are revalidated against M1 at read time.

## Memory and work bounds

- SQLite pages contain at most the configured page size (1–4096 events).
- The reader retains only the set of roots encountered during the current scan.
- `max_scan_events` is a hard limit in [1, 65536], default 4096.
- `MemoryPacket` separately enforces max_records and byte_budget.
- If the scan budget is reached before the stream is exhausted, the packet is marked `BUDGET_EXHAUSTED`; it is never mislabeled `NOT_FOUND`.
- The query order is explicit: `latest-lifecycle-event-desc-v1`.

The root set is bounded by max_scan_events, not by total corpus size. This bounds Python memory independently of the total number of persisted candidates, subject to the size of an individual candidate and page.

## Remaining limitation

`PersistentM2SemanticUnitStore` remains the append/revision/retraction writer and currently reconstructs a full in-memory history during initialization. The new reader avoids that cost on query paths, but a fully bounded deployment still needs the writer to move lifecycle state to indexed SQLite projections or use stateless event-based writes. This PR does not claim that the entire M2 lifecycle runtime is yet O(1) memory.

## Validation

Tests cover reverse keyset pagination, latest-version selection, tombstone exclusion, no full-stream replay, evidence revalidation, packet limits, and scan-budget incompleteness.