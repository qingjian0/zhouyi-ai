# M65 — Bounded-exclusion IV sensitivity v0.1

Status: implementation and focused tests added; exact-head CI pending.

## Objective

Do not force a point-identification claim when the IV exclusion restriction is doubtful. M65 relaxes exclusion using an explicit sensitivity parameter while retaining instrument-outcome exogeneity and a nonzero first stage.

## Moment model

For a scalar binary instrument Z, binary exposure X, and outcome Y, the prototype uses:

Cov(Z,Y) = beta * Cov(Z,X) + gamma * Var(Z), with |gamma| <= delta.

The returned set is the interval with endpoints:

(Cov(Z,Y) - delta Var(Z)) / Cov(Z,X)
(Cov(Z,Y) + delta Var(Z)) / Cov(Z,X)

The endpoints are sorted to handle a negative first stage. At delta=0 the interval collapses to the ordinary Wald ratio. Increasing delta weakly widens the set.

## Retained assumptions and graph gate

The graph gate still requires:
- a directed relevance path Z→X;
- no open back-door path from Z to Y after deleting outgoing edges from Z;
- nonzero exact-population first-stage covariance.

Unlike M64's point-IV screen, this M65 sensitivity route does not require the exclusion graph criterion to pass. Instead, the total reduced-form direct effect of Z on Y is bounded by delta in the linear covariance-moment model.

## Interpretation limits

- The result is a set for a linear structural coefficient under the declared moment model.
- It is not automatically a nonparametric ATE, a complier LATE, or a binary-outcome potential-outcome bound.
- The sensitivity parameter delta is externally specified; it is not learned from the observed distribution.
- Exogeneity remains untestable from the observed distribution and is conditional on the supplied DAG.
- No finite-sample confidence region, weak-IV robust inference, multiple instruments, covariate adjustment, or exogeneity-violation sensitivity is implemented.
- This is not a complete invalid-IV solution.

## Controlled tests

- An exclusion-violating but graph-exogenous instrument is allowed into the bounded-exclusion sensitivity route.
- delta=0 collapses to a point Wald ratio.
- Larger delta produces a nested, wider effect set.
- An instrument with an open back-door path to Y is rejected.
- Negative and non-finite delta values are rejected.

## Research basis

The design follows the methodological lesson that IV exclusion and exogeneity can fail and should be made explicit rather than hidden. Relevant research includes:
- Kang et al. (2025), *Identification and Inference with Invalid Instruments*: https://doi.org/10.1146/annurev-statistics-112723-034721
- Penn et al. (2025), *BudgetIV: Optimal Partial Identification of Causal Effects with Mostly Invalid Instruments*: https://proceedings.mlr.press/v258/penn25a.html
- Yamaguchi (2025), *From perfect to practical: Partial identification methods for causal inference in strategic management research*: https://doi.org/10.1002/smj.3714

M65 is a narrow linear-moment sensitivity extension, not a general partial-identification engine and not empirical evidence of yixiang causality.
