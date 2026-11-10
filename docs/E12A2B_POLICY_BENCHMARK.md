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
6. exact_optimal: finite-horizon dynamic programming minimizing expected terminal posterior entropy under the same action set and budget.

For deterministic measurements, expected information gain equals the entropy of the predicted outcome distribution. Gini disagreement is a distinct objective and can rank multi-outcome partitions differently.

## Metrics

- Identification rate: fraction of episodes ending with one surviving hypothesis.
- Mean residual entropy: uncertainty remaining after the budget is spent or no informative action remains.
- Mean posterior MAP confidence: reciprocal of the surviving version-space size under the uniform prior.
- Mean cost and number of measurements.

The exact-optimal policy is an oracle only over the declared finite hypothesis/action space. It is a reference bound, not a deployable general-purpose learner.

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
- Report all three world families, not only the family most favorable to a policy.
- Compare policies at the same action set and budget. Report residual entropy alongside identification rate so abstention or partial identification is not hidden.
- Do not infer a Yijing-specific advantage: this benchmark contains no Yijing encoding.

## Next steps

1. Run the full seed sweep and record exact JSON output and commit SHA.
2. Add noisy observation channels and prior-misspecification stress tests.
3. Add held-out compositional action families and capacity-matched symbolic partition priors.
4. Only then compare Yin/Yang, four-image, trigram, hexagram, or five-phase structured priors against random and permuted controls.
