# E13-C.3.6 — Sequential Bayesian Evidence Accumulation

Date: 2026-11-11

## Motivation

C.3.5 selects observations in observation space but does not update candidate
beliefs after evidence arrives. C.3.6 adds an exact finite-state Bayesian
filter. It maintains two coupled distributions per candidate:

1. posterior probability of the joint mechanism + observation-channel
   hypothesis;
2. latent-state distribution conditional on that candidate and all evidence
   observed so far.

The second distribution is essential. Multiplying unconditional observation
marginals across time is generally incorrect because observations are coupled
through hidden state.

## Generative model

For candidate (i):

- mechanism: (P_i(s_{t+1}\mid s_t,a_t,c))
- observation channel: (P_i(o_t\mid s_t,q_t))
- prior candidate weight: (w_i)

The filter predicts next latent states, projects them through the selected
sensor channel, and conditions on the received observation. Candidate weights
are updated by predictive likelihood:

[
w_i' = \frac{w_i P_i(o_t\mid o_{0:t-1},a_{0:t-1},c,q_{0:t})}
{\sum_j w_j P_j(o_t\mid o_{0:t-1},a_{0:t-1},c,q_{0:t})}
]

Within each candidate, the latent belief is updated by the corresponding
Bayes filter. All arithmetic uses exact `Fraction` values.

## Implemented API

- `BayesianObservationCandidate`: a candidate mechanism plus explicitly
  keyed observation channels.
- `initialize_observation_belief`: validates a normalized candidate prior
  and initial latent-state distribution, then conditions both on the first
  observation.
- `advance_observation_belief`: performs one action/observation filter step,
  carrying each candidate's conditional latent-state distribution forward.
- `BayesianObservationBelief`: immutable current posterior and evidence
  sequence.
- `BayesianUpdateResult`: reports UPDATED, UNKNOWN or CONTRADICTION,
  predictive evidence probability and per-candidate likelihoods.

## Evidence semantics

- UPDATED: all positive-weight candidates have the required transition and
  observation support, and the observation has positive total predictive
  probability.
- UNKNOWN: required transition/channel/support is missing for a candidate
  with nonzero posterior weight. No partial posterior is returned.
- CONTRADICTION: the observation has zero predictive probability under every
  remaining candidate. No posterior is returned and no candidate is invented.
- Duplicate evidence IDs are rejected.
- Zero-weight candidates remain at zero and cannot be resurrected by later
  evidence.
- Evidence records preserve the supplied evidence ID, sensor ID, action and
  observation. The caller remains responsible for the provenance and trust
  assessment of the observation itself.

## Critical correctness property

A hidden-state process with a perfect sensor can have
(P(o_t=0)=P(o_{t+1}=1)=1/2) as separate marginals while
(P(o_t=0,o_{t+1}=1)=0) under identity dynamics. The filter carries the
conditional latent-state distribution, so it detects this impossible sequence
instead of multiplying the two marginals and assigning it positive
likelihood.

## Limits and next gates

- Finite discrete state/action/context/observation spaces and known candidate
  kernels only.
- Exact rational probabilities; no parameter estimation, approximate
  inference, particle filtering or continuous-state support.
- Candidate hypotheses combine mechanism and sensor channel. Mechanism-only
  attribution still requires controlled comparisons with the observation
  channel held fixed; channel-only attribution requires the mechanism held
  fixed.
- Priors are explicit inputs, not learned or justified by Yi-Xiang labels.
- This is Bayesian filtering over supplied hypotheses, not proof that the
  candidate set is exhaustive or that the true mechanism is represented.
- Next: evidence provenance/trust policy, calibrated/learned kernel estimation,
  posterior-predictive calibration, candidate birth/split/merge policy and
  active query selection by genuine expected information gain using the
  posterior predictive observation distributions.

No empirical superiority over Transformer or other architectures is claimed.
