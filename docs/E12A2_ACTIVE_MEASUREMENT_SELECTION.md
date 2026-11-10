# E12-A2-M — Active Measurement Selector (Deterministic Baseline)

Status: implemented as a pure finite-hypothesis selector. This is an A2-M passive-measurement baseline; it is not an intervention learner, causal discovery system, neural architecture, or evidence of Yijing-specific benefit.

## 1. Implemented interface

Implementation: [prototype/e12a2_active_measurement.py](../prototype/e12a2_active_measurement.py)

Tests: [tests/test_e12a2_active_measurement.py](../tests/test_e12a2_active_measurement.py)

The learner receives:
- finite hypotheses with explicit normalized prior weights;
- a finite set of permitted measurement actions;
- per-hypothesis outcome likelihoods for each action;
- positive declared action costs;
- a remaining acquisition budget.

The selector does not receive evaluator truth, hidden generator state, or locked Test data.

## 2. Decision rule

For each action, calculate predictive outcome mass:

P(o | a) = sum_h P(h) P(o | h, a)

Then calculate expected posterior entropy and information gain:

IG(a) = H(H) - sum_o P(o | a) H(H | a, o)

The current baseline ranks eligible actions by:

U(a) = IG(a) / (cost(a) + epsilon)

Entropy is Shannon entropy in bits. Likelihoods are finite categorical distributions; deterministic predictions are represented by probabilities 0/1. The implementation supports noisy likelihoods without changing the selector contract.

## 3. Explicit outcomes

Selection returns one of:
- SELECTED
- NO_DISCRIMINATING_ACTION
- BUDGET_EXHAUSTED
- INVALID_ACTION_SET

Invalid priors, malformed prediction coverage, invalid likelihood distributions, duplicate IDs, non-positive costs, or invalid budgets do not silently fall back to a partial candidate set.

Ties are deterministic: highest utility, then lower cost, then lexicographically smaller action ID. A fixed numerical tolerance is part of the function input.

After the environment reveals an outcome, a separate update function applies Bayes' rule. If every candidate assigns zero likelihood to that observation, it returns INCONSISTENT and does not invent a new hypothesis.

## 4. Minimal discriminating example

Two hypotheses remain consistent with observations at x=0 and x=2:

- p1(x) = [x >= 2]
- p2(x) = [x = 2]

The action measuring x=0 predicts 0 under both; x=2 predicts 1 under both. Both have zero information gain.

The action measuring x=3 predicts 1 under p1 and 0 under p2. Under equal priors, it yields exactly 1 bit of information gain and is selected when its cost fits the budget.

## 5. Validation cases

The test suite covers:
- one-bit gain from an even split;
- zero-information actions and explicit abstention;
- cost-normalized selection with a noisy lower-cost action;
- deterministic tie-breaking;
- budget exhaustion;
- impossible observations;
- posterior update;
- prior and likelihood normalization;
- malformed/duplicate action sets;
- prediction-order invariance;
- API separation from evaluator truth.

The test suite is committed; CI is the authoritative execution record. Do not report local execution unless a local test run was actually performed.

## 6. Scope and limitations

- This is a finite, supplied hypothesis set. It does not autonomously discover an open-ended hypothesis language.
- Action predictions and priors are supplied inputs; the learner does not estimate its own causal model yet.
- The current acquisition utility is information gain per cost. Risk, irreversibility, privacy, latency, and safety constraints are not yet modeled.
- No active intervention is performed. A2-I requires a separate randomized causal protocol.
- No Yin/Yang, four-image, trigram, hexagram, or five-phase prior is integrated here.
- The two-hypothesis example is a correctness fixture, not a performance benchmark.

## 7. Next experiments

1. A2-B: benchmark selector against random, fixed, raw-disagreement, and exact-optimal policies over held-out synthetic world families.
2. A2-N: calibration under noisy observations and misspecified priors.
3. A1.1: evidence provenance and versioned candidate identity, so every hypothesis can be traced to the evidence and grammar that proposed it.
4. Only after generic baselines are stable, compare symbolic priors against capacity-matched generic partitions and deliberately permuted controls.

A Yijing-inspired structure earns a place only if it improves sample efficiency, cost, calibration, or out-of-distribution transfer under equal budgets, and if the gain survives negative controls.
