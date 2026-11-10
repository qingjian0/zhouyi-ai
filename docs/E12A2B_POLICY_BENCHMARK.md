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

The CI sweep used 5 seeds per family, budget 4, and 8 exhaustive targets per world (720 policy-episodes total). Pooled results:

| Policy | Identification rate | Mean residual entropy (bits) | Mean cost |
|---|---:|---:|---:|
| Random | 0.4583 | 0.6099 | 3.0833 |
| Fixed | 0.3417 | 0.7022 | 2.7500 |
| Max disagreement | 0.8250 | 0.1896 | 3.3417 |
| Expected IG | 0.8250 | 0.1896 | 3.3250 |
| Cost-normalized IG | 0.5250 | 0.5189 | 2.8083 |
| Exact optimal | 0.8583 | 0.1563 | 3.5750 |

This is one small synthetic sweep, not a general performance claim. The pooled summary hides interactions between policy and world family; `family_summary` was added so future runs can report those interactions directly. The two-step lookahead policy was added after this snapshot and has not yet been measured in this run.

Family-level identification rates from the same CI JSON:

| World family | Random | Fixed | Max disagreement | Expected IG | Cost-normalized IG | Exact optimal |
|---|---:|---:|---:|---:|---:|---:|
| Balanced | 47.5% | 40.0% | 80.0% | 80.0% | 85.0% | 90.0% |
| Skewed | 60.0% | 57.5% | 67.5% | 67.5% | 67.5% | 67.5% |
| Redundant | 30.0% | 5.0% | 100.0% | 100.0% | 5.0% | 100.0% |

In the redundant family, Expected IG and max disagreement select the expensive direct-identification action and identify every target within budget. Cost-normalized IG instead spends budget on cheaper partial measurements and identifies only 5% of targets. In the balanced family, cost-normalized IG is competitive and reaches 85%; in the skewed family, all informed strategies tie. Thus, cost normalization is not uniformly good or bad: it interacts strongly with the structure of the available action set. This is the main reason the benchmark now reports per-family outcomes rather than only pooled averages. The Run #360 full workflow completed successfully.

## Next steps

1. Run the full seed sweep and record exact JSON output and commit SHA.
2. Compare one-step greedy, cost-normalized greedy, two-step lookahead, and exact finite-horizon planning on the same worlds; add three-step lookahead only if the runtime/quality trade-off is justified.
3. Add noisy observation channels and prior-misspecification stress tests.
4. Add held-out compositional action families and capacity-matched symbolic partition priors.
5. Only then compare Yin/Yang, four-image, trigram, hexagram, or five-phase structured priors against random and permuted controls.
