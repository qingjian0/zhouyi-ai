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
