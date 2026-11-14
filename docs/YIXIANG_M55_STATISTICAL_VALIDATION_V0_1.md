# M55 statistical validation protocol v0.1

## Purpose

M55 converts the M54 adapter harness into a statistically auditable comparison
workflow. The unit of pairing is the same scenario and random seed evaluated
by both methods. Methods must share data-generating parameters, train/validation/
test partitions, intervention permissions, and resource limits.

## Implemented inference utilities

`prototype/yixiang_stats_m55.py` provides:
- Wilson intervals for binomial rates such as Type-I error and power;
- Holm step-down family-wise error correction;
- Benjamini-Hochberg false-discovery-rate adjustment;
- deterministic percentile bootstrap intervals for paired mean differences;
- strict paired-cell validation that rejects duplicate or missing seed/method
  observations rather than silently dropping them.

The paired comparison reports method A minus method B, so the sign convention
must be retained when interpreting results. Bootstrap intervals quantify
sampling uncertainty across the supplied paired units; they do not repair
biased scenario selection or invalid data-generating assumptions.

## Required experiment matrix

Pre-register scenario families and seeds before execution:
1. linear-Gaussian SCMs: null, weak, medium, and strong direct effects;
2. common-cause confounding and collider/selection structures;
3. non-Gaussian noise (e.g. Laplace and bounded/heavy-tailed variants);
4. nonlinear mechanisms and interaction effects;
5. collinearity and near-deterministic relations;
6. mechanism drift and held-out mechanism families.

Run Random, marginal-correlation screening, the M54 PC-style target-skeleton
baseline, and any genuinely implemented SCM/Transformer/Zhouyi agents. Do not
list an unimplemented adapter as an experimental result. Keep evaluator truth
outside agent context and use external process/resource accounting for methods
that are not trusted in-process code.

## Reporting requirements

For every method/scenario/seed, preserve raw predictions and resource traces.
Report precision, recall, F1, structural Hamming distance where defined,
intervention coverage, invalid proposals, budget violations, and runtime/
resource measurements. Report Type-I error and power with Wilson intervals.
For method contrasts, use paired bootstrap intervals and report effect sizes.
Correct families of confirmatory p-values with Holm; use BH only for explicitly
exploratory families. Separate confirmatory from exploratory analyses.

## Acceptance criteria

- Reproducible seeds and immutable split manifests.
- Complete paired cells; missing runs are errors or explicitly documented.
- Calibration checks against known null generators.
- Power curves across sample sizes and effect sizes.
- Multiplicity correction for declared hypothesis families.
- No superiority claim based only on CI, a single seed, or synthetic toy data.

## Scope boundary

This first M55 commit implements inference and validation primitives plus
unit tests. It does not claim the full scenario matrix has been executed, nor
that Zhouyi/Yixiang outperforms established methods. The next experiment commit
must add reproducible generators and raw multi-seed results before drawing
substantive conclusions.


## Implemented paired synthetic runner

`prototype/yixiang_experiments_m55.py` now generates five deterministic
stress scenarios: linear-Gaussian direct effect, quadratic nonlinear effect,
non-Gaussian Laplace noise, latent common-cause confounding, and collider-based
selection. For each scenario/seed it runs the three currently implemented
comparators—Random, marginal correlation, and the M54 PC-style skeleton—through
the same M54 train-only comparison harness and emits per-method metrics.
The test suite verifies deterministic generators, complete paired method
cells, and clean budget/proposal status on a small smoke matrix.

This is a smoke-tested experiment harness, not yet a completed large-scale
study. The committed tests use a small seed/scenario subset. A scientific
result requires a larger pre-registered seed matrix, preserved raw run outputs,
scenario-stratified paired intervals, multiplicity correction, and independent
review of generator semantics. No Transformer, SCM learner, or Zhouyi agent
is claimed as measured unless an actual executable adapter is added and run.


## Expanded M55 design and dependence-aware uncertainty

The current runner includes twelve scenario families:
- strong, weak, near-null, and null linear-Gaussian effects;
- quadratic and two-parent multiplicative nonlinear mechanisms;
- non-Gaussian Laplace noise;
- latent common-cause confounding;
- collider-based selection;
- a noisy observed proxy for a latent cause (measurement-error stress);
- near-collinear observed predictors;
- hidden alternating-sign mechanism heterogeneity.

The standard study uses 50 seeds (1000–1049) at sample sizes 120, 240, and 480. Every scenario/size/seed cell runs the same three implemented methods and preserves the raw predicted-parent set and evaluator truth in a JSONL artifact.

A statistical dependence correction is important here: the three candidate-edge outcomes within one seed are not independent replicates. Therefore the reported false-positive-rate and power uncertainty intervals bootstrap independent seed-level clusters, not individual edges. The paired F1 contrasts also pair methods by the exact same scenario, sample size, and seed. Confirmatory paired p-values are sign-flip randomization tests and are adjusted across the declared contrast family using Holm; BH is retained as a secondary exploratory adjustment.

## First completed five-scenario sweep (historical baseline)

The first 50-seed sweep produced 2,250 method records in approximately 3.72 seconds of wall time, with maximum resident set size 16,684 KiB. Its results showed:
- linear-Gaussian: correlation screening and PC-style were essentially tied at high F1;
- Laplace-noise linear: both were also close;
- quadratic nonlinear: PC-style was materially worse than correlation screening;
- latent common-cause and collider-selection cases: all three methods produced false-positive associations, with no reliable direct-parent recovery.

These are synthetic results and not population estimates. The expanded twelve-scenario run supersedes this first sweep for M55 acceptance. The first run's raw artifact is retained in GitHub Actions run 43585306200.

## Resource accounting and artifacts

The dedicated workflow runs the study as a separate process under `/usr/bin/time -v` and uploads raw JSONL records, scenario summaries, paired contrasts, stdout, and process resource statistics as a 90-day artifact. This gives an external process-level wall-time and peak-RSS record, although it is not a per-adapter sandbox or a security boundary.
