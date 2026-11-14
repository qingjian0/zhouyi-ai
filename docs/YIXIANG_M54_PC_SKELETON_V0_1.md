# M54 PC-style target-skeleton baseline v0.1

## Purpose

Add a statistically defined conditional-independence comparator to the M54
train-only adapter protocol. This addresses a gap in M47, which currently has
random selection and observational marginal-correlation screening only.

## Method

- Candidate-target dependence is tested with a two-sided Fisher-z test on
  partial correlations.
- Conditioning columns are orthogonalized with modified Gram-Schmidt.
- Candidate adjacency is pruned when a conditioning subset yields
  p >= alpha.
- Defaults: alpha=0.05, maximum conditioning-set size=2.
- The adapter sees only the immutable training rows supplied by M54.

## Scope boundary

This is a **target-local PC-style skeleton heuristic**, not a full PC algorithm,
not FCI, and not full-DAG discovery. It does not orient edges, estimate causal
effects, or identify latent confounding. Its standard Fisher-z calibration
assumes approximately linear-Gaussian data and adequate sample size. Singular
or insufficient-degree cases are handled conservatively as dependent except
for zero residual variance, which is treated as conditionally independent;
this convention must be stress-tested under degeneracy before broad use.

The baseline must be run under the same training split and external resource
accounting as other M54 adapters. It reports no self-certified cost or sample
count. M54's adapter protocol currently audits declared budget fields but
cannot enforce actual CPU/memory/hidden data access against arbitrary Python
closures; production comparisons require process/container isolation and
external metering.

## Required follow-up validation

- Type-I error calibration under null and near-null partial correlations.
- Power curves across sample sizes, effect sizes, and conditioning-set sizes.
- Collinearity, deterministic relations, non-Gaussian noise, nonlinear edges,
  hidden confounding, selection bias, and mechanism drift.
- Paired multi-seed comparisons against correlation screening and random.
- No superiority claim until the full M55 statistical protocol is executed.
