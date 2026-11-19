# P5-C bounded evidence hydration

Status: first implementation slice; requires CI validation before integration.

## Contract

`MemoryPacket` remains a compact, provenance-preserving projection. The
hydration layer resolves its exact `EvidenceRef` values through the M1
resolver so a downstream caller can obtain source text without treating IDs
alone as evidence content.

- Resolve references in deterministic packet-item/source-reference order.
- Deduplicate identical references for I/O, then associate the resolved text
  with every packet record that cited it.
- Enforce independent maximum unique-reference and UTF-8 byte budgets before
  requesting source content.
- Verify resolver result order, exact reference identity, text type, ordinal,
  and UTF-8 byte length.
- Propagate stale-manifest and source-integrity failures; never silently skip
  invalid evidence.
- Return `BUDGET_EXHAUSTED` whenever not all unique references fit.
- Preserve the original packet and its provenance; hydrated text is a separate
  derived result and is not written back into M2/ZPCM.

## Limits

This slice does not add semantic ranking, vector search, lifecycle resolution,
evidence summarization, model conditioning, or cognitive capability claims.
The SQLite resolver still verifies the complete document manifest for each
distinct document in its read snapshot; performance profiling and grouped
multi-document resolution remain follow-up work. The byte budget bounds source
text returned by this API, not all Python object overhead or resolver internals.
