# M66 — Multiple-instrument bounded-invalidity sensitivity v0.1

## Motivation

M65 handles one instrument and bounds a single reduced-form direct-effect term. That is too narrow for settings with several candidate instruments. The 2025 invalid-IV literature distinguishes exclusion violations from instrument–confounder dependence, and documents majority/plurality identification rules, weak-IV complications, and sensitivity frameworks for both side effects and confounding. M66 takes a deliberately narrower step: multiple graph-screened instruments with explicit per-instrument bounds in a linear reduced-form projection model.

Research references:
- Kang et al. (2025), *Identification and Inference with Invalid Instruments*: https://doi.org/10.1146/annurev-statistics-112723-034721
- Cinelli & Hazlett (2025), *An omitted variable bias framework for sensitivity analysis of instrumental variables*: https://doi.org/10.1093/biomet/asaf004
- Watson et al. (2024), *Bounding Causal Effects with Leaky Instruments*: https://arxiv.org/abs/2404.04446

## Model

For a selected instrument vector Z, define the population linear projection coefficients:

- gamma = Var(Z)^(-1) Cov(Z, X)
- Gamma = Var(Z)^(-1) Cov(Z, Y)

Under a constant linear structural coefficient beta and reduced-form violation vector pi:

Gamma = beta * gamma + pi.

M66 declares instrument-specific bounds |pi_j| <= delta_j. Each instrument therefore implies an interval for beta:

[(Gamma_j - delta_j) / gamma_j, (Gamma_j + delta_j) / gamma_j],

with endpoints sorted when gamma_j is negative. The reported sensitivity set is the intersection of these intervals.

## Graph screen

A candidate is included only when:
- it is observed;
- a directed path to the exposure exists;
- deleting its outgoing edges leaves no open back-door path to the outcome in the supplied DAG.

The exclusion restriction is not required to pass: its possible reduced-form violation is represented by delta_j. Graph-based exogeneity is still an assumption conditional on the supplied DAG, not something established by the observed joint distribution.

## Diagnostics and abstention

- Singular instrument covariance matrix: abstain.
- Any near-zero conditional first-stage projection coefficient: abstain rather than divide by a weak coefficient.
- No graph-screened instruments: abstain.
- Empty interval intersection: report incompatibility with the declared violation bounds, not a point estimate.
- Scalar delta applies the same bound to all selected instruments; a mapping supplies instrument-specific bounds.

## Scope limits

- The estimand is a constant linear structural coefficient under a population projection/moment model.
- This is not automatically a nonparametric ATE or LATE bound.
- No finite-sample uncertainty, weak-IV-robust confidence set, majority/plurality valid-instrument selection, nonlinear effects, covariate adjustment, or exogeneity-violation sensitivity is implemented.
- A DAG screen is only as credible as the supplied graph.
- Synthetic tests validate algebra and abstention behavior, not the validity of yixiang causal claims.

## Focused tests

The M66 tests cover intersecting intervals, incompatibility at zero tolerance, graph-based exclusion of a confounded candidate, invalid sensitivity bounds, singular instrument covariance, and weak conditional first-stage abstention.
