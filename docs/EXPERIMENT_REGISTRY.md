# Experiment Registry (P1.5)

## Purpose

P1.5 adds reproducible experiment registration and result provenance. It is a
metadata registry, **not an experiment runner**: it does not launch training,
evaluate models, allocate GPUs, fetch datasets, or execute arbitrary commands.

## Experiment specification

Each immutable `ExperimentSpec` pins:

- Hypothesis and method identifier.
- Model ID and model version.
- Dataset ID, version, and SHA-256 content digest.
- Git code revision (7–64 hexadecimal characters).
- Random seed.
- Environment metadata (runtime, platform, hardware, dependency versions).
- Explicit resource budget (for example steps, examples, wall-clock seconds,
  accelerator-hours); all values must be positive finite numbers.
- Timezone-aware creation timestamp.
- Optional baseline ID, comparison group, and method-specific configuration.

Use a distinct experiment ID for every seed/repetition. Keep baseline and candidate
runs in the same comparison group and align their dataset, evaluation protocol,
and resource budget before interpreting differences.

## Results and provenance

An `ExperimentResult` records terminal status, finite numeric metrics, references
to stored artifacts, evidence references, blockers, and a timezone-aware completion
timestamp. Results are linked to an existing spec and can be recorded only once.
Both spec and result payloads have SHA-256 integrity digests.

The registry uses SQLite transactions and a uniqueness constraint to prevent
duplicate experiment IDs and duplicate result publication. It is a local,
single-host metadata store. Back up the database and artifact store together.

## Statistical protocol

The registry records seeds and comparison groups but does not calculate statistical
significance. For claims about architecture improvements:

1. Pre-register baseline and candidate specs before execution.
2. Use identical dataset snapshots, train/evaluation splits, and metric definitions.
3. Match compute budgets; report actual consumed compute in result metrics.
4. Run multiple independent seeds; do not select only the best seed.
5. Report mean, standard deviation, confidence intervals, and effect size outside
   the registry or in a versioned analysis artifact.
6. Separate in-distribution, compositional OOD, rule-family OOD, and long-context
   evaluations. Record failures and incomplete runs rather than silently dropping them.

## Integrity and security boundaries

Digests detect accidental modification; they are not signatures and do not prove
author identity. The registry has no user authentication, encryption-at-rest,
multi-tenant isolation, remote replication, retention policy, or garbage collection.
Do not store credentials, private chain-of-thought, or raw sensitive data here.
The registry does not establish that a declared model, dataset, environment, or
budget was actually used; execution attestation belongs to a future controlled
runner and trusted provenance layer.

## Acceptance

- Specs reject missing provenance, invalid commit/dataset digests, naive timestamps,
  invalid seeds, non-finite budgets, and non-JSON configuration.
- Duplicate IDs cannot overwrite prior specs.
- Results require a registered spec and cannot overwrite a prior result.
- Spec/result integrity is checked on read.
- Round-trip, validation, and append-only behavior are covered by unit tests.
