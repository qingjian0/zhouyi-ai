# E12-A2-B — Active Measurement Policy Benchmark

Status: benchmark implementation committed; quantitative results are produced by CI and must be recorded against the exact commit/run before making performance claims.

## Research question

Does selecting measurements by expected information gain improve identification efficiency over random, fixed, or disagreement-only selection? Does dividing information gain by acquisition cost improve information gained under a constrained budget? How close do these policies come to the exact finite-horizon optimum?

## Experimental unit

Each world contains eight candidate hypotheses and a public finite set of deterministic categorical measurement actions. A hidden target hypothesis is selected uniformly for each episode. Every target in each world is evaluated exhaustively, avoiding Monte Carlo sampling error over target identity.

Policies receive only:
- the current version space (hypotheses still consistent with observations);
- each permitted action's public outcome prediction for every candidate;
- action cost and remaining budget.

The hidden target index is used only by the environment to reveal the selected action's observed outcome. It is not an argument to the policy selector.

## World families

- balanced: binary near-even partitions plus a multi-outcome partition.
- skewed: partitions with uneven class sizes and a rare-outcome three-way measurement.
- redundant: duplicate, correlated, refining, and expensive direct-identification measurements.

Seeds vary the assignments of hypotheses to outcome classes. The same world and hidden target are evaluated under every policy.

## Policies

1. random: random informative affordable action.
2. fixed: lexicographically first informative affordable action.
3. max_disagreement: maximize pairwise outcome disagreement (Gini impurity).
4. expected_ig: maximize expected posterior entropy reduction in bits.
5. cost_normalized_ig: maximize expected information gain divided by measurement cost.
6. lookahead_2: two-step receding-horizon planning; it chooses the first action minimizing expected terminal entropy after the best affordable second action, without access to the hidden target.
7. exact_optimal: finite-horizon dynamic programming minimizing expected terminal posterior entropy under the same action set and budget.

For deterministic measurements, expected information gain equals the entropy of the predicted outcome distribution. Gini disagreement is a distinct objective and can rank multi-outcome partitions differently.

## Metrics

- Identification rate: fraction of episodes ending with one surviving hypothesis.
- Mean residual entropy: uncertainty remaining after the budget is spent or no informative action remains.
- Mean posterior MAP confidence: reciprocal of the surviving version-space size under the uniform prior.
- Mean cost and number of measurements.

The two-step policy is a bounded planning baseline: it can preserve budget for complementary measurements but can miss plans requiring three or more steps. The exact-optimal policy is an oracle only over the declared finite hypothesis/action space. It is a reference bound, not a deployable general-purpose learner.

## Running

```bash
python -m unittest tests.test_e12a2b_policy_benchmark -v
python -m prototype.e12a2b_policy_benchmark --seeds 20 --budget 4 --start-seed 100 --json
```

CI runs a smaller deterministic sweep to keep feedback time bounded. The full sweep should be run separately for final reporting.

## Interpretation safeguards

- Do not call this a natural-world, language, causal, or neural architecture benchmark.
- The action prediction tables are supplied to all policies; autonomous action-model learning is not evaluated.
- The current protocol uses uniform priors and deterministic observations. Noisy observations and prior misspecification are separate follow-up experiments.
- Report all three world families, not only the family most favorable to a policy. The benchmark JSON now includes `family_summary` in addition to the pooled `summary`; each family-policy cell contains all eight targets per seed.
- Compare policies at the same action set and budget. Report residual entropy alongside identification rate so abstention or partial identification is not hidden.
- Do not infer a Yijing-specific advantage: this benchmark contains no Yijing encoding.

## CI result snapshot (Run #360, commit 7206be86)

The initial six-policy CI sweep used 5 seeds per family, budget 4, and 8 exhaustive targets per world (720 policy-episodes). Its results are retained in GitHub Actions Run #360 for historical comparison.

## Seven-policy result snapshot (Run #42871598695, commit 8ad5dc38)

The seven-policy sweep used 5 seeds per family, budget 4, and 8 exhaustive targets per world (840 policy-episodes).

Pooled results:

| Policy | Identification rate | Mean residual entropy (bits) | Mean cost |
|---|---:|---:|---:|
| Random | 45.83% | 0.6099 | 3.0833 |
| Fixed | 34.17% | 0.7022 | 2.7500 |
| Max disagreement | 82.50% | 0.1896 | 3.3417 |
| Expected IG | 82.50% | 0.1896 | 3.3250 |
| Cost-normalized IG | 52.50% | 0.5189 | 2.8083 |
| Two-step lookahead | 80.83% | 0.2063 | 3.4583 |
| Exact optimal | 85.83% | 0.1563 | 3.5750 |

Family-level identification rates:

| World family | Random | Fixed | Max disagreement | Expected IG | Cost-normalized IG | Two-step lookahead | Exact optimal |
|---|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 47.5% | 40.0% | 80.0% | 80.0% | 85.0% | 75.0% | 90.0% |
| Skewed | 60.0% | 57.5% | 67.5% | 67.5% | 67.5% | 67.5% | 67.5% |
| Redundant | 30.0% | 5.0% | 100.0% | 100.0% | 5.0% | 100.0% | 100.0% |

Interpretation:

- Two-step lookahead solves the constructed complementary-measurement case and matches exact optimal on the redundant family, but it does not improve the pooled score over one-step Expected IG. It is worse on the balanced family (75% vs 80%) and ties on skewed and redundant families.
- This is not a contradiction: bounded lookahead optimizes a two-action horizon and can miss globally better sequences or be affected by deterministic tie-breaking. It is a useful intermediate planning baseline, not a generally superior policy.
- Expected IG and max disagreement reach 100% on the redundant family by selecting the direct-identification action. Cost-normalized IG reaches only 5% because it prefers cheap partial measurements that consume the budget.
- Exact optimal remains the finite-action oracle reference and is not a deployable general-purpose learner.

The seven-policy Run #42871598695 full workflow completed successfully. These are small synthetic results, not general claims about natural cognition, language, causality, or Yijing-specific priors.

## Next steps

1. Run the full seed sweep and record exact JSON output and commit SHA.
2. Compare one-step greedy, cost-normalized greedy, two-step lookahead, and exact finite-horizon planning on the same worlds; add three-step lookahead only if the runtime/quality trade-off is justified.
3. Add noisy observation channels and prior-misspecification stress tests.
4. Add held-out compositional action families and capacity-matched symbolic partition priors.
5. Only then compare Yin/Yang, four-image, trigram, hexagram, or five-phase structured priors against random and permuted controls.
