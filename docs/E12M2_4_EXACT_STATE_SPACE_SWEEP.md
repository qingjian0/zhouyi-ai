# E12-M2.4: exhaustive tiny-state-space sweep

## Research question

The M2.3 exact audit initially covered one 2x2 degree sequence. M2.4
enumerates every labeled binary incidence matrix for shapes 2x2, 2x3, 3x2,
and 3x3, groups matrices by row/item degree margins, and audits every
distinct feasible margin profile.

For each profile it checks:
1. Connectivity of all fixed-margin realizations under valid bipartite 2-switches.
2. Equality of forward and reverse proposal multiplicities.
3. Exact row and column sums of the integer transition matrix, including
   rejected proposals as diagonal self-loops.

## Exact transition kernel

The production sampler chooses an unordered pair of distinct incidence edges
uniformly. The audit helper counts ordered pairs, so off-diagonal transition
multiplicity is divided by two. Invalid proposals remain at the current state.
The total number of proposals is choose(E, 2), where E is the number of edges.
Exact equality of all row and column sums supports a uniform stationary
distribution on the enumerated state space; connectivity is separately
required for irreducibility.

## Reproduce

```bash
python -m prototype.e12m2_state_space_sweep
python -m unittest tests.test_e12m2_state_space_sweep -v
```

The JSON report includes the number of degree profiles, maximum realization
count, disconnected profiles, asymmetric profiles, and exact kernel checks.
The sweep is bounded to dimensions no larger than 3x3 and uses the existing
state-count safety cap.

## Interpretation limits

This is exhaustive only for the enumerated tiny labeled graph shapes. It
does not prove 2-switch connectivity for arbitrary degree sequences or larger
graphs, and it says nothing about finite-time mixing. A connected state graph
and a uniform stationary distribution do not imply that the chain reaches
that distribution within the current burn-in/thinning budget. The next gate
is larger sparse shapes under strict state caps, followed by finite-chain
empirical-frequency comparisons against exact stationary probabilities.
