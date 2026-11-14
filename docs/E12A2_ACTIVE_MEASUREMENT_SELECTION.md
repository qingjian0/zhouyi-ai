# E12-A2 — Active Measurement and Probe Selection

Status: research protocol proposal. No implementation or benchmark result is claimed yet. This experiment follows E12-A0 identifiability and E12-A1 typed predicate proposal.

## 1. Research question

When several candidate predicates remain consistent with current evidence, can the learner choose the next permitted measurement that is expected to distinguish them most efficiently?

This is an active information-acquisition problem. It is not automatically causal discovery: a query that measures a value is distinct from an intervention that changes the world.

## 2. State

At decision time, the learner receives:
- a finite candidate set H proposed from permitted Train evidence;
- a normalized prior weight w(h) for each candidate, or a preregistered uniform prior;
- an action set A of permitted measurements, each with a declared cost;
- the observation schema and noise model;
- the immutable evidence already available.

The learner must not receive evaluator truth, hidden generator state, or locked Test examples.

Each action a has a predicted outcome distribution under every candidate:
P(o | h, a). Deterministic predicates are the zero-noise special case.

## 3. Expected information gain

Candidate uncertainty is measured by entropy:

H(H) = - sum_h w(h) log2 w(h)

For an action a, compute the predictive outcome distribution:

P(o | a) = sum_h w(h) P(o | h, a)

After observing o, update the candidate weights by Bayes' rule and compute posterior entropy. Expected information gain is:

IG(a) = H(H) - sum_o P(o | a) H(H | a, o)

Choose a permitted action by maximizing a cost-adjusted utility:

U(a) = IG(a) / (cost(a) + epsilon)

The cost unit and epsilon must be fixed before evaluation. If actions have risk, irreversibility, latency, or privacy cost, those must be represented as separately declared terms rather than hidden inside an arbitrary score.

For a deterministic binary candidate family with uniform prior, an action that splits candidates evenly yields the maximum one-bit information gain. An action on which all candidates agree has zero information gain.

## 4. Decision states

- SELECTED: a permitted action has positive expected information gain and fits the remaining budget.
- NO_DISCRIMINATING_ACTION: every permitted action has zero expected information gain.
- BUDGET_EXHAUSTED: no action fits the remaining acquisition budget.
- INVALID_ACTION_SET: action schema, costs, or predicted outcome support is invalid.

If several actions tie within a preregistered tolerance, use a deterministic tie-break based on lower cost and then canonical action ID. Do not invent a preference from hidden truth.

After the environment returns an observation, update candidate weights using only that observation. If all candidates assign zero likelihood, return INCONSISTENT; do not silently add a new candidate after seeing the outcome. Candidate expansion must be a separate, versioned proposal event.

## 5. Measurement versus intervention

E12-A2 is split into two tracks:

### A2-M: passive measurement selection
The learner chooses which available channel, location, time, or input value to measure. The environment is not deliberately changed. Claims are limited to predictive discrimination under the declared observation process.

### A2-I: intervention selection
The learner chooses an action that changes the environment. This requires a causal data-generating protocol, action authorization, treatment assignment, and outcome measurement. Observational agreement alone cannot establish causal direction. The benchmark must distinguish randomized interventions from passive observations.

A2-M should pass before A2-I is implemented.

## 6. Benchmark construction

Create paired synthetic worlds whose candidate mechanisms agree on existing Support but disagree on some available measurements.

For each episode:
1. Generate a hidden world and candidate grammar outside the learner process.
2. Provide learner-visible Support and permitted action descriptions.
3. Ensure at least one episode family has a discriminating action.
4. Include a family where all permitted actions are observationally equivalent.
5. Include noisy outcomes and non-uniform prior arms only after the deterministic baseline.
6. Reveal action outcomes through the environment interface, never by passing evaluator truth to the learner.
7. Keep locked Test inaccessible until the action policy and candidate set are frozen.

The learner must be ambiguous before a discriminating observation is acquired, then update only after the environment reveals the result.

## 7. Baselines and ablations

Compare under equal action and compute budgets:
- random permitted action;
- fixed canonical action;
- maximum raw disagreement;
- expected information gain without cost;
- cost-normalized expected information gain;
- exact optimal action on tiny candidate spaces;
- oracle action policy only as an upper-bound diagnostic.

Ablate prior calibration, outcome noise, action cost, and candidate multiplicity. Add deliberately misleading candidate priors to test whether the policy becomes overconfident.

## 8. Metrics

- expected and realized entropy reduction;
- number of measurements to unique identification;
- total acquisition cost;
- identification accuracy on identifiable episodes;
- ambiguity retention on non-identifiable episodes;
- false identification rate;
- no-discriminating-action precision;
- budget-exhaustion rate;
- calibration of candidate posterior probabilities;
- regret against the exact optimal policy on tiny tasks.

Aggregate uncertainty at the independent world/episode level, not by treating correlated observations as independent samples.

## 9. Falsification

The proposed policy is not useful if:
- it fails to outperform random or fixed action selection at equal cost;
- it selects actions with no measurable expected discrimination;
- its posterior becomes overconfident under noisy or misleading priors;
- it claims identification when all permitted actions are equivalent;
- gains disappear on held-out world families;
- action selection relies on evaluator truth or locked Test leakage.

## 10. Yijing-inspired hypotheses

Only after the generic information-gain controller works, test whether structured state partitions or transition priors improve action selection.

Compare:
- no symbolic prior;
- Yin/Yang complementary partition prior;
- four-state coarse partition prior;
- trigram-factorized state prior;
- capacity-matched generic learned partition;
- deliberately permuted or incorrect symbolic prior.

Evaluate sample efficiency, cost, calibration, and OOD transfer. The symbolic prior must be rejectable and must not alter the evaluator's ground truth.

## 11. Implementation contract

The first implementation should be a small deterministic selector over finite hypotheses and finite permitted probes:
- pure function from candidate predictions, priors, action costs, and remaining budget to a selected action or explicit abstention state;
- exact entropy calculation;
- no environment truth parameter;
- separate environment-side observation reveal;
- immutable action and observation records;
- tests for equal split, zero-information actions, cost trade-offs, tie-breaking, budget exhaustion, impossible observations, and truth-mutation invariance.

Do not integrate interventions, neural scoring, or Yijing priors in this first implementation. Establish the generic decision rule and its controls first.
