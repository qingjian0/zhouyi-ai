# M68 — Anderson–Rubin weak-instrument-robust inference v0.1

## Why this milestone is needed

M64–M66 use exact-population moments and graph screens. They are not finite-sample inference. M66 conservatively abstains when a conditional first-stage projection is weak, but a weak first stage should not be treated as a reason to invent a finite Wald interval or to declare the parameter unidentified in every inferential framework.

The Anderson–Rubin (AR) test tests a candidate structural coefficient without dividing by an estimated first-stage coefficient. Inverting the test can produce an unbounded, disconnected, empty, or bounded confidence set. Unboundedness is an informative result, not a software failure.

Research references:
- Anderson & Rubin (1949), *Estimation of the Parameters of a Single Equation in a Complete System of Stochastic Equations*.
- Andrews, Stock & Sun (2019), *Weak Instruments in Instrumental Variables Regression: Theory and Practice*: https://doi.org/10.1146/annurev-economics-080218-025643
- Dufour (1997), *Some Impossibility Theorems in Econometrics with Applications to Structural and Dynamic Models*: https://doi.org/10.1111/1468-0262.00015
- Mikusheva & Poi (2006), *Tests and Confidence Sets with Correct Size when Instruments are Potentially Weak*: https://doi.org/10.1177/1536867X0600600303
- Moreira (2003), *A Conditional Likelihood Ratio Test for Structural Models*: https://doi.org/10.1111/1468-0262.00421
- Doko Tchatoka & Ma (2025), *Inference with many instruments: When is Anderson–Rubin test still useful?*: https://doi.org/10.1016/j.econlet.2025.112702

## Implemented model

For a candidate beta0, form y(beta0) = Y - beta0 X and test whether all coefficients on the instrument vector are zero in the regression of y(beta0) on an intercept, optional controls, and Z.

M68 computes the classical homoskedastic AR F statistic and p-value, and analytically inverts the F test over beta. The inversion solves the quadratic inequality directly; it does not rely on a finite grid that could miss unbounded tails or disconnected components.

## Exactness and assumptions

The finite-sample F calibration is exact only under the declared linear model with iid, homoskedastic Gaussian errors, valid instruments, and a full-rank instrument matrix after residualizing controls. The AR test remains robust to weak first-stage identification under these assumptions.

This implementation is not heteroskedasticity-robust, cluster-robust, HAC-robust, or nonparametric. It handles one endogenous regressor and one or more instruments. It does not repair invalid instruments; exclusion and exogeneity remain substantive assumptions. M65/M66 sensitivity sets address bounded reduced-form exclusion deviations under separate assumptions and are not merged with this classical AR confidence set.

## Set geometry and abstention

The analytic inversion preserves:
- bounded interval;
- one unbounded ray;
- two unbounded rays;
- all real values;
- empty set;
- singleton boundary case.

No code path silently truncates an unbounded set or replaces it with a Wald interval.

## Tests

Seven tests cover:
1. A no-first-stage case where the AR p-value remains valid and the inverted set is all real.
2. A stronger first-stage case where the inverted set is bounded and contains the structural coefficient.
3. Finite-sample F degrees of freedom and p-value range.
4. Rank-deficient instruments after controls.
5. Invalid sample sizes and alpha.
6. Control residualization.
7. Weak-IV-robust flag and non-grid analytic inversion behavior.

Synthetic data verify implementation mechanics only; no empirical yixiang causal claim is established.
