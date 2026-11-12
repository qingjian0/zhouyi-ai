# M2 Lazy Observation Store and Bounded Replay

## Problem

The first persistent M2 adapter wrote observations into ZPCM's shared event log but eagerly replayed the complete stream during construction and retained three corpus-sized dictionaries (observations, receipts, and record digests). Persistence therefore did not bound the default Python working set.

## Contract

- Construction reads only the indexed stream high-water mark. It does not replay event bodies or construct an observation cache.
- `get_observation(record_id)` and `get_receipt(record_id)` use a single indexed event lookup.
- `iter_observations(after_sequence, page_size)` uses ZPCM keyset pagination and validates each event as it is yielded.
- The compatibility `observations` property explicitly materializes a full dictionary only when a caller asks for it. New runtime code must use indexed lookup or the paged iterator.
- Raw source bytes remain in M1. M2 stores typed Observation DTOs and immutable EvidenceRefs only.
- SQLite's unique event ID and digest check arbitrate retries. Record IDs remain immutable; revisions require new IDs.
- A bounded retry loop refreshes the per-stream sequence after unrelated concurrent appends.

## Memory Bound

For the default API, Python-side retained state is O(1) per store. During iteration, decoded event memory is bounded by the ZPCM page size plus the current observation and one source chunk resolved from M1. The explicit compatibility property is O(N) by design and must not be used in the runtime hot path.

This is a structural bound, not yet an RSS benchmark. A later acceptance test must measure process RSS while replaying a large synthetic stream and verify that increasing corpus size does not increase retained memory beyond the configured page and single-record working set.

## Validation

Tests cover lazy construction, indexed retrieval without calling the full-stream iterator, keyset paging/resumption, idempotent append, immutable record IDs, evidence verification, and restart recovery.