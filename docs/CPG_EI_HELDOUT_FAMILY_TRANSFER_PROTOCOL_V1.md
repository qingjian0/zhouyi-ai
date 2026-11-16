# CPG-EI Held-Out-Family Few-Shot Transfer Protocol v1

## Research question

Can a learner trained on one set of teacher families adapt to entirely unseen
teacher families from a bounded support set and predict disjoint query states?

## Split semantics

The generator's family split is now used as an actual protocol boundary:

- family_split=train: meta-training episodes only.
- family_split=development: unseen validation families; labeled support is
  available for adaptation, query labels are evaluator-only.
- family_split=locked: unseen final-test families; labeled support is
  available for adaptation, query labels are evaluator-only.

No teacher family may occur in more than one group. Within every family, support
comes from state_split=train; validation queries come from
state_split=development; final test queries come from state_split=locked.

## Few-shot semantics

This is few-shot family transfer, not zero-shot transfer: the learner receives
a fixed number of labeled support states from each unseen family. The default is
16 support states, with 32 and 64 intended as follow-up conditions.

The protocol emits two files:

1. learner_view.json: meta-training episodes include train-family support and
   query labels. Validation/test episodes expose only support labels and query
   input states.
2. evaluator_view.json: validation/test query labels are stored separately.

This separation is an API-level leakage guard, not a process or security boundary.
The evaluator must remain outside the learner process for stronger isolation.

## Metrics required for a learner

- Query bit accuracy and exact-state accuracy by family split.
- Per-family median, lower quartile, and worst-family accuracy.
- Support-size curves at 16/32/64.
- Multi-seed mean and dispersion.
- Calibration and abstention where probabilities are emitted.
- Comparison with per-family-from-scratch adaptation and pooled-training baselines.

## Claim boundary

This PR defines data views and tests leakage invariants. It does not implement a
meta-learner, train a model, or demonstrate cross-family generalization. A later
algorithm PR must consume only learner_view and be evaluated against the
separate evaluator_view.
