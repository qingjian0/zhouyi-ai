# E10-A Support/Query Boundary v1

Status: prototype implementation. This document describes a task-view adapter
for generator v2; it does not claim a validated benchmark or learner result.

## Problem

Generator v2's `Episode.learner_view()` exposes outcomes for every generated
observation. That representation is useful as a complete labelled episode
fixture, but it cannot directly serve as a held-out prediction task: a learner
receiving the full view has already seen query labels.

## Adapter boundary

`prototype/e10a_task_split.py` accepts two separately serialized inputs:
- learner payload: `Episode.learner_view()`;
- evaluator payload: `Episode.audit_view()`.

It does not accept an Episode instance. It returns:
- `support`: labelled observations and visible object attributes;
- `query`: observations without outcome, violation, or template fields;
- `evaluator_truth`: query-only answers and evaluator metadata;
- `manifest`: deterministic split seed, counts, grouping policy and ID hashes.

The caller must keep `evaluator_truth` in a separate evaluator process or
capability boundary. Returning both payloads from one helper is a test/data
construction convenience, not a security boundary against a caller that has
access to the entire returned object.

## Leakage defense

Observations are grouped by
`(relation_symbol, unordered participant set)`. Thus the positive instance,
same-participant context-negative instance, and any duplicate-context records
cannot be split across support and query merely because their context or
observation IDs differ.

For each relation symbol:
- at least three distinct participant groups are required;
- support must retain at least one positive and one negative observation;
- at least one complete participant group is assigned to query.

The grouping prevents exact participant-set overlap. It does not prevent
near-duplicate attribute patterns, shared individual objects, or higher-order
structural leakage. Those require separate split policies and attacks.

## Explicit limitations

- This is an episode-local random group split, not an object-disjoint or
  relation-template OOD split.
- Query groups can share individual objects with support groups.
- It does not prove the latent template is identifiable from support.
- It does not implement a multi-hypothesis oracle, abstention scoring,
  four-axis OOD isolation, noise/missingness arms, or baselines.
- The adapter's evaluator payload must be physically isolated by the benchmark
  runner; Python dictionaries in one process are not an access-control system.
- The exact repository tests have not yet been executed in CI or a local
  checkout. No test pass is claimed.

## Acceptance tests authored

The test module checks:
- query labels and evaluator-only fields are absent from QueryView;
- participant-set groups do not cross partitions;
- support retains both label classes per relation;
- deterministic split output for a fixed seed;
- exact one-time assignment of every observation;
- fail-closed behavior for invalid split fractions and mismatched episode IDs.

Next gates: execute the exact tests, add serialization/process-boundary tests,
measure identifiability on the support-only view, and add object-disjoint plus
OOD split policies before training a learner.
