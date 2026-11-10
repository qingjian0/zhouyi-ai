# E10-A Phase-Gated Query Runner Prototype (2026-11-11)

## Status

Adds a sequential query-release gate over the A-O generator and append-only prequential ledger. This is a trusted-process protocol prototype. It is not a sandbox, subprocess boundary, or empirical learning result. Tests are authored but not executed; no CI pass is claimed.

## Flow

1. The learner receives Support (from the A-O task builder).
2. Evaluator gate releases one unlabeled Query observation and, on the first query only, the Query object table.
3. Learner commits a prediction or explicit abstention to the ledger.
4. Evaluator gate checks that the commit exists and matches the currently open observation.
5. Only then does the evaluator append/reveal the target label.
6. The next Query cannot be opened until the current Query has been revealed.
7. Repeat until all Query observations have been consumed.

## Files

- `prototype/e10a_phase_gate.py`
- `tests/test_e10a_phase_gate.py`

The existing ledger also gains a read-only lookup for a committed prediction by observation ID.

## Enforced gates

- No reveal when there is no open Query.
- No reveal without a prior committed prediction.
- No reveal if the prediction ID does not match the open Query's commit.
- No advancing to the next Query before revealing the current Query.
- Query labels are not included in released learner payloads.
- Query object table is sent once; subsequent releases contain only the next observation.
- Evaluator truth IDs must exactly cover Query observation IDs.
- Abstention commits unlock feedback just like ordinary predictions.

## Boundary and security caveat

All Python objects still execute in one trusted process in this prototype. A caller with access to the evaluator object or its memory can inspect hidden truth. Production use requires the evaluator gate to run in a separate process/service, with the learner receiving only serialized messages over a narrow interface. The ledger must be durably persisted before the evaluator accepts a reveal request.

This prototype enforces temporal protocol order at the API level; it does not prove hostile-process isolation.

## Next gates

- Move evaluator truth and gate into a separate process with filesystem/IPC permissions that deny learner access.
- Add durable append-only persistence and crash recovery.
- Add a learner that proposes and revises an actual relation mechanism.
- Measure pre-reveal prediction, post-reveal recovery, revision stability, and marginal update cost.
- Compare incremental revision with frozen and full batch-refit controls at equal total compute.
