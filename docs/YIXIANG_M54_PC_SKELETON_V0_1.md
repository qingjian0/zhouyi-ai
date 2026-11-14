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
assumes approximately linear-Gaussian data and adequate sample size. Insufficient-degree and zero/near-zero residual-variance cases are handled
conservatively as dependent (edge retained), because the conditional test is
unidentified or numerically degenerate rather than evidence of independence.

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

## Executed calibration harness

`prototype/yixiang_pc_calibration_m54.py` adds deterministic Monte Carlo checks for marginal Gaussian-null Type-I error, conditional-null Type-I error under a generated common-cause structure, and marginal power at predeclared correlation effects. Every estimated rate includes a Wilson 95% interval; the seed, repetitions, alpha, sample sizes, and effect sizes are reported. Unit tests check reproducibility and broad sanity bounds. These narrow linear-Gaussian checks do not establish calibration across arbitrary SCM families.

Run with:

```bash
python -m prototype.yixiang_pc_calibration_m54 --repetitions 500 --seed 20261114 --json
```

Near-null grids, larger sample-size sweeps, collinearity, deterministic relations, non-Gaussian noise, nonlinear edges, hidden confounding, selection bias, mechanism drift, and paired multi-seed algorithm comparisons remain open M55 validation.


## M54 integration update

The adapter is now exercised through `run_fair_comparison` using the same
train-only immutable context and evaluator-side truth boundary as the other
M54 adapters. A degenerate residual variance no longer prunes an edge: it
returns a conservative dependent result. This avoids interpreting an
unidentified test as affirmative evidence of conditional independence.

This integration test establishes interface compatibility, not end-to-end
algorithm superiority or resource-enforced fairness. The harness still relies
on trusted adapters; process isolation and external resource metering remain
required for adversarial or production-grade comparisons.
