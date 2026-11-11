# E13-C.3.2 Cross-domain stochastic multi-step dynamics and feedback tests

Date: 2026-11-11

## Status

Executable finite-state multi-step trajectory comparison added. The prototype
compares exact mapped latent-state distributions at every step of a declared
action sequence. It is a bounded validation instrument, not an open-world
causal discovery system or proof of global mechanism equivalence.

## Why one-step kernel agreement is insufficient

A pair of systems can agree at the observed initial state/action row and
diverge immediately after entering a new state. For example:

- Positive feedback: low -> high -> high -> high.
- Negative feedback: calm -> tense -> calm -> tense.

If only the first transition is tested, both systems appear identical. The
second transition reveals the different feedback structure.

## Implemented API

- `TrajectoryValidationCase`: explicit case ID, source/target initial
  states, and source-domain action sequence.
- `_map_state_distribution`: maps every state in a categorical distribution
  into target vocabulary, merging probability mass if mappings converge.
- `_propagate_mapped_source`: exact source rollout followed by per-step
  vocabulary mapping.
- `validate_cross_domain_trajectory`: maps source actions, independently
  propagates target dynamics, and compares each time step with exact TV
  distance.
- `compare_action_sequences`: evaluates multiple declared action sequences
  independently and preserves each result.

The validator requires explicit initial-state alignment and action mapping.
Missing source or target transition support is reported as UNKNOWN, not as a
pass or as a contradiction. A mismatch at any step rejects the tested
trajectory. A pass applies only to that initial state and action sequence.

## Feedback counterexample

The test suite includes two renamed one-variable systems:

- Source: low -> high; high -> high (positive/absorbing feedback).
- Target: calm -> tense; tense -> calm (negative/oscillating feedback).

Their one-step distributions from the initial states match exactly. Their
two-step distributions have total variation distance 1. This demonstrates
why one-step kernel matching cannot stand in for multi-step feedback testing.

A matching positive-feedback target is also tested over multiple steps. Tests
cover unknown initial alignment, missing target support, and independent
evaluation of multiple action sequences.

## Mathematical comparison

For each step t, map the source state distribution into target vocabulary,
then compare it with the independently propagated target distribution:

`TV_t = 1/2 * sum_s |P_source_mapped(s,t) - P_target(s,t)|`

The report retains each step's exact Fraction distance. It does not collapse
the whole trajectory to a single average that could hide a critical local
divergence. Any step above the declared threshold yields MISMATCH.

## Limits

- Finite discrete state spaces only.
- Explicit variable/value/action mappings only.
- No automatic discovery of feedback direction or semantic mappings.
- No hidden-state inference, confounder handling, continuous-time dynamics,
  asynchronous/concurrent action semantics, or partial observability inference.
- No posterior candidate revision under noisy observations yet.
- No Bayesian EIG or claim of calibrated uncertainty.
- PASS is bounded to supplied states and action sequences; exhaustive
  equivalence requires coverage of the relevant reachable state/action space.

## Next gates

1. Add context-indexed transition kernels and explicit context mappings.
2. Add active action-sequence selection that maximizes candidate trajectory
   disagreement subject to authorization, risk, and cost constraints.
3. Add evidence-ledger events for PASS, MISMATCH, UNKNOWN and contradiction,
   retaining provenance and prior candidates.
4. Add stochastic noisy-evidence posterior revision only after priors and
   likelihood assumptions are specified.
5. Run matched-budget ablations for no structural prior, shuffled prior,
   generic structural prior, and Yi-Xiang-derived candidate biases.
