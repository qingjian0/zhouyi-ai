# Paired Experiment Statistics (P1.5.1)

## Scope

This module analyzes recorded metric values. It does not run models, validate that
the claimed seeds were actually used, or attest compute budgets. It is intentionally
separate from the SQLite registry.

## Paired comparison

Use `SeedMetric(seed, value)` and `compare_paired` to compare a candidate with
a baseline using exactly matched random seeds. The function rejects duplicate or
mismatched seed sets rather than silently comparing unpaired samples.

The reported effect is candidate-minus-baseline when higher is better, and
baseline-minus-candidate when lower is better. Positive values therefore always
mean improvement. The report includes means, mean/median paired difference,
sample standard deviation of paired differences, improvement rate, and paired
Cohen's dz (undefined when the paired-difference standard deviation is zero).

## Confidence interval

The interval is a deterministic paired percentile-bootstrap interval over paired
seed differences. Resampling preserves baseline/candidate pairing. The bootstrap
seed and iteration count are returned so the analysis can be repeated exactly.

This interval is descriptive and may have poor coverage with very small sample
counts or highly dependent seeds. It is not a substitute for a pre-registered
statistical analysis plan, power analysis, or domain-appropriate inferential test.
Always report the number of independent seeds and raw per-seed results. Do not
interpret an interval excluding zero as definitive proof when sample size or
experimental design is inadequate.

## Recommended protocol for Zhouyi-AI

- Compare Transformer/autoregressive baselines against candidate parallel-composition
  generators under identical data splits, parameter/compute budgets, and evaluation.
- Pair by seed and keep the seed set identical.
- Report in-distribution, compositional OOD, rule-family OOD, and long-context results
  separately.
- Record latency, throughput, memory, parameter count, training compute, accuracy,
  calibration, and failure rate as distinct metrics.
- Run enough independent seeds based on a pre-study power analysis; three seeds are
  useful for smoke tests, not strong scientific evidence.
- Preserve raw per-seed metrics and analysis configuration as versioned artifacts.


## Paired sign-flip inference

`paired_sign_flip_test` tests a zero-centered mean paired effect by flipping
the signs of paired differences. It enumerates all sign assignments for small
samples (up to the configured exact limit); larger samples use deterministic
Monte Carlo and the plus-one p-value correction. The result records the method,
number of permutations, and random seed.

This test requires independent, exchangeable paired units under the null. A
matching seed label alone does not establish that assumption. If seeds share
training data, checkpoints, hyperparameter tuning, or other dependencies, the
effective sample size may be lower and the test can be anti-conservative.
The test is two-sided and should be pre-specified before examining outcomes.

## Multiple comparisons

`holm_bonferroni` computes step-down adjusted p-values for a declared family
of metric/hypothesis tests. Define the family before inspecting results; do not
add or remove metrics after seeing their p-values. Adjusted p-values control
family-wise error under arbitrary dependence, but they do not repair biased
datasets, invalid pairing, optional stopping, or an underpowered experiment.
