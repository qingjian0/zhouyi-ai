# Raw Experiment Analyzer v1

## Purpose

Turn per-task, multi-dimension evaluation observations into auditable, paired evidence rows. This is
separate from the serial/parallel benchmark: throughput measurements are not
scientific outcome metrics.

## Input contract

Call `analyze_raw_observations(observations, task_manifest=..., ...)`.

The authoritative task manifest is derived from `ExperimentMatrix.to_tasks()`
with `task_manifest_from_specs(tasks)`, which extracts one record per task. This helper accepts the TaskSpec objects returned directly by `ExperimentMatrix.to_tasks()`:

- `task_id`, `track`, `condition`, `seed`

Each observation must provide:

- unique `observation_id`, `task_id`, `split` (`iid` or `ood`), `control`
  (`none`, `shuffled`, `random`), `metric`, `metric_value`
- `status`, `preregistered`, `parameter_count`, `compute_budget`
- `split_source`, `control_family`

The task identity fields are joined from the manifest, not trusted from the
observation payload. A task may emit multiple observations (for example IID
and OOD evaluations, or distinct control families). Each observation ID must
be unique, and each task/split/control tuple may appear only once per metric.

## Pairing and estimand

Treatment and baseline are paired only when track, seed, split, control,
parameter count and compute budget match exactly. No interpolation or
imputation is performed. Failed, missing, non-contrast and unmatched tasks
are recorded as exclusions or missing IDs.

The reported effect always preserves the conventional raw estimand:
`treatment metric - baseline metric`. It is never sign-flipped.

- higher-is-better: a positive effect is desirable
- lower-is-better: a negative effect is desirable

The raw metric polarity (`metric_direction`) describes desirability; the
hypothesis effect direction (`effect_direction`) describes the predicted
numeric sign of treatment-minus-baseline. The evidence evaluator consumes the
latter. A hypothesis predicting improved latency should therefore predict a
negative effect, not a positive one.

## Statistics

The analyzer computes a two-sided paired Student-t confidence interval on
per-seed differences. The critical value is obtained from the regularized
incomplete beta function and numerical inversion, not a normal approximation.
The default interval is 95%; the default evidence minimum is 10 paired seeds.

This method assumes independent, approximately normal paired differences.
Inspect raw distributions and outliers; for small samples the interval may be
unstable. This implementation does not perform multiplicity correction,
power analysis, hierarchical/mixed-effects modelling, or preregistration
auditing.

## Output and archive

The result contains `task_set_digest`, an input-observation digest, unique task
and observation counts, missing task IDs, exclusions, and `evidence_rows`.
Each evidence row carries both task IDs and observation IDs for provenance. The result can be passed to
`archive_benchmark_report` as an immutable analysis report, with the matrix
digest as the task-set digest. Preserve the original benchmark archive; store
this analysis as a distinct run ID.

The archived evidence adapter validates provenance shape and digests. It does
not prove that producer-supplied split labels, budgets, or preregistration
claims are truthful. Retain source observations and raw run logs for audit.

## Deliberate limitations

- No raw observation is fabricated from benchmark summaries.
- No task is silently dropped: missing and excluded IDs are surfaced.
- Only exact budget/parameter-matched pairs contribute.
- A favorable interval is not by itself proof of a theory.
- A complete research decision still needs preregistration, multiple-testing
  control, power analysis, replication, and expert review.


## Sign convention

Every effect is computed as treatment minus baseline. `metric_direction` indicates whether higher or lower values are desirable; it never changes the numeric sign. Hypotheses must predict the raw numeric direction.
