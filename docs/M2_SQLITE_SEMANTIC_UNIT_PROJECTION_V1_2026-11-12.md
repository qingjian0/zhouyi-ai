# M2 SQLite semantic-unit projection v1

Date: 2026-11-12

## Purpose

Remove corpus-sized semantic-unit history restoration from
`PersistentM2SemanticUnitStore.__init__`. The append-only
`memory_events` stream remains the sole source of truth. SQLite tables in this
change are disposable, derived projections.

## Projection layout

- `m2_semantic_unit_versions`: one compact metadata row per immutable
  candidate version (scope, record/root/predecessor IDs, event identity,
  sequence, and digests). It contains no candidate body.
- `m2_semantic_unit_roots`: one row per candidate lineage, containing only
  its current candidate body, current version metadata, and optional
  retraction reason.
- `m2_semantic_unit_projection_state`: per-scope mutation generation,
  advanced by SQLite triggers for every projection insert/update/delete.
- `m2_semantic_unit_projection_checkpoint`: schema version, event high-water
  mark, projection generation, and a digest binding those values.

## Runtime behavior

1. Startup validates the checkpoint in constant-size metadata queries.
2. A valid checkpoint avoids historical event replay. It revalidates current
   active candidate evidence in bounded byte pages.
3. A missing, stale, or corrupt checkpoint triggers a transactionally rebuilt
   projection. Event pages are consumed incrementally; candidate bodies are
   decoded and discarded one at a time.
4. New candidate/revision/retraction events and their projection mutations are
   committed in one `BEGIN IMMEDIATE` transaction. A projection failure rolls
   back the event append too.
5. `iter_candidates` is the bounded current-working-set API. The legacy
   `candidates` and `history` properties explicitly materialize results for
   compatibility/export and should not be used by bounded runtime paths.

## Invariants

- The event log is authoritative; projections can be deleted and rebuilt.
- Version bodies are not copied into the versions metadata table.
- Revision must extend the active current version exactly once.
- Retraction is a tombstone and does not delete history.
- A stale cross-instance writer fails closed or refreshes from the projection;
  it must not overwrite a newer current version.
- E09/E12 authorization code and event formats are unchanged.

## Limits and outstanding verification

This change bounds Python memory used by historical candidate bodies during
startup and exposes byte-bounded current-candidate iteration. The SQLite
projection itself still grows on disk with version metadata and current bodies.
No RSS, latency, or million-token capability claim is made here. CI, crash
injection, multi-connection behavior, and large-history RSS measurements must
pass before this is considered production-ready.
