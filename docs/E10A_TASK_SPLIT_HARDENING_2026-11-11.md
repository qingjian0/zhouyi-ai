# E10-A Task Split Hardening (2026-11-11)

Status: implementation follow-up to PR #37 and independent static review PR #38.
Branch: `research/e10a-task-split-hardening-2026-11-11`.
Base: `research/e10a-support-query-boundary-2026-11-10`.

## Motivation

PR #38's static review identified two concrete weaknesses in the original support/query adapter:

1. Query-group selection consulted evaluator labels to preserve both classes in Support. This made Query selection label-aware and means query metrics cannot be treated as an unconditional random-sample estimate.
2. The adapter built evaluator lookup with a dictionary comprehension before checking duplicate IDs, coerced labels with `bool(...)`, and did not fully validate schema, participants, or learner/evaluator label consistency.

This branch addresses those two implementation issues without modifying PR #37 or PR #38.

## Changes

- Query groups are now selected by a seeded uniform shuffle over structural group keys only. Evaluator labels do not participate in group assignment.
- Support is no longer guaranteed to contain both classes. The manifest reports observed support label counts; a downstream learner/benchmark must handle one-class support explicitly rather than changing the split after seeing labels.
- Evaluator query-label counts are recorded under an explicitly evaluator-only manifest field for diagnostics, not exposed in the learner query view.
- Duplicate evaluator observation IDs are rejected before lookup construction.
- Learner outcomes and evaluator validity values must be exact booleans; truthy integers/strings are rejected.
- Learner/evaluator labels must agree for every observation.
- Unknown schema/generator versions, malformed objects/participants/context, duplicate participants, unknown object references, and invalid seed/fraction types fail closed.
- Query rows remain explicit-allowlist payloads without outcomes or evaluator fields.

## Tests authored

The test suite now includes:
- query-label mutation invariance of query assignment;
- duplicate evaluator ID rejection;
- exact-boolean validation;
- learner/evaluator label consistency;
- unknown schema rejection;
- duplicate participant rejection;
- deterministic split and manifest policy;
- support/query group and observation partition invariants.

These tests are authored but have not yet been executed in a local checkout. A GitHub Actions result for the exact branch head is required before claiming validation.

## Statistical interpretation

The old label-aware selection policy was conditional on evaluator labels. The new policy removes that direct selection dependence, but it does not solve all benchmark sampling issues:

- participant groups within an episode are not independent in general;
- objects may overlap between Support and Query;
- participant sets can partially overlap;
- object attributes and repeated structural patterns can leak role information;
- the generator is synthetic and has a narrow finite template family.

Therefore this is only a more defensible episode-local group split. It is not object-disjoint generalization, cross-episode transfer, relation-family OOD, or open-world discovery.

A one-class Support episode is retained and reported, not silently discarded. Benchmark metrics must report its frequency and specify whether the learner abstains, uses a prior, or fails to fit.

## Next gates

1. Execute the exact unit tests and full CI for this branch.
2. Add an isolated runner that serializes only Support and Query to the learner process.
3. Add object-disjoint and participant-overlap-controlled splits.
4. Add a finite-hypothesis identifiability oracle; ambiguous support must permit calibrated ABSTAIN.
5. Compare label-blind group splitting against explicit sampling alternatives with per-class inclusion rates and seed-block uncertainty.
6. Only after these gates, add a transparent baseline learner.

No relation learner, empirical performance, or autonomous-discovery claim is included.
