# M69 — Heteroskedasticity-robust Anderson–Rubin test v0.1

## Motivation

M68 supplies classical Anderson–Rubin (AR) finite-sample inference under iid Gaussian homoskedastic errors. Applied observational data often exhibit heteroskedasticity, so that exact F calibration cannot be carried over unchanged. M69 adds a heteroskedasticity-consistent covariance estimator to the reduced-form AR moment restriction.

## Test

For candidate structural coefficient beta0, define the null outcome Y(beta0) = Y - beta0 X. Partial out the intercept and declared controls, regress the residualized null outcome on residualized instruments, and test that all instrument coefficients are zero using an HC0 sandwich covariance matrix.

The Wald statistic has an asymptotic chi-square reference distribution with degrees of freedom equal to the number of instruments. It does not divide by the estimated first-stage coefficient, so it remains an AR-style weak-identification-robust test under valid instrument assumptions.

## Scope and caveats

- HC0 is asymptotic, not an exact finite-sample F calibration.
- This milestone does not provide a confidence-set inversion.
- It does not implement HC1/HC2/HC3, cluster-robust, HAC, wild-bootstrap, or many-instrument corrections.
- Small-sample and many-instrument distortions may remain.
- Instrument exogeneity and exclusion remain substantive assumptions; the test does not validate them.
- One endogenous regressor; multiple instruments; optional controls.
- Synthetic tests validate code behavior, not the validity of any empirical yixiang causal claim.

## References

- Anderson & Rubin (1949), *Estimation of the Parameters of a Single Equation in a Complete System of Stochastic Equations*.
- Andrews, Stock & Sun (2019), *Weak Instruments in Instrumental Variables Regression: Theory and Practice*, Annual Review of Economics, https://doi.org/10.1146/annurev-economics-080218-025643.
- MacKinnon & White (1985), *Some Heteroskedasticity-Consistent Covariance Matrix Estimators with Improved Finite Sample Properties*, Journal of Econometrics, https://doi.org/10.1016/0304-4076(85)90158-7.
- Stock & Yogo (2005), *Testing for Weak Instruments in Linear IV Regression*, in Identification and Inference for Econometric Models.

## Tests

Five focused tests cover heteroskedastic HC0 output semantics, no-strong-first-stage handling, rank deficiency, invalid inputs, and covariate adjustment.
