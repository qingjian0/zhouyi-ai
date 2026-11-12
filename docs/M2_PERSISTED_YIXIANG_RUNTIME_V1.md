# Persisted M2 → TRLW → Yixiang/SROK → CSG-GCR Runtime

## Executable path

1. M1 stores source bytes and resolves immutable EvidenceRefs.
2. M2 semantic-unit candidates are persisted as append-only ZPCM events. The writer supports record, revision, and retraction lifecycle events.
3. `PersistentM2SemanticUnitReader` uses reverse keyset pages and indexed predecessor reads to expose only the latest active candidate version for each root.
4. TRLW selects a byte-bounded working set from the reader. Its source scan has an explicit event cap; hitting the cap produces `SOURCE_INCOMPLETE`.
5. `run_persisted_yixiang_search` retrieves the requested current relation candidate, composes role transforms against the bounded TRLW workspace, and coordinates the resulting typed proposals through CSG-GCR.
6. Every output remains `HYPOTHESIS_ONLY`. The runtime does not write E12-A6 lifecycle events or promote hypotheses to facts.

## Provenance

- M1 EvidenceRefs remain source-byte provenance.
- E09 observation-event references are supplied separately and must cover exactly the relation and workspace candidate records.
- XSL transform-prior references remain derivation metadata; they are not inserted into observational evidence.
- `GROUNDED` is not treated as `TRUE`; candidate truth status is preserved.

## Limits

This path starts from already-grounded, persisted M2 semantic-unit candidates. It does not yet implement raw Observation text parsing, entity resolution, or an autonomous semantic extractor. The M2 semantic-unit writer still reconstructs its full lifecycle history on startup; the new reader bounds query memory, but writer-side memory remains a separate P0. The E09 event references are verified by the upstream E09 authority boundary, not by the Yixiang adapter itself.

## Acceptance

The integration test creates real M1 evidence, persists typed M2 candidates, writes a real E09 observation event, pages current candidates into TRLW, runs the XSL/SROK role transform, and compiles typed CSG-GCR hypotheses. It asserts the scan-incomplete path fails closed and that no E12-A6 lifecycle event is written.