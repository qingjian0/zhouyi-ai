# M60 — Causal intervention and transfer controls v0.1

Status: executable exact-distribution synthetic diagnostic; not empirical causal discovery.

## Methodological anchors

- Hernán & Robins, Causal Inference: What If (2020; current online edition): defines causal effects through interventions and treats confounding, backdoor adjustment, selection bias, and mediation as distinct problems. The M60 cases mirror these distinctions, but use exact synthetic distributions rather than empirical study data.
- Peters, Janzing & Schölkopf, Elements of Causal Inference (MIT Press, 2017): develops structural causal models, intervention distributions, hidden variables, and domain adaptation. This motivates separating the graph, observational distribution, and evaluator-only intervention truth.

## Research question

Does a system distinguish observational association from intervention, preserve total effects through mediators, avoid conditioning on colliders, and abstain when latent confounding makes the effect non-identifiable from the available evidence?

## Implemented SCM cases

1. Observed confounder: U causes both X and Y, while X also causes Y. The naive observational difference is biased; adjustment for U recovers the exact total effect.
2. Mediation: X causes M, which causes Y, and X also has a direct effect on Y. The total effect must not adjust away M.
3. Collider: X and Y independently cause C. Conditioning on C induces a spurious association; C is not a valid adjustment variable.
4. Latent confounder: an unobserved L causes both X and Y. The graph-aware baseline must abstain rather than report an observational association as a causal effect.

## Baselines and metrics

- Naive observational difference.
- Adjust for every observed non-exposure/non-outcome variable (deliberately unsafe baseline).
- Graph-aware direct-parent backdoor adjustment, with explicit abstention for latent exposure parents.
- Metrics: identification accuracy, MAE on identifiable cases, and number of identified cases scored.

The public case exposes a DAG and exact observed joint distribution. Structural equations and true intervention effects are evaluator-only. The current graph routine is intentionally scoped to the tested direct-parent backdoor subset; it is not a complete do-calculus or generalized adjustment implementation.

## Interpretation boundary

This benchmark validates causal-estimation distinctions under known synthetic SCM assumptions. It does not infer causal graphs from classical texts, establish that a traditional yixiang relation is causal, model hidden cultural mechanisms, or prove transfer to real domains. Exact distributions also remove finite-sample estimation uncertainty; later versions must add sample-size sweeps, noise, graph uncertainty, and independently authored domain cases.

## Next gates

1. Add randomized-intervention and observational-only variants with matched sample sizes.
2. Add graph-structure uncertainty and multiple valid/invalid adjustment sets.
3. Add counterfactual queries with explicit structural-equation assumptions; do not score individual counterfactuals from observational marginals alone.
4. Add domain-renamed transfer pairs and held-out mechanism families.
5. Link claims to M59 source witnesses before any classical-text causal annotation enters a gold set.
