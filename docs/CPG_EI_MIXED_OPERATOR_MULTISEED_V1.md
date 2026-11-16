# Mixed-operator learner: five-seed replication and controls v3

## Purpose

The initial trainable polynomial baseline reports one eight-family corpus seed. This follow-up repeats the learner on two independently generated corpora and adds two controls to test whether its score reflects higher-order interactions rather than simple output imbalance or unary effects.

## Fixed protocol

- Five independent corpus seeds: 20261114–20261118.
- Eight teacher families per seed; eight Boolean inputs and eight outputs.
- 256 states per family, with disjoint 128/64/64 train/development/locked partitions.
- 120 epochs, learning rate 0.1, L2 0.0001.
- Full model: complete Boolean monomial basis, arity 1–8.
- Unary control: same learner and optimizer, but only arity-1 features.
- Majority control: per-output majority label estimated from that family's training partition; ties predict 0.
- Each teacher family is fitted independently. Locked states are evaluation-only and never select hyperparameters.

The combined benchmark contains 40 independent teacher families and 10,240 rows across five corpora, five times the row count of the original eight-family, single-seed run.

## Reporting

The report contains per-seed development and locked metrics, corpus digests, mean and sample standard deviation across seeds, min/max, and full-model-minus-control differences. Locked metrics and comparisons are report-only. Both trainable models report whether training loss decreased for every family.

## Interpretation limits

This remains per-family supervised fitting on synthetic Boolean operators. It is not cross-family meta-learning, zero-shot transfer, open-world relation discovery, causal discovery, Yi-Xue reasoning, or natural-language reasoning. The full model uses a fixed exhaustive feature basis; it does not learn that basis. Five seeds provide a more useful, though still limited, estimate of between-seed dispersion.

## Validation

The dedicated pull-request workflow runs deterministic contract tests, the two-seed replication and uploads a machine-readable report. No result is claimed until that exact-head workflow completes.
