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
