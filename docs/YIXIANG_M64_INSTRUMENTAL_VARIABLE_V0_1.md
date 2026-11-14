# M64 — Graphical instrumental-variable identification v0.1

Status: implementation and controlled tests added; exact-head CI pending.

## Objective

Add a conservative IV route to the existing M61/M63 causal identification diagnostics. This is not a general causal identification algorithm.

## Graphical validity conditions

For instrument Z, exposure X, and outcome Y, the checker requires:

1. Relevance path: at least one directed path Z→X exists in the supplied DAG.
2. Exclusion: every directed path Z→Y passes through X; a direct or indirect bypass is rejected.
3. Exogeneity: after deleting outgoing edges from Z, Z and Y are d-separated. This screens open back-door paths from the instrument to the outcome in the supplied fully specified DAG.
4. Population relevance: the exact observed-data covariance Cov(Z,X) must exceed a configurable absolute threshold.

These graph checks are conditional on the supplied DAG. They do not prove that the DAG is correct, and no observational test can establish an untestable exclusion restriction by itself.

## Estimand semantics

For binary instrument and treatment, the implementation computes the exact-population Wald ratio:

Wald = Cov(Z,Y) / Cov(Z,X).

It does not label this ratio as the population ATE. It is labelled as a LATE for compliers only when the user-supplied case explicitly declares monotonicity. Monotonicity is not inferred from the DAG or verified from the observed joint distribution. Without that declaration the output remains `wald_ratio_monotonicity_unasserted`.

## Controlled cases and regressions

- Valid instrument with latent U confounding X and Y; Z is independent of U, exclusion holds, and monotonicity is explicitly declared. The expected Wald/LATE is 0.4 while the population ATE differs (0.5), protecting against an estimand-label error.
- Exclusion violation: Z has a direct Z→Y path bypassing X.
- Instrument confounding: U→Z and U→Y create an open back-door path.
- Weak/near-irrelevant first stage: graph conditions hold but observed Cov(Z,X) falls below the declared threshold.
- Missing monotonicity declaration: ratio is returned with non-LATE/non-ATE label.
- Cyclic DAG rejection.

## Important limits

- Exact population distributions only; no finite-sample 2SLS, standard errors, weak-IV robust confidence sets, or heteroskedasticity-robust inference.
- Binary instrument and binary treatment only.
- No multiple instruments, multiple endogenous treatments, continuous treatment, heterogeneous response beyond the LATE interpretation, or covariate-conditional IV.
- No sensitivity analysis for exclusion/exogeneity violations and no partial-identification bounds for invalid instruments.
- No proof of instrument validity from observed data.
- No claim that a yixiang/classical-text relationship is an instrumental variable.

## Research rationale

Recent work emphasizes that IV assumptions are difficult to verify and that violations should be analyzed rather than hidden. Invalid-IV reviews cover exclusion and exogeneity violations; partial-identification methods provide effect sets under relaxed assumptions; covariate-assisted bounds can be more defensible than forcing point identification; and recent work studies multiple treatments and heterogeneous response types. This prototype deliberately stops before those extensions:
- Kang et al. (2025), *Identification and Inference with Invalid Instruments*: https://doi.org/10.1146/annurev-statistics-112723-034721
- Penn et al. (2025), *BudgetIV*: https://proceedings.mlr.press/v258/penn25a.html
- Zhang et al. (2025), *Covariate-assisted bounds on causal effects with instrumental variables*: https://doi.org/10.1093/jrsssb/qkaf028
- Angrist, Santos & Tecchio (2025), *One Instrument, Many Treatments*: https://economics.mit.edu/sites/default/files/2026-01/w34607.pdf

M64 is a controlled graph/estimand diagnostic, not empirical evidence of yixiang causal validity or a complete IV estimator.
