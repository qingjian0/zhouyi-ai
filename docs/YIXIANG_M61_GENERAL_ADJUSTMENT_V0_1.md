# M61 — Graph-theoretic back-door adjustment v0.1

Status: implemented on the M61 research branch; exact-head CI pending.

## Objective

Replace the M60 direct-parent heuristic with a checkable implementation of the sufficient back-door criterion for a fully specified DAG. The goal is not to claim general causal identification. It is to determine whether a proposed observed covariate set is valid for back-door adjustment under the supplied graph.

## Algorithm

Given treatment X, outcome Y, observed variables O, and DAG G:

1. Validate unique node names, valid endpoints, unique edges, and acyclicity.
2. Construct the back-door graph by deleting every outgoing edge from X.
3. Exclude X, Y, hidden nodes, and descendants of X from candidate adjustment variables.
4. Enumerate candidate observed sets by increasing cardinality.
5. For each candidate Z, form the ancestral subgraph of {X,Y} union Z in the back-door graph; moralize it by marrying co-parents; remove Z; test whether X and Y are disconnected.
6. Select the first valid set, yielding a minimum-cardinality observed set under the enumeration order.
7. If no candidate passes, return not_identified_by_backdoor. This is not a statement that the effect is globally non-identifiable.

The current implementation caps exhaustive candidate search at 18 eligible observed variables. Exceeding this cap returns an explicit search-budget result rather than silently approximating.

## Correctness diagnostics

The focused suite covers:
- Chain and fork: conditioning on the middle node blocks dependence.
- Collider: marginally blocked, opened by conditioning on the collider.
- Observed common cause: recover the minimum adjustment set.
- Mediator: excluded from total-effect adjustment because it is a treatment descendant.
- Hidden common cause: no observed back-door set is available, so the system declines a back-door claim.
- Cyclic input: rejected rather than processed as a DAG.
- Domain renaming: the graph solution is invariant to variable labels.

## Output semantics

- identified_by_backdoor: a valid back-door set was found and the exact-distribution adjustment estimate was computed.
- not_identified_by_backdoor: no observed adjustment set passed the sufficient back-door criterion.
- backdoor_estimation_failed: the criterion passed but the observed distribution did not support the required stratum estimate.
- estimate_only: a numerical observational contrast was computed without an identification proof.
- unvalidated_adjustment: a numerical adjusted contrast was computed without validating the proposed all-observed set.

Metrics separate back-door criterion classification accuracy from MAE on back-door-identified cases. They do not score global identifiability, front-door, IV, or general do-calculus.

## Known limitations

- Fully specified DAG is assumed; no CPDAG/PAG uncertainty or latent projection is handled.
- The method only searches back-door adjustment sets; it does not implement front-door, instrumental variables, or complete do-calculus.
- Exhaustive subset enumeration is bounded and is not designed for large covariate sets.
- Exact joint distributions eliminate finite-sample uncertainty and positivity estimation problems; later work must add sampling, noise, uncertainty, and sensitivity analysis.
- The synthetic generator's hidden causal equations remain evaluator-side. This does not establish causal claims for classical yixiang text.

## Research design implications

CausalReasoningBenchmark (2026) motivates scoring identification specifications separately from numerical estimates. CausalPitfalls (ICLR 2026) motivates explicit selection-bias and collider controls. Recent work on causal-estimator hyperparameter tuning warns that no single proxy metric is uniformly reliable across scenarios. Therefore, later comparisons should report identification strategy, control set, bad-control violations, estimation error, uncertainty, and abstention separately.

## References

- https://arxiv.org/abs/2602.20571
- https://proceedings.iclr.cc/paper_files/paper/2026/hash/9235c376df778f1aaf486a882afb7471-Abstract-Conference.html
- https://link.springer.com/article/10.1007/s10994-026-07140-9
- https://proceedings.mlr.press/v286/vassimon-manela25a.html
