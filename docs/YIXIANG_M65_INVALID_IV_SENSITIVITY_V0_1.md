# M65 — Bounded-exclusion IV sensitivity v0.1

Status: implementation complete; focused and repository-wide CI passed.

## Objective

Do not force a point-identification claim when the IV exclusion restriction is doubtful. M65 relaxes exclusion using an explicit sensitivity parameter while retaining instrument-outcome exogeneity and a nonzero first stage.

## Moment model

For a scalar binary instrument Z, binary exposure X, and outcome Y:

Cov(Z,Y) = beta * Cov(Z,X) + gamma * Var(Z), with |gamma| <= delta.

The returned set has endpoints:

- (Cov(Z,Y) - delta Var(Z)) / Cov(Z,X)
- (Cov(Z,Y) + delta Var(Z)) / Cov(Z,X)

Endpoints are sorted to handle a negative first stage. At delta=0 the interval collapses to the ordinary Wald ratio. Increasing delta weakly widens the set.

## Retained assumptions and graph gate

- A directed relevance path Z→X.
- No open back-door path from Z to Y after deleting outgoing edges from Z.
- Nonzero exact-population first-stage covariance.
- A linear covariance-moment model and externally specified bound delta.

Unlike M64's point-IV screen, this sensitivity route does not require the exclusion graph criterion to pass. Instead, the total reduced-form direct effect of Z on Y is bounded by delta.

## Validation

- The first focused run #43594022408 exposed a missing _decode import and a reversed nested-interval assertion; both were repaired.
- Repaired code/test head e52788f996f733d941a107b55cadd3541068e07c passed all 11 combined M64/M65 tests in focused workflow #43594100977.
- Full repository workflow #43594100995 completed successfully: unit tests, E01, E01-B, E01-C, E02-A, E02-B, E02-C, and E02-D all passed.

## Interpretation limits

- The result is a set for a linear structural coefficient under the declared moment model.
- It is not automatically a nonparametric ATE, a complier LATE, or a binary-outcome potential-outcome bound.
- Delta is externally specified; it is not learned from the observed distribution.
- Exogeneity remains untestable from the observed distribution and is conditional on the supplied DAG.
- No finite-sample confidence region, weak-IV robust inference, multiple instruments, covariate adjustment, or exogeneity-violation sensitivity is implemented.
- This is not a complete invalid-IV solution.

## Research basis

- Kang et al. (2025), *Identification and Inference with Invalid Instruments*: https://doi.org/10.1146/annurev-statistics-112723-034721
- Penn et al. (2025), *BudgetIV: Optimal Partial Identification of Causal Effects with Mostly Invalid Instruments*: https://proceedings.mlr.press/v258/penn25a.html
- Cinelli & Hazlett (2025), *An omitted variable bias framework for sensitivity analysis of instrumental variables*: https://doi.org/10.1093/biomet/asaf004

M65 is a narrow linear-moment sensitivity extension, not a general partial-identification engine and not empirical evidence of yixiang causality.
