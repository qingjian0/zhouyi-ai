# M55.1 repaired statistical study protocol v0.1

## Purpose

M55.1 reruns the synthetic target-parent benchmark after the independent audit of M55. It does not overwrite or reinterpret the historical M55 artifact. The old run remains preserved as a superseded diagnostic record.

## Repairs

### 1. Remove evaluator-derived sparsity

No candidate adapter receives `len(true_parents)` or any other evaluator-derived statistic. The random and correlation baselines are instantiated at fixed, preregistered cardinalities (k=1) and (k=2). These are explicit protocol variants, not estimates selected using ground truth. The PC-style baseline remains threshold-based and may return a variable-size set.

This does not make the baselines equally capable; it makes their information boundary explicit and removes the oracle leak. Results must be reported separately for each fixed-k variant.

### 2. Define sample size as training N

The CLI argument `--train-sample-sizes` means the number of observations available to candidate adapters. Validation and test observations are additional, disjoint units. Every raw record includes:

- `train_sample_size`;
- `validation_sample_size`;
- `test_sample_size`;
- `total_sample_size`.

The adapter receives only the training rows through the M54 contract.

### 3. Repair hidden-regime assignment

The mechanism-heterogeneity regime is sampled from a separate deterministic random stream, independent of unit order and identifier. Regime labels are retained only in evaluator metadata and are not included in agent-facing rows. This prevents deterministic recovery from row parity or `unit_id`.

### 4. Repair raw artifact format

Each serialized record is followed by a physical newline. A regression test parses the file line-by-line with the standard JSON parser and verifies the exact record count.

### 5. Clarify inference

Paired bootstrap intervals estimate uncertainty in the mean seed-level F1 difference. The sign-flip p-value is explicitly a sensitivity analysis and requires a justified exchangeability/symmetry assumption. Holm-adjusted values are labeled as sensitivity-only until the inferential assumptions are independently reviewed. No unqualified significance or superiority claim is permitted.

## Design

- 12 synthetic scenarios;
- 50 seeds (1000–1049);
- training sample sizes 120, 240, 480;
- five adapters: random-k1, correlation-k1, random-k2, correlation-k2, PC-style target skeleton;
- all methods share the same scenario/seed data and train/validation/test partition;
- evaluator truth is used only by the scoring harness after proposals are returned;
- hidden regime labels are stored outside agent-facing observations.

Expected raw record count:

[
12 	imes 3 	imes 50 	imes 5 = 9{,}000.
]

## Limitations

- Synthetic data only; no real-world causal identification is established.
- The PC-style comparator is target-local, linear-Gaussian, and does not orient edges or identify latent confounding.
- Fixed-k baselines intentionally expose a cardinality hyperparameter selected by protocol, not by oracle. Their limitations must be considered when comparing against a variable-cardinality method.
- No Transformer, general SCM learner, or actual Zhouyi agent is measured.
- A successful workflow validates execution and artifact creation, not theory validity or generalization.

## Acceptance

1. All M55.1 regression tests pass.
2. The full 9,000-record matrix completes.
3. Raw JSONL parses as exactly 9,000 physical lines.
4. Every record reports the actual training and total sample sizes.
5. No evaluator-truth field is present in agent-facing rows.
6. Hidden regimes are independent of unit order and remain evaluator-only.
7. Raw artifact, summary, and process resource report are retained.
8. The report includes scenario-stratified estimates and clearly labels sign-flip assumptions.

M55.1 is a repaired benchmark protocol, not evidence that a Zhouyi/Yixiang architecture is superior.
