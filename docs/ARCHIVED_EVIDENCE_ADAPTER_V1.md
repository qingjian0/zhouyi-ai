# Archived Evidence Adapter v1

Status: implemented as a strict structural/provenance gate; end-to-end integration with real experiment producers remains pending.

## Contract

Use `evaluate_archived_evidence(archive_path, expected_task_set_digest, predicted_direction, min_seeds)` only after a benchmark report has been archived with the experiment archive module.

The archived report must contain a non-empty `evidence_rows` array. Each row contains the evaluator fields plus:

- `task_ids`: unique task IDs contributing to this comparison; task IDs cannot be reused by another evidence row in the same report.
- `expected_seeds` and `observed_seeds`: explicit seed manifests; observed seeds must be a subset of expected seeds and their count must equal `seeds`.
- `metric` and `metric_direction`: named metric and declared direction, which must agree with the hypothesis direction.
- `split_source`: provenance label; OOD rows must identify an OOD source.
- `control_family`: must match `shuffled` or `random` when that control is claimed.

The adapter verifies the archive schema, canonical report digest, and expected task-set digest before evaluation. It rejects missing provenance, duplicate task IDs, unexpected seeds, seed-count mismatch, metric-direction mismatch, and unsubstantiated OOD labels.

## Critical boundary

This adapter verifies structural consistency, not the truth of producer-supplied labels. It does not inspect raw predictions, dataset split files, per-seed metrics, or whether controls are actually parameter/compute matched. A trustworthy producer must derive evidence rows from raw task outputs and immutable experiment manifests. Do not hand-author evidence rows after seeing outcomes and treat them as independent evidence.

## Next step

Implement a producer that joins the archived benchmark's per-task outputs to the original experiment matrix manifest, computes paired per-seed effect sizes and confidence intervals using a preregistered metric definition, and emits these rows. Only then can the research loop consume real experimental evidence.
