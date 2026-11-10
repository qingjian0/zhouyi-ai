# E10-A Generator-First Object-Disjoint Prototype (2026-11-11)

## Scope

This branch adds an executable first prototype of A-O known-mechanism/unseen-object transfer. It is deliberately separate from the existing v2 episode/task splitter and does not change their behavior.

## Implementation

Files:
- `prototype/e10a_object_disjoint.py`
- `tests/test_e10a_object_disjoint.py`

`build_object_disjoint_task(seed, instances_per_template=6)` returns three separate serializable values:
1. Support learner payload: Support object table and labeled Support observations.
2. Query learner payload: independently generated Query object table and unlabeled Query observations.
3. Evaluator truth: shared mechanism specification, role mappings, source-group provenance, and labels.

The latent mechanism is sampled once. Its hash is shared by Support, Query, and evaluator truth. The temporary objects created by the mechanism sampler are discarded. Support and Query object pools are independently synthesized from split-specific deterministic RNG streams derived from the root seed.

Each pool independently provides every required role value and one nuisance value per template. No object record is copied across pools. Observations are instantiated only from their own pool. Query labels and evaluator annotations are removed from the Query learner payload.

## Acceptance checks authored

- Support/Query object-table identity intersection is empty.
- Every observation participant belongs to the correct pool.
- Same mechanism hash across both phases.
- Query IDs and full object records absent from Support serialization.
- Query observations omit labels, validity, violation, role map, template ID, and source provenance.
- Source-instance variants remain grouped within each phase.
- Deterministic output for a fixed seed.
- Mechanism hash invariant to pool size (mechanism sampling is fixed independently of pool-size parameter).
- Evaluator-truth mutation does not mutate serialized learner payloads.
- Invalid arguments fail closed.

## Important limitations

This is a generator/data-contract prototype, not yet a benchmark runner or a security boundary.

- The function currently constructs and returns Support, Query, and evaluator truth in one Python process. A production runner must serialize and deliver Support first, then deliver Query only at prediction time, while keeping evaluator truth in a separate process/service. Returning three values is not physical process isolation.
- Query payload is constructed in memory at task creation; temporal withholding is a runner responsibility.
- The prototype's object records contain only the mechanism feature relevant to their template plus a nuisance value. It does not yet provide broad matched nuisance-attribute distributions or a full multi-feature object world.
- It reuses the existing finite categorical template family. It does not demonstrate new relation primitive invention, relation-family OOD, cross-world transfer, or open-world concept discovery.
- The learner algorithm, finite DSL Oracle, calibration, abstention, cost accounting, and multi-seed benchmark evaluation are not implemented here.

## Validation status

The source and tests have been committed and fetched back from GitHub for static inspection. Tests have not been executed in this environment; no CI run or empirical result is claimed.

## Next implementation gates

1. Run the full repository test suite and resolve failures.
2. Add a phase-gated runner that writes/opens only the Support payload during fitting and opens Query payload only after the learner emits predictions.
3. Move evaluator truth into an isolated process or service with a narrow scoring API.
4. Add recursive payload canaries and a deliberate shared-object negative control.
5. Add distribution/support-count reports and compare baselines under identical object pools and compute budgets.
