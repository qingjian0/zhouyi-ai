# E12-A2-M — Active Measurement Selector Prototype

Status: first deterministic implementation committed on
`research/e12a2-selector-prototype-2026-11-11`. The code is a finite-hypothesis
baseline; no benchmark result or superiority claim is made here.

## Files

- `prototype/e12a2_active_measurement_selector.py`
- `tests/test_e12a2_active_measurement_selector.py`

## Contract

The learner receives only:
- hypothesis IDs and prior weights;
- per-action, per-hypothesis outcome distributions;
- declared action costs;
- remaining acquisition budget.

It does not receive hidden generator state, evaluator truth, or locked Test data.
The environment remains responsible for actually performing a measurement and
revealing its outcome.

For action a, the implementation computes mutual information in bits:

`IG(a) = H(H) - E_o[H(H | a,o)]`

and selects the feasible action maximizing:

`U(a) = IG(a) / (cost(a) + epsilon)`

Tie-breaking is deterministic: lower cost, then lexical action ID. The result is
one of:
- `SELECTED`
- `NO_DISCRIMINATING_ACTION`
- `BUDGET_EXHAUSTED`
- `INVALID_ACTION_SET`

`update_weights` applies a Bayesian update only after an outcome is supplied by
the environment. An impossible observation is rejected rather than silently
creating a new hypothesis.

## Test coverage

The tests cover:
- one-bit information gain for a balanced split;
- zero information when all hypotheses agree;
- selection of a discriminating action;
- cost-normalized choice;
- no-discrimination and budget-exhaustion states;
- deterministic tie-breaking;
- Bayesian posterior update;
- rejection of impossible outcomes and invalid probability mass.

## Run

```bash
python -m unittest tests.test_e12a2_active_measurement_selector -v
python -m prototype.e12a2_active_measurement_selector
```

## Known limits and next gates

1. This is passive measurement selection (A2-M), not intervention selection
   (A2-I) and not causal discovery.
2. The action outcome distributions are supplied by the benchmark protocol;
   learning or calibrating those distributions is not implemented.
3. The current selector assumes a finite, explicit hypothesis set and declared
   outcome spaces.
4. It uses expected information gain divided by cost; risk, privacy, latency,
   and irreversibility must be separate declared constraints before real-world
   actions are considered.
5. The unit tests must pass in CI, followed by multi-seed synthetic episodes,
   random/fixed/disagreement baselines, exact tiny-instance oracle comparison,
   and held-out world-family evaluation.
6. Only after generic A2-M passes should Yijing-inspired priors be tested against
   capacity-matched generic partitions and deliberately incorrect priors.

A successful unit test establishes implementation behavior only. It does not
establish sample efficiency, robust active learning, or any advantage over
existing methods.
