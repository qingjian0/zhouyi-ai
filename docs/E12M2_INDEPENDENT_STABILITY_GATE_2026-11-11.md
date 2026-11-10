# E12-M2.4: Independent Motif Stability Gate

## Change

The existing E12-M2 miner proposes motifs from one unlabeled observation partition using support and independence lift. This increment adds a separate validation partition that can retain or reject those proposals.

The API is intentionally one-way:

- Proposal observations are passed to `discover_motifs`.
- Validation observations are used only to measure the already-proposed candidates.
- A motif found only in validation data is never added to the proposal pool.
- Results are labeled `STABLE_MOTIF` or `REJECTED`, not "concept".

## Why this matters

A candidate selected and evaluated on the same observations is optimistically biased. Independent recurrence is a minimal check against sample-specific co-occurrence. It is not a complete statistical test and does not establish semantic unity.

## Current gate

For each proposal, the validator reports count, support, and lift in the independent partition. It requires configurable minimum validation count, support, and lift. Empty validation data rejects every candidate.

## Explicit limitations

- The gate does not compute permutation p-values or family-wise error correction.
- It does not correct for the fact that many candidates were searched on the proposal partition.
- It does not establish causal, semantic, or cross-environment stability.
- A random object split from one generator family is weaker than source-group, environment, and generator-family separation.
- It does not infer concept count or perform candidate-to-concept assignment.
- `STABLE_MOTIF` means only "the pre-proposed co-occurrence recurred under the declared independent validation threshold."

The conditional degree-preserving null and its calibration remain separate E12-M2 components. The stability gate must not be substituted for those tests.

## Regression coverage

- Recurrent proposal retained on independent observations.
- Proposal that does not recur is rejected.
- Validation-only pattern cannot enter the proposal pool.
- Empty validation partition rejects all proposals.
- Parameter validation.
- Input-order invariance.

## Next required tests

1. Source-group-disjoint validation.
2. Environment-disjoint validation with nuisance reversal.
3. Generator-family-disjoint transfer.
4. Threshold sensitivity and multi-seed calibration.
5. Candidate-family correction / max-statistic integration.
6. Matched-budget comparison against random proposals.

No empirical performance or autonomous concept-discovery claim is made.
