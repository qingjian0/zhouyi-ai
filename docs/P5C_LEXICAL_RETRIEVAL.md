# P5-C lexical retrieval baseline

Status: research implementation; exact-head CI required before integration.

## Policy

- Policy ID: `lexical-overlap-v1`.
- Query and candidate text use case-folded Latin/digit terms, CJK single-character
  terms, and adjacent CJK bigrams.
- Candidate fields: surface forms, typed attribute names/types/values/units,
  role names/targets, and canonical key.
- Score: unique query-term coverage, in [0, 1].
- Stable tie-break: immutable record ID.
- Retrieval keeps at most `max_records` candidate objects and scans at most
  `max_scan_events` records from the append-only source stream.
- Scope, required type, and temporal constraints are applied before ranking.
- Reaching the scan cap is reported conservatively as BUDGET_EXHAUSTED.

## Claim boundaries

This is lexical matching, not semantic similarity, embeddings, lifecycle
resolution, learned relevance, or analogy. It is a transparent baseline for
later comparisons. It does not infer truth and does not establish cognitive
improvement. The packet byte budget still applies independently after top-k
selection.
