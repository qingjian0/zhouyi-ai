# E12-A3-M0 Implementation Record

Date: 2026-11-11  
Status: first executable baseline; unit tests and CI pending at time of writing  
Branch: research/e12a3-proposer-competition-2026-11-11

## Delivered

- `prototype/e12a3_multi_proposer.py`
- `tests/test_e12a3_multi_proposer.py`

The baseline contains four transparent proposal paths:

1. STAT: typed threshold/equality/parity candidates for numeric features and equality candidates for categorical features.
2. RELATIONAL: numeric pairwise difference thresholds and categorical equality relations.
3. RANDOM: seeded grammar-valid exploration.
4. EXHAUSTIVE: bounded enumeration over the current finite proposal grammar.

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
