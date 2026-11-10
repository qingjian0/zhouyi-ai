# E10-A Prequential Ledger Prototype (2026-11-11)

## Status

This branch adds a minimal append-only ledger primitive and invariant tests. It does not yet integrate a learner, evaluator process, benchmark runner, or online structure-induction algorithm. Tests are authored but have not been executed; no CI pass is claimed.

## Relationship to shared evidence contract

This is a narrow E10-A implementation slice of the shared protocol proposed in PR #53:

`predict -> commit_prediction -> reveal -> append_evidence -> revise`

It intentionally does not introduce a shared monolithic learner or force E02/E09/E11 to use E10's hypothesis representation.

## Files

- `prototype/e10a_prequential_ledger.py`
- `tests/test_e10a_prequential_ledger.py`

## Enforced invariants

1. A prediction commit is persisted before evidence reveal.
2. A reveal requires a matching prior prediction commit.
3. A prediction ID and observation can be revealed only once.
4. Prediction commits cannot be overwritten.
5. A revision can cite only evidence IDs already revealed in the ledger.
6. Abstention is a first-class committed decision.
7. Snapshots are detached copies; mutating a returned snapshot cannot mutate ledger history.
8. Each event receives a monotonic step and immutable event ID.
9. Compute-cost metadata is recorded with prediction and revision events.
10. Invalid decision states, confidence values, and malformed costs fail closed.

## Important boundary

The current implementation is a trusted-runner state machine, not a security boundary. It stores prediction commits and revealed evidence in one ledger object. A production deployment must split responsibilities:

- Evaluator process: owns hidden labels and source provenance; accepts a committed prediction ID; reveals only after validating the commit.
- Learner process: owns its candidate structures and learner-visible evidence; cannot read evaluator files, descriptors, or APIs.
- Runner: transports serialized messages, timestamps events, and preserves append-only audit artifacts.

The evaluator should not send hidden labels to the learner before a prediction commit is durably acknowledged. The learner must never receive locked-test labels during candidate selection.

## Not yet implemented

- StructureVersion registry with parent/child lineage and validity intervals.
- Revision impact checks and stale-version retirement.
- A learner that actually changes a relation mechanism after a counterexample.
- Query-phase gating integrated with the A-O object-disjoint generator.
- Separate evaluator service and learner subprocess.
- Hash-chained or signed ledger persistence.
- Marginal compute measurement and batch-refit comparison.
- Calibration, coverage-risk, and world-level confidence intervals.

## Next acceptance gate

Build a phase-gated A-O runner around this ledger:

1. Deliver Support payload to learner.
2. Learner emits candidate mechanism and commits a prediction for one Query observation.
3. Runner durably acknowledges the commit.
4. Evaluator reveals that observation's label.
5. Learner appends the reveal and either revises or explicitly keeps its structure.
6. Repeat sequentially; never reveal a later query before its own commit.
7. Compare incremental revision against frozen and full batch-refit controls under equal cumulative compute.

Only after this runner works should the project claim prequential evaluation. Only after a learner improves on the frozen and batch-refit controls should it claim an incremental-learning benefit.
