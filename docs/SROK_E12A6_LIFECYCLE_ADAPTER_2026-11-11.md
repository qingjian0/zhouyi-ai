# SROK → E12-A6 lifecycle adapter

日期：2026-11-11  
状态：P1 integration slice; lifecycle ownership remains with E12-A6.

## Responsibility

SROK proposes a typed multi-role composition. This adapter converts that immutable composition into an E12-A6 native Candidate in the initial OBSERVED state, then projects it through the existing read-only E12-A6 → CPG-EI adapter.

The adapter does not introduce another lifecycle enum, state machine, evidence ledger or persistent store.

## Semantic mapping

- relation type → native Candidate.operator;
- ordered role bindings → canonical expression and input type sequence;
- member node types → native Candidate.input_types;
- source evidence IDs → native Candidate.evidence_ids and sorted shared evidence refs;
- stable semantic digest → candidate ID and shared definition digest;
- raw SROK score → separate uncalibrated ranking metadata only;
- uncertainty → fixed conservative 1.0 until an independent calibration protocol exists;
- initial state → OBSERVED; LifecycleLedger and an explicit PROPOSE action own subsequent transitions.

The raw score is deliberately excluded from the semantic definition digest. Changing a ranking score must not create a new semantic candidate version.

## Boundaries

- This adapter does not authenticate evidence IDs or insert evidence into the lifecycle ledger.
- The caller must resolve member IDs to the exact SROK nodes used to produce the candidate.
- Search completeness must account for both role-pool truncation and expansion-budget exhaustion.
- E09 prediction commit/reveal and learner update remain a separate integration task.
- No model capability or calibration claim follows from this DTO mapping.

## Validation

Tests cover deterministic projection, evidence canonicalization, raw-score semantics, stable identity, invalid bindings, and an actual OBSERVED → PROPOSED transition through the existing E12-A6 LifecycleLedger.
