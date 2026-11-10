# E12-A3-M1 UCB Allocator — Independent Static Audit

Date: 2026-11-11  
Audit target: `research/e12a3-m1-ucb-allocator-2026-11-11`  
Audited files: `prototype/e12a3_adaptive_allocator.py`, `tests/test_e12a3_adaptive_allocator.py`  
Status: static review only; no test execution or CI result is claimed.

## Executive finding

The implementation is a useful deterministic **allocation-policy component**, but it is not yet an adaptive proposer benchmark. Its tests replay synthetic, pre-generated reward streams. They establish state-machine and budget invariants for the allocator, not that UCB improves primitive discovery, proposal coverage, generalization, or compute efficiency.

Keep the component research-only. Do not interpret the unit-test pass (if/when obtained) as evidence that adaptive allocation beats equal allocation or a specialist.

## Findings

### F1 — High: replay harness is not an integrated proposer experiment

`replay_ucb1()` selects from per-family reward sequences supplied in advance. The allocator does not call proposer implementations, inspect candidate envelopes, canonicalize proposals, measure candidate execution, compute incremental portfolio utility, or evaluate a held-out task.

The reward sequence is effectively an oracle fixture indexed by the family selected. This is suitable for deterministic policy tests, but it cannot establish that real proposer families produce the assumed reward process.

**Required next step:** build an episode runner that invokes actual proposers under the same Support snapshot, canonicalizes candidates, charges proposal and evaluation costs, computes the preregistered Gate-Dev incremental portfolio reward, and records the complete trace.

### F2 — High: the reward contract is underspecified for portfolio competition

The code accepts any finite reward in [0, 1]. It does not define the transformation from raw Gate-Dev utility to this interval, nor enforce that reward means *incremental portfolio improvement* rather than absolute candidate score.

This distinction matters: a family that repeatedly rediscovers an existing best candidate must not receive repeated credit. Negative regressions also need a declared mapping rather than being silently clipped or shifted after observing results.

**Required next step:** freeze a reward adapter with an explicit formula, normalization constants fixed on development worlds, duplicate-credit handling, and tests for zero gain, negative gain, repeated rediscovery, and cost penalties.

### F3 — High: batch budget is not yet compute-matched budget

The allocator counts one call to `next_family()` as one unit. The docstring describes that unit as a fixed-size proposal batch, but the allocator API does not carry batch size, proposal count, measured operations, evaluation cost, or wall-clock cost.

Two proposer families can therefore consume the same number of allocation units while doing very different amounts of work. This repeats a known limitation of M0, where proposal slots were matched but CPU operations and wall-clock costs were not.

**Required next step:** make each allocation event reference a batch manifest with declared proposal slots, measured evaluation operations, and elapsed time. Report both slot-matched and compute-matched comparisons.

### F4 — Medium: UCB1 stationarity assumptions do not match the intended reward process

Portfolio-incremental rewards are dependent on the current candidate registry and can shrink as useful candidates are discovered. Reward distributions are therefore non-stationary and cross-family dependent. The repository protocol already acknowledges that textbook stationary-bandit regret bounds do not apply.

The current UCB1 implementation can still serve as a heuristic baseline, but should not be presented as a theoretically justified optimal allocator.

**Required next step:** retain UCB1 as one control and compare it with equal allocation, round-robin, successive halving/racing, and a small-instance exact allocation oracle. Include order sensitivity, duplicated proposers, reward drift, and early-noise collapse conditions.

### F5 — Medium: validation behavior is inconsistent across allocation controls

`UCB1Allocator` rejects duplicate family names, but `allocate_equal_budget` silently deduplicates them with `set()`. The two controls can therefore interpret the same malformed family list differently. Both paths also need explicit validation of family element types and non-empty names before sorting/deduplication.

For example, mixed incomparable values may fail during `sorted(set(families))` with an incidental Python `TypeError`, rather than the documented input-contract error.

**Required next step:** share one family-list validator across all allocator policies; add duplicate, blank, non-string, mixed-type, and generator-input tests.

### F6 — Medium: evidence IDs provide trace uniqueness, not evidence provenance

The allocator checks that `evidence_id` is a unique non-empty string. It cannot establish that the ID refers to a Gate-Dev observation, that the observation belongs to the correct episode/split, or that Gate-Final/Locked-Test data did not influence the supplied reward.

The module boundary is useful because it has no Gate-Final or Locked-Test arguments, but the full pipeline still needs a versioned evidence ledger and mutation-invariance tests.

**Required next step:** bind each reward to an immutable Gate-Dev evidence record containing split role, episode ID, candidate-registry snapshot, scoring version, and source observation IDs. Reject non-Gate-Dev evidence in the runner, not merely by convention.

## Required test additions

1. Shared family-name validation across UCB1 and equal-allocation controls.
2. Explicit reward-adapter tests: no improvement, negative delta, duplicate rediscovery, complexity penalty, evaluation-cost penalty.
3. Candidate-order and proposer-order invariance.
4. Duplicated proposer family test: duplicate outputs retain provenance but do not create extra utility.
5. Gate-Final mutation invariance: changing Gate-Final labels must not change allocation trace.
6. Locked-Test mutation invariance: changing Locked-Test labels must not change proposals, rewards, or allocation trace.
7. Exact budget conservation across proposal slots and measured evaluation operations.
8. A tiny-world exhaustive oracle comparison.
9. Reward drift and early-noise tests demonstrating whether the exploration floor prevents premature family collapse.
10. An integrated two-task smoke test using actual proposer implementations rather than synthetic reward streams.

## Recommended experiment sequence

- **M1-P0:** close the input-contract and reward-adapter gaps; keep the current allocator unchanged as a baseline.
- **M1-P1:** connect real proposer batches and canonical candidate registry; enforce four-way Support / Gate-Dev / Gate-Final / Locked-Test separation.
- **M1-P2:** run slot-matched and measured-compute-matched comparisons over at least 20 independent world seeds per task family.
- **M1-P3:** add noisy, correlated-distractor, sparse-composition, held-out relation-family, and DSL-misspecification tasks.
- **M1-P4:** only after generic allocator results are stable, test Yijing-inspired priors as isolated proposal-distribution ablations with capacity-matched generic and shuffled controls.

## Decision

**Accept as a policy-test prototype; reject any claim of empirical allocator superiority at this stage.** The next evidence-bearing milestone is an integrated, compute-accounted benchmark with an evaluator firewall—not more replay fixtures.

No source code was changed by this audit. No benchmark was run. No changes were made to `main`.
