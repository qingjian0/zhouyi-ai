# M60 — Causal intervention and transfer controls v0.1

Status: executable exact-distribution synthetic diagnostic; not empirical causal discovery.

## Methodological anchors

- Hernán & Robins, Causal Inference: What If (2020; current online edition): defines causal effects through interventions and treats confounding, backdoor adjustment, selection bias, and mediation as distinct problems. The M60 cases mirror these distinctions, but use exact synthetic distributions rather than empirical study data.
- Peters, Janzing & Schölkopf, Elements of Causal Inference (MIT Press, 2017): develops structural causal models, intervention distributions, hidden variables, and domain adaptation. This motivates separating the graph, observational distribution, and evaluator-only intervention truth.

## Research question

Does a system distinguish observational association from intervention, preserve total effects through mediators, avoid conditioning on colliders, and abstain from a back-door identification claim when no valid observed adjustment set is available?

## Implemented SCM cases

1. Observed confounder: U causes both X and Y, while X also causes Y. The naive observational difference is biased; adjustment for U recovers the exact total effect.
2. Mediation: X causes M, which causes Y, and X also has a direct effect on Y. The total effect must not adjust away M.
3. Collider: X and Y independently cause C. Conditioning on C induces a spurious association; C is not a valid adjustment variable.
4. Latent confounder: an unobserved L causes both X and Y. The graph-aware baseline must abstain from claiming a back-door-identified effect rather than report an observational association as a causal effect.

## Baselines and metrics

- Naive observational difference.
- Adjust for every observed non-exposure/non-outcome variable (deliberately unsafe baseline).
- Graph-aware minimum adjustment-set search using ancestral moralization and d-separation in the back-door graph; hidden variables remain in the graph but cannot be selected as observed controls.
- A domain-renaming control verifies that the inferred causal mapping does not depend on variable names.
- Metrics: back-door criterion accuracy, MAE on cases identified by the back-door criterion, and number of such cases scored.

The public case exposes a DAG and exact observed joint distribution. Structural equations and true intervention effects are evaluator-only. The graph routine validates DAG acyclicity, searches observed, non-descendant adjustment sets and validates them using the sufficient back-door criterion via d-separation. It is still not a complete do-calculus, generalized adjustment, front-door, IV, or latent-projection identification implementation.

## Interpretation boundary

This benchmark validates causal-estimation distinctions under known synthetic SCM assumptions. It does not infer causal graphs from classical texts, establish that a traditional yixiang relation is causal, model hidden cultural mechanisms, or prove transfer to real domains. Exact distributions also remove finite-sample estimation uncertainty; later versions must add sample-size sweeps, noise, graph uncertainty, and independently authored domain cases.

## M61 extension

The follow-on M61 branch replaces the hard-coded direct-parent heuristic with a graph-theoretic search: construct the back-door graph by removing outgoing treatment edges; moralize the ancestral subgraph of treatment, outcome, and candidate controls; then test separation after conditioning. The minimum-cardinality valid observed set is selected. If no observed set blocks the back-door paths, the system abstains from a back-door claim; it does not infer global non-identifiability, since front-door, IV, and other strategies are outside this implementation. Tests cover chains, forks, colliders, mediation, observed confounding, hidden common causes, and cyclic-graph rejection.

## Next gates

1. Add randomized-intervention and observational-only variants with matched sample sizes.
2. Add graph-structure uncertainty and multiple valid/invalid adjustment sets.
3. Add counterfactual queries with explicit structural-equation assumptions; do not score individual counterfactuals from observational marginals alone.
4. Add domain-renamed transfer pairs and held-out mechanism families.
5. Link claims to M59 source witnesses before any classical-text causal annotation enters a gold set.


## Recent benchmark design implications

- CausalReasoningBenchmark (Sawarni, Tan & Syrgkanis, 2026) separates causal identification specifications from numerical effect estimation. M60/M61 should therefore report the proposed strategy and control set separately from estimation error; a correct number alone is insufficient evidence of correct causal reasoning.
- CausalPitfalls (ICLR 2026) explicitly tests Simpson's paradox, selection bias, and related statistical pitfalls under direct and code-assisted protocols. The existing collider and confounding cases are a starting subset, not a complete coverage claim.
- Machlanski, Samothrakis & Clarke (2026) report that causal estimator model-selection metrics can be inconsistent across scenarios. Future finite-sample comparisons must avoid tuning solely on one proxy metric and must report sensitivity across estimands and data regimes.

These findings motivate a separate identification-specification score, estimation score, abstention calibration, and scenario-wise reporting. They do not imply that the synthetic M60/M61 results establish real-world causal competence.


## Selected 2026 references

- Sawarni, Tan & Syrgkanis, *CausalReasoningBenchmark: A Real-World Benchmark for Disentangled Evaluation of Causal Identification and Estimation* (2026): https://arxiv.org/abs/2602.20571
- Du et al., *Ice Cream Doesn't Cause Drowning: Benchmarking LLMs Against Statistical Pitfalls in Causal Inference* (ICLR 2026): https://proceedings.iclr.cc/paper_files/paper/2026/hash/9235c376df778f1aaf486a882afb7471-Abstract-Conference.html
- Machlanski, Samothrakis & Clarke, *The Challenges of Hyperparameter Tuning for Accurate Causal Effect Estimation* (Machine Learning, 2026): https://link.springer.com/article/10.1007/s10994-026-07140-9
- de Vassimon Manela, Yang & Evans, *Testing Generalizability in Causal Inference* (UAI 2025): https://proceedings.mlr.press/v286/vassimon-manela25a.html
