# M2 Observation-to-Candidate Pipeline v1

## Purpose

This adapter connects the persisted M2 Observation stream to the persistent
SemanticUnitCandidate stream. It provides the missing orchestration boundary
between source-grounded observation and downstream candidate extraction.

## Authoritative input check

A caller-supplied receipt is not trusted on its own. Before invoking the
extractor, the pipeline re-reads the Observation and its receipt from the
authoritative `PersistentM2ObservationStore`. It requires exact record
equality and matches the immutable event ID, sequence, payload digest, and
record digest. A fabricated receipt, unpersisted Observation, or modified
record is rejected before extraction.

## Candidate contract

- The extractor is injected; this package does not claim to include a semantic
  parser or trained model.
- Candidate scope and immutable M1 source references must exactly match the
  Observation.
- Candidate derivation references must cite
  `m2:observation:<observation_record_id>`.
- Candidate IDs must be unique within the batch.
- Output count is bounded before persistence.
- Extraction must leave grounding as `UNRESOLVED` and truth as `UNKNOWN`.
  Grounding, verification, and truth adjudication remain separate stages.
- `PARTIAL` observations are marked in the batch receipt; `UNPARSEABLE` and
  `REJECTED` observations are not extractable.

The complete batch is validated before its first write. Candidate events are
still appended individually by ZPCM; a process or storage failure during the
append loop can leave a durable prefix. Stable candidate IDs and content make
such retries idempotent; a changed payload under an existing ID is rejected.

## Validation boundary

Tests cover forged/missing persisted receipts, altered observations, scope and
derivation provenance, grounding/truth escalation, duplicate IDs, output
limits, partial/unparseable observations, and a real SQLite M1 -> M2 ->
candidate-store round trip.

This validates persistence orchestration and provenance enforcement only. It
does not establish extraction precision/recall, semantic correctness,
calibration, or out-of-domain generalization. A model-backed extractor must
pass independently annotated, source-licensed multi-domain evaluations before
being treated as a production perception component.
