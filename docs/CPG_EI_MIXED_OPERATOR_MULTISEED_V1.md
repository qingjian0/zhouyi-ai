# Mixed-operator trainable baseline: independent-seed replication v1

## Purpose

The initial trainable polynomial baseline runs one eight-family corpus seed. This follow-up repeats the unchanged learner and optimizer configuration on a second independently generated corpus seed. Each seed creates new teacher families and new state partitions.

## Fixed protocol

- Two independent corpus seeds: 20261114 and 20261115.
- Eight teacher families per seed; eight Boolean inputs and eight outputs.
- 256 states per family, with disjoint 128/64/64 train/development/locked partitions.
- 120 epochs, learning rate 0.1, L2 0.0001.
- Each teacher family is fitted independently with the complete Boolean monomial basis.
- Locked states are evaluation-only and never select hyperparameters.

The combined benchmark contains 16 independently generated teacher families and 4,096 rows across the two corpora. This is twice the row count of the original eight-family, single-seed run, not a million-row or natural-language dataset.

## Reporting

The report contains per-seed development and locked metrics, corpus digests, mean and sample standard deviation across seeds, min/max, and whether training loss decreased for every family. The two-seed standard deviation is preliminary and must not be treated as a high-confidence estimate.

## Interpretation limits

This remains per-family supervised fitting on synthetic Boolean operators. It is not cross-family meta-learning, zero-shot transfer, open-world relation discovery, causal discovery, Yi-Xue reasoning, or natural-language reasoning. The model uses a fixed exhaustive feature basis; it does not learn that basis.

## Validation

The dedicated pull-request workflow runs the focused deterministic contract tests, the two-seed replication, and uploads the machine-readable report. No result is claimed until that exact-head workflow completes.
