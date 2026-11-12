# M2 Grounded Observation → Yixiang/SROK Bridge v1

Date: 2026-11-12  
Status: executable research slice; not a production grounding pipeline.

## Scope

This slice adds a strict adapter from M2 `SemanticUnitCandidate` records into the existing explicit XSL role-transform and bounded SROK search.

It does **not** parse raw text, perform OCR, resolve entity identity, adjudicate truth, or automatically discover analogies. It consumes candidates produced by an upstream extractor/grounder and refuses any candidate whose grounding status is not `GROUNDED`.

## Data path

```text
M1 immutable EvidenceRef
        │
        ▼
M2 SemanticUnitCandidate (typed, scoped, versioned)
        │  all role participants must be GROUNDED
        │  relation role order is preserved
        ▼
M2 Yixiang grounding adapter
        │  E09 event refs are supplied separately
        ▼
explicit versioned XSL RoleTransform
        │
        ▼
bounded SROK-0 role composition
        │
        ▼
Typed CSG-GCR proposal (HYPOTHESIS_ONLY)
```

## Provenance separation

Three reference classes must not be conflated:

1. **M1 source references**: exact document/chunk/hash/byte-span references stored in each M2 envelope. The adapter hashes their canonical DTO representation for trace metadata.
2. **E09 observation-event references**: supplied per M2 record by the caller and carried into SROK/CSG-GCR evidence refs. The E09 verifier remains the authority that checks their existence, signatures, scope, domain, and authorization. The adapter does not mint or verify E09 evidence.
3. **XSL transform-prior references**: remain derivation/prior metadata. They are never inserted into the evidence-ref set.

This prevents an M1 chunk locator or an analogy prior from being misrepresented as an authenticated E09 event.

## Grounding and truth

- `GROUNDED` means the source/derivation locators satisfy the M2 grounding contract; it does not mean `TRUE`.
- The adapter preserves the source candidates' truth status and does not infer `SUPPORTED`.
- Every transformed composition and typed CSG-GCR proposal remains `HYPOTHESIS_ONLY`.
- XSL is explicit and versioned. This slice does not learn or infer a role transform from raw language.
- Relation role order is semantic and is preserved before applying the declared permutation.
- SROK-0 uses neutral score 0.0. Extractor confidence, source reliability, calibrated probability, and ranking scores are not silently converted into SROK priority.

## Constraints

- Relation and workspace candidates must share one scope.
- Every workspace candidate must be grounded and typed (not `UNKNOWN`).
- Every record must map to at least one E09 observation event reference.
- The E09 reference map must cover exactly the relation record and workspace records.
- Current SROK-0 cannot represent repeated identity in two roles; such relations fail closed.
- Search candidate/expansion budgets remain explicit and report truncation/exhaustion.
- CSG-GCR proposals retain mutual exclusion between alternative SROK assignments.
- E12-A6 remains a hard lifecycle boundary: `HYPOTHESIS_ONLY` proposals cannot become lifecycle evidence or durable facts.

## TRLW working-set status

This branch now includes an executable, ephemeral TRLW projection in `prototype/trlw_working_set.py`.

- `TRLWQuery` constrains scope, requested types, allowed grounding states, valid-time interval, record count, and canonical serialized-byte budget.
- `build_trlw_working_set` consumes an iterable and retains only a bounded ranked packet; it does not materialize the full input history.
- Packet status distinguishes `SOURCE_INCOMPLETE` from `BUDGET_EXHAUSTED`; the two conditions can also be reported simultaneously.
- Ranking scores have an explicit `trlw-ranking` semantic and are not conflated with extractor confidence, truth probability, or SROK priority.
- The byte budget applies to canonical serialized record bytes, **not** Python heap/RSS. Runtime memory still requires separate measurement.

The Yixiang adapter now also accepts a completed TRLW `MemoryPacket` through `compose_trlw_grounded_yixiang_hypotheses`. It uses only the bounded packet entries, requires the relation candidate and all role targets to be present, and carries packet status/source-completeness/budget-exhaustion into the result. A truncated packet may still produce hypotheses, but the result explicitly sets `search_exhaustive=False`; it never claims to have searched the complete durable history.

The new `coordinate_trlw_grounded_yixiang_csg_gcr` entry point composes the bounded packet through explicit XSL role transformation, bounded SROK assignment search, and typed CSG-GCR coordination. It returns the packet completeness metadata beside the typed proposals. Every proposal remains `HYPOTHESIS_ONLY`; this function does not consume an E09 verification receipt and never advances E12-A6 lifecycle.

This PR branch still does not itself contain the persistent ZPCM candidate store. The persistent candidate iterator is being developed separately in PR #273; once both branches are integrated, it can feed TRLW and then this packet adapter without materializing full history.

## Not implemented

- Raw M1 EvidenceChunk paging and byte-span verification in this adapter.
- OCR/parser execution and semantic candidate extraction.
- Entity resolution, conflict adjudication, assertion/relation materialization.
- Persistent SemanticUnitCandidate append/revision/retraction adapter.
- A keyset-paginated ZPCM semantic-candidate reader feeding TRLW.
- Full observation-to-E09 event orchestration.
- Production registry, identity, and policy deployment.

## Acceptance

The unit tests verify scope and grounding gates, relation role ordering, M1/E09/XSL provenance separation, hypothesis-only output, and the bounded TRLW packet contract. The repository CI must pass on the exact PR head before this slice is considered validated.

Research/security branches now run the full repository validation workflow on push via `.github/workflows/research-branch-validation.yml`.
