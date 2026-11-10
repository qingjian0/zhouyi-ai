# E12-A2-M — Active Measurement Selector Prototype

Status: bounded deterministic implementation. Tests are authored; execution status must be checked on the exact commit. This is not an intervention policy, causal learner, neural learner, or Yijing-prior result.

## Scope

Implements the first E12-A2 contract over finite candidate hypotheses and permitted measurements:
- exact Shannon entropy and expected information gain;
- normalized candidate priors;
- per-hypothesis outcome likelihood tables, including deterministic and noisy probes;
- cost-normalized utility IG / cost;
- remaining-budget filtering;
- deterministic tie-break: highest utility within tolerance, then lower cost, then lexical action ID;
- explicit SELECTED, NO_DISCRIMINATING_ACTION, BUDGET_EXHAUSTED, and INCONSISTENT states;
- Bayes update only after an environment-side outcome is supplied.

## API boundary

select_probe(priors, probes, remaining_budget) receives only learner-visible candidate weights, probe likelihoods, and costs. It has no evaluator truth, hidden world, or locked-test argument.

posterior_after_observation(..., observed_outcome) is called only after the environment reveals an outcome. An undeclared outcome is invalid; a declared outcome with zero prior predictive probability returns INCONSISTENT. Candidate expansion after seeing the outcome is deliberately forbidden.

The module models passive measurement selection (A2-M). It does not authorize or choose interventions (A2-I).

## Tests authored

- balanced deterministic split gives one bit and is selected;
- candidate agreement yields zero information and explicit abstention;
- cost-normalized selection can prefer a cheaper, lower-IG probe;
- deterministic tie-break;
- budget exhaustion;
- impossible outcome;
- noisy Bayes update;
- invalid likelihood normalization;
- probe input-order invariance.

## Known limitations

- Finite hypotheses and finite outcomes only.
- Likelihoods are supplied by the candidate model; calibration is not established.
- Cost is a single positive scalar; risk, latency, privacy, and irreversibility remain separate future dimensions.
- No active-learning benchmark or comparison against random/fixed policies is included yet.
- No Yijing-inspired prior or state partition is included. Those require capacity-matched controls after the generic selector is validated.

## Run

```bash
python -m unittest tests.test_e12a2_active_measurement -v
```
