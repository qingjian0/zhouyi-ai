# E12-A3-M0 Implementation Record

Date: 2026-11-11  
Status: executable baseline; full repository CI and the exact-budget 20-seed benchmark passed on commit `55cd2ca7fc4d72e729df83fc3003398c09295be1`  
Branch: research/e12a3-proposer-competition-2026-11-11

## Delivered

- `prototype/e12a3_multi_proposer.py`
- `tests/test_e12a3_multi_proposer.py`

The baseline contains four transparent proposal paths:

1. STAT: typed threshold/equality/parity candidates for numeric features and equality candidates for categorical features.
2. RELATIONAL: numeric pairwise difference thresholds and categorical equality relations.
3. RANDOM: seeded grammar-valid exploration.
4. BOUNDED_ENUM: bounded enumeration over the current finite proposal grammar, used as a separate control rather than a member of the portfolio.

Shared infrastructure includes:
- immutable observation, expression, proposal, signature, allocation, and lifecycle-event records;
- schema validation and homogeneous feature-type checks;
- canonical expression serialization;
- dataset-scoped empirical behavior signatures;
- equal budget allocation and deterministic round-robin scheduling;
- separate Gate evaluation;
- guarded lifecycle transitions;
- deterministic synthetic smoke-test output.

## Important limitations

This is a minimal proposal-portfolio baseline, not yet the complete E12-A3 architecture.

- Proposal grammar is finite and hand-specified.
- STAT and RELATIONAL are data-grounded but do not yet use labels to optimize proposals.
- The current scheduler counts proposal slots, not measured CPU operations or wall-clock cost.
- Gate scoring reports accuracy only; it does not yet enforce a Support -> Gate -> Locked Test acceptance protocol.
- Lifecycle events are validated but not yet persisted in an append-only registry.
- There is no process-level evaluator/learner isolation yet.
- The demo is a smoke test, not a benchmark or evidence of superiority.

## Test coverage

The test suite checks deterministic proposals, relational candidate generation, seeded random reproducibility, bounded enumeration, budget conservation, round-robin fairness, dataset-scoped equivalence, Gate separation, schema/type rejection, lifecycle transition guards, and smoke-test labeling.

## Next gates

1. Run all repository unit tests and the new E12-A3 tests in CI.
2. Add tiny hand-computable worlds with known useful and spurious primitives.
3. Add Support screening, Locked Test isolation, and append-only event persistence.
4. Measure operation costs and compare equal-budget proposer policies over independent seeds.
5. Add held-out world families and DSL-misspecification cases.
6. Only after generic baselines are stable, add Yijing-inspired proposal priors and capacity-matched controls.

No performance claim is made in this record.

## Validation update

Full repository GitHub Actions workflow passed on commit `08bed36bc844998fee28f8d7bbd5b634e0be657d`. This included the repository-wide unit-test step, E12-A3 unit tests, the A3 smoke test, benchmark tests, the 20-seed equal-proposal-slot benchmark, and all existing E01/E02 workflow steps.

After that successful run, additional strict validation was added for boolean labels, non-finite numeric values, and numeric predicate thresholds. The latest commits require a fresh full CI confirmation before being called green.

## Cross-family deduplication follow-up

A subsequent implementation added syntactic deduplication across STAT, RELATIONAL, and RANDOM while preserving all contributing proposer IDs in `supporting_families`. The full repository workflow passed on commit `1b22906652faf4c3279c5744a3617b6732b12997` (run `42871279195`).

The follow-up benchmark is recorded in `E12A3_M0_1_DEDUP_RESULTS_2026-11-11.md`. Portfolio coverage fell to 17.5%, confirming that deduplication must be coupled to an allocation policy that handles shared candidates without arbitrary family ownership.

## M1 allocator-core update

A stateful UCB1 allocator core is now available in `prototype/e12a3_adaptive_allocator.py`, with unit tests in `tests/test_e12a3_adaptive_allocator.py`. The A3-specific unit-test and benchmark steps passed in GitHub Actions run `42872397534`.

The allocator enforces an exploration floor, deterministic tie-breaking, budget conservation, and normalized finite rewards in [0, 1]. It is not yet connected to candidate generation or a four-way Support/Gate-Dev/Gate-Final/Locked-Test benchmark; no adaptive-allocation performance claim is made.
