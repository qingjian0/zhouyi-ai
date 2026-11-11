# E13-C.3.5 — Active Observation and Observation-Channel Identifiability

Date: 2026-11-11

## Purpose

C.3.4 selects action sequences by disagreement between candidate latent-state
trajectories. That is insufficient for an agent that acts through sensors:
different latent mechanisms may be observationally indistinguishable, while
identical mechanisms paired with different observation channels may produce
different measurements.

C.3.5 moves active selection into observation space.

## Model separation

The model has two distinct stochastic layers:

- Context-conditioned mechanism:
  (P(s_{t+1}\mid s_t,a_t,c))
- Sensor/measurement channel:
  (P(o_t\mid s_t,q))

For a candidate mechanism (M_i), observation channel (O_{ij}), initial
state, fixed context, action sequence and sensor query, the projected
observation distribution at each step is:

[
P_i(o_t\mid a_{0:t-1},c,q)
=\sum_{s_t}P_i(s_t\mid a_{0:t-1},c)P_{ij}(o_t\mid s_t,q)
]

The selector ranks candidates using exact pairwise total-variation distance
between these observation distributions, averaged over time and candidate
pairs. This is predictive disagreement in the observation space, **not**
Bayesian expected information gain. No posterior update is performed.

## Implemented prototype

- `ContextualObservationCandidate`: one contextual mechanism plus explicit
  observation kernels keyed by sensor/query ID.
- `ContextualObservationQuery`: sensor ID, action sequence, authorization,
  risk and cost.
- `project_contextual_observation_trajectory`: propagates latent state
  distributions internally and projects every time step through the selected
  observation kernel.
- `select_contextual_observation_query`: exposes and scores only observation
  distributions. Missing transition or observation support is UNKNOWN.
- Authorization, hard risk and optional hard cost gates run before scoring.
  Soft utility cannot override a hard gate.

The observation kernel is reused across candidates to isolate mechanism
differences. Candidate-specific kernels under the same sensor ID represent
competing observation-channel hypotheses. These are distinct experimental
conditions and must not be conflated.

## Required identifiability controls

1. **Mechanism difference, shared coarse sensor:** two latent mechanisms differ
   but the sensor maps their differing states to the same observation symbol.
   Expected result: zero observation-space disagreement and
   `OBSERVATIONALLY_NON_DISCRIMINATING`.
2. **Same mechanism, different channel hypotheses:** latent transition systems
   are identical but sensor kernels differ. A nonzero score is attributed to
   observation-channel uncertainty, not mechanism uncertainty.
3. **Joint mechanism/channel candidates:** select a sensor/action combination
   whose projected observations distinguish the joint candidates.
4. Missing observation rows/support remain UNKNOWN; they are never treated as
   zero probability or evidence of equivalence.
5. Project observations at every step; do not compare only terminal readings.
6. Authorization, risk and cost are hard gates.
7. The public forecast object contains observation distributions only, not
   latent state distributions.

## Interpretation and limits

- Zero disagreement means only that the supplied candidates are
  observationally equivalent for the supplied action sequence, context,
  initial state and sensor query. It does not prove global equivalence.
- Nonzero disagreement may arise from mechanism differences, observation
  channel differences, or both. Attribution requires factorial controls:
  hold the channel fixed to test mechanisms; hold the mechanism fixed to test
  channels; then evaluate joint candidates.
- This prototype assumes finite discrete states and categorical observations,
  exact rational probabilities, known candidate kernels and fixed context.
- It does not infer sensors, calibrate likelihoods, learn observation kernels,
  handle continuous/high-dimensional measurements, hidden confounding,
  adaptive sensor hardware, or posterior/EIG.
- Cross-domain observation-symbol mappings are not inferred. They require a
  separate explicit mapping contract before cross-domain comparison.
- No Yi-Xiang prior is hard-coded into the observation layer. Future tests may
  compare such priors only as falsifiable, preregistered structural biases.

## Tests

The test suite covers latent mechanism differences hidden by a shared coarse
sensor, channel differences under an identical mechanism, joint candidate
selection, incomplete observation support, multi-step projection, hard
authorization/risk/cost gates, and the observation-only forecast boundary.
