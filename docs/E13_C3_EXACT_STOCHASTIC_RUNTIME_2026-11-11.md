# E13-C.3 exact finite stochastic mechanisms and observation noise

Date: 2026-11-11

## Status

Executable bounded prototype and unit tests. This is not an open-world causal
learner, calibrated probabilistic model, or evidence of superiority over
Transformer architectures.

## Two independent probability layers

- Mechanism kernel: P(s[t+1] | s[t], a[t], m, c), governing latent transitions.
- Observation kernel: P(o[t] | s[t], q), governing measurement by a sensor/query.

The transition kernel is propagated first. The observation kernel is applied
afterward. Changing sensor noise must not mutate latent trajectory probabilities.

## Exact finite oracle

prototype/e13_stochastic.py uses fractions.Fraction for finite categorical
probabilities. Each transition and observation row must be nonnegative and sum
exactly to one. Floating-point inputs are rejected at the contract boundary to
avoid binary rounding. Zero-probability outcomes remain zero.

propagate_latent_distribution performs exact finite-state forward propagation
and fails closed on missing transition rows. observation_distribution applies
an independently specified observation channel. run_stochastic_trajectory
retains both distributions at every step.

This is a small-system oracle, not a scalable inference engine. State-space
growth is explicit; no Monte Carlo approximation is hidden behind the API.

## Candidate disagreement is not expected information gain

jensen_shannon_divergence computes categorical JS divergence in bits between
candidate predictive observation distributions. The risk-aware selector
averages pairwise candidate JS divergence.

This is a disagreement heuristic, not Bayesian expected information gain.
True EIG requires explicit candidate priors and calibrated likelihoods over
possible observations, followed by posterior entropy calculation. Those
assumptions are deliberately absent here.

## Risk-aware query selection

select_risk_aware_query applies hard gates in order:
1. Authorization must be true.
2. Query risk must not exceed the declared hard risk limit.
3. Predictions must cover every candidate exactly once.
4. Only then are JS disagreement, cost, and risk-weighted utility ranked.

No utility score can compensate for an unauthorized query or a query exceeding
the hard risk limit. Risk and cost remain separately inspectable.

## Tests and limitations

Tests cover exact normalization, negative and float probability rejection,
multiple outcomes, zero-probability support, missing-row rejection, multistep
normalization, sensor-noise/mechanism-randomness separation, JS identity, and
hard authorization/risk gates.

Not implemented: stochastic cross-domain kernel mappings, posterior updates
under noisy evidence, calibrated priors/likelihoods, Bayesian EIG, intervention
policy optimization, continuous state/time, concurrent actions, or empirical
comparison against learned baselines.

Next gates:
- Specify priors and likelihoods before implementing posterior updates.
- Add cross-domain stochastic-kernel mapping and held-out intervention tests.
- Compare deterministic FSTS, stochastic mechanisms, observation-noise-only,
  and combined-noise conditions under matched budgets.
- Test direction reversal, feedback, sensor mismatch, and OOD refusal.
- Evaluate Yi-Xiang structural priors only as ablations against no-prior,
  shuffled-prior, and generic-structure controls.
