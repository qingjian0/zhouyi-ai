# E10-A Mechanism Controls and Revision Semantics (2026-11-11)

## Important correction

The first learner draft appended Query evidence and re-ran induction over the entire evidence history. That is cumulative batch refitting, not an incremental algorithm. This branch changes the online arm to true candidate elimination: after each reveal it filters the current candidate set using only the newly revealed observation. It cannot invent candidates outside the Support-induced hypothesis set.

## Three comparison arms

- Frozen: predict every Query row from the initial Support hypothesis set; never revise.
- Online candidate elimination: after each prediction and reveal, filter the current candidates using only that one new labelled row.
- Batch refit: after each reveal, reconstruct the candidate set from Support plus all Query evidence revealed so far.

All arms see the same Query object table, row order, and prediction opportunities. The harness obtains the evaluator target only after all three predictions for the current row have been produced. This is a trusted-process experiment harness, not a security boundary.

## Metrics

Report decided count, abstention count, coverage, accuracy conditional on decisions, accuracy with abstentions scored wrong, candidate count/hash trajectory, online revision count, and batch-refit count.

## Benchmark validity warning

The current A-O generator uses the same finite relation mechanism and the same positive/context-negative/role-near-miss construction in Support and Query, changing object identities rather than the task's structural challenge. Therefore, identical performance across frozen/online/batch arms would not establish that revision is unnecessary. A stronger revision benchmark must hold out a discriminating context combination, role-value composition, relation family, or controlled mechanism change while preserving enough Support evidence to make the task identifiable.

## Validation status

Tests are authored. No local execution or CI pass is claimed. GitHub workflow lookup for the initial learner PR returned no PR-triggered runs at that head SHA.
