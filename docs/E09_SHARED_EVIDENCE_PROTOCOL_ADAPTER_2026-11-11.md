# E09 Shared Evidence Protocol Adapter (2026-11-11)

## Status

Research integration slice on an isolated branch. The adapter connects the existing E09 prequential runner and both revision arms to the SQLite shared evidence protocol v0.2. It is not yet CI-validated, crash-resumable, or a process security boundary.

## Integration

- `E09SharedProtocolAdapter` persists the E09 learner track as `e09`.
- `BATCH_REFIT` and `INCREMENTAL_INDEX` remain separate learning arms. The adapter records the selected arm in prediction and structure metadata; it does not relabel batch refitting as incremental learning.
- The initial bootstrapped model is recorded as an initial `StructureVersion` with a snapshot digest. Bootstrap examples are explicitly pre-episode training evidence and are not represented as post-prediction reveals.
- For each query observation, the adapter records an opaque input digest, obtains the E09 prediction, durably commits it, and only then exposes the reveal method.
- A reveal is durably appended before it is added to the E09 evidence ledger.
- A revision creates a new immutable structure version with a parent pointer and the reveal event as support evidence, followed by a revision event.

## Required causal sequence

`initial_structure -> observation -> prediction_commit -> evidence_reveal -> structure_version -> revision`

## Important failure semantics

The existing E09 runner keeps in-memory state. The adapter therefore fails closed if a persistence or learner operation fails after a partial step. It does not attempt to continue with potentially divergent in-memory and durable state. A future version must implement transaction/outbox coordination or reconstruct runner state from the event log before claiming crash recovery.

The adapter currently accepts only a fresh episode. Replay is available for audit, but reconstructing a live E09 runner from persisted events is not implemented.

## Validation

Run:

```bash
python -m unittest tests.test_shared_evidence_protocol tests.test_e09_shared_protocol_adapter tests.test_e09_incremental_prequential tests.test_e09_prequential -v
```

Tests cover both E09 update arms, durable prediction-before-reveal ordering, structure lineage, reveal support references, and recorded update-cost counters. The full GitHub Actions workflow passed on code head `56073a63e38ad579d2cf0fd87afc72c1246ff26b` (Run #42892825395); all 109 unit tests and configured E01/E02 workflow steps succeeded. The later documentation-only update does not change executable code.

## Non-claims

- No claim of general online learning beyond the bounded `INCREMENTAL_INDEX` update rule already implemented in E09.
- No process isolation between evaluator and learner.
- No authenticated learner-track identity.
- No crash-safe resume or distributed transactions.
- No performance superiority claim versus `BATCH_REFIT`; equal-budget benchmark work remains separate.
