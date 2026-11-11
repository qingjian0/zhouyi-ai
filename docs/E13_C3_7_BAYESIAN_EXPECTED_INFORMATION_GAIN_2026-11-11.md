# E13-C.3.7 — Bayesian Expected Information Gain for Active Experiments

Date: 2026-11-11

## Purpose

C.3.4/C.3.5 ranked finite queries by trajectory or observation-space
disagreement. C.3.6 introduced a posterior over supplied joint mechanism +
observation-channel hypotheses and a conditional latent-state belief per
hypothesis. C.3.7 uses that posterior to select experiments by Bayesian
expected information gain (EIG).

## Query and prediction

A query is a finite action sequence paired with one sensor ID per step.
For each positive-posterior candidate, the evaluator enumerates the exact
joint probability distribution over future observation sequences, carrying
latent state and observation prefix jointly through each transition and
sensor channel. It does not multiply per-time marginal observation
probabilities.

For a hypothesis target (H), the score is mutual information:

[
\operatorname{EIG}(q;H)=I(H;O_{1:T}\mid q,D)
=H(O_{1:T}\mid q,D)-\mathbb{E}_{H\mid D}
[H(O_{1:T}\mid H,q,D)]
]

Here (D) is the evidence already incorporated into the C.3.6 belief. The
predictive sequence probabilities are exact rational values. Entropy uses
base-2 logarithms and is a floating-point approximation in bits.

## Information targets

- `candidate`: identify the joint candidate (mechanism + observation
  channel).
- `mechanism`: identify `mechanism_hypothesis_id`; candidates sharing the
  same mechanism label are grouped before mutual information is computed.
- `channel`: identify `channel_hypothesis_id`; candidates sharing the
  same channel label are grouped.

Mechanism/channel attribution requires explicit hypothesis labels. Candidate
identity EIG can be positive even when mechanism EIG is zero, for example
when only sensor-channel hypotheses differ. This avoids falsely attributing
sensor differences to mechanism differences.

## Safety and missing evidence

Authorization, hard risk limit and optional hard cost budget are checked
before forecasting or scoring. Soft utility is EIG minus weighted risk and
cost; it cannot override a hard gate. Missing transition/channel/observation
support makes a query UNKNOWN and excludes it from ranking. Forecasts expose
observation sequences only, not latent states.

## Implemented API

- `BayesianExperimentQuery`: action sequence, per-step sensor IDs, target,
  authorization, risk and cost.
- `select_bayesian_experiment`: exact finite predictive sequence enumeration,
  target-grouped mutual information and safe query ranking.
- `BayesianObservationCandidate` now supports optional explicit mechanism
  and channel hypothesis IDs for attribution.

## Limits

- Finite candidate set, finite discrete states/actions/observations, fixed
  context, known exact transition and observation kernels.
- No learning/calibration of the kernels or priors; Bayesian optimality is
  conditional on supplied models and prior.
- Entropy is computed numerically; predictive probabilities remain exact.
- No continuous action optimization, adaptive policy tree beyond a supplied
  fixed action sequence, or robust/minimax EIG under model misspecification.
- Candidate-set incompleteness is not detected automatically.
- Risk/cost are supplied external estimates, not inferred from information
  gain. Hard authorization/risk/cost constraints remain absolute.
- Yi-Xiang priors are not used as privileged probabilities; any future
  structural prior must be preregistered and ablated against generic and
  shuffled controls.

No empirical superiority over Transformer or other architectures is claimed.
