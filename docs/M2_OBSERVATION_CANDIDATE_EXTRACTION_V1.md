# Observation → SemanticUnitCandidate extraction boundary v1

Status: executable orchestration contract; no production semantic model is included.

## Purpose

M2 persists typed Observations and SemanticUnitCandidates, but the safe handoff between them was not defined. This slice introduces an injected `SemanticUnitExtractor` protocol and a bounded persistence pipeline.

## Contract

- Input is one persisted M2 Observation plus the matching `ObservationReceipt`.
- The receipt event ID and canonical record digest must match the supplied Observation.
- The extractor is injected; implementations may later wrap a parser, model, human review, or a fusion stage.
- Candidate `source_refs` must exactly preserve the Observation's immutable M1 EvidenceRefs.
- Candidate `derivation_refs` must cite `m2:observation:<record_id>`.
- Scope must remain unchanged.
- Candidate IDs must be unique within the batch.
- A per-observation candidate cap bounds memory and output amplification.
- The entire bounded batch is validated before the first candidate append.
- A partial parse is allowed but explicitly marked in the batch receipt. Rejected and unparseable observations fail closed.
- Extraction cannot claim entity grounding or truth adjudication: output must remain `UNRESOLVED` and `UNKNOWN`. Grounding, E09 verification, and truth adjudication are separate stages.

## Failure semantics

Batch validation failures cause zero candidate writes. ZPCM appends each valid candidate as its own immutable event, so a process/database failure during the append loop can leave a durable prefix. Candidate IDs and content must therefore be stable across retries; the store's idempotency and immutable-ID conflict checks remain authoritative.

## Non-goals

This is not a semantic parser, entity linker, grounding service, truth adjudicator, or E09 verifier. A model-backed extractor must be evaluated separately for precision/recall, calibration, abstention, provenance preservation, adversarial inputs, and domain/OOD generalization. Fixture tests validate the orchestration contract only, not semantic quality.
