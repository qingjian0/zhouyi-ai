# E12-M2.5: exact stationary law and finite-chain convergence

## Objective

M2.4 audits tiny-state connectivity and transition-kernel balance. M2.5
connects that exact kernel to finite-run behavior:

- Build the complete transition matrix with rational probabilities.
- Solve the stationary equations exactly using rational Gaussian elimination.
- Verify the stationary law is uniform for the symmetric 2-switch proposal.
- Run seeded finite chains and compare empirical occupancy with the exact
  stationary law using total variation distance (TV).

## Reproduction

```bash
python -m prototype.e12m2_finite_chain_audit
python -m unittest tests.test_e12m2_finite_chain_audit -v
```

The default example is deliberately tiny. Increase the state space only
within a safe exact-enumeration bound. Rational arithmetic is exact for the
transition matrix and stationary vector; the Monte Carlo occupancy and TV
are finite-sample estimates.

## Interpretation

A uniform stationary law does not imply rapid convergence. TV distance is
reported separately for each chain and for pooled samples. A small observed
TV in one run is not a mixing-time guarantee; a large value may reflect
insufficient burn-in, autocorrelation, poor exploration, or simply sampling
noise. Always vary initial states, seeds, burn-in, and run length before
making claims about the sampler.

This module does not alter the motif statistic or claim semantic discovery.
It strengthens the conditional-null sampler's mathematical and empirical
validation only.
