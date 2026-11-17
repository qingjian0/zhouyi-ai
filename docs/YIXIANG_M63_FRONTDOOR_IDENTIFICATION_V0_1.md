# M63 — Front-door identification beyond back-door adjustment v0.1

Status: implementation added; exact-head validation pending.

## Objective

Extend M61's graph-validated sufficient back-door criterion with a narrowly scoped single-observed-mediator front-door criterion. This is an additional identification route for some DAGs with unobserved treatment–outcome confounding. It is not a complete do-calculus implementation.

## Implemented criteria

For exposure X, outcome Y, and one observed candidate mediator M, the checker requires:

1. Every directed path from X to Y passes through M (no unmediated direct or alternate directed path).
2. X and M are d-separated in the graph with outgoing edges from X removed (no open back-door path from X to M).
3. M and Y are d-separated conditional on X in the graph with outgoing edges from M removed (X blocks all back-door paths from M to Y).

The graph is a fully specified DAG. Hidden nodes remain in the graph for d-separation but cannot be selected as observed mediators. The implementation currently handles one binary observed mediator; it does not search mediator sets or generalize to continuous/multivalued variables.

## Estimation

For binary X, M, and Y, the front-door functional is computed from the observed joint distribution:

P(Y=1 | do(X=x)) =
sum_m P(M=m | X=x) * sum_x' P(Y=1 | M=m, X=x') P(X=x').

The reported contrast is the difference between x=1 and x=0. Positivity failures return an estimation-failed status rather than silently imputing unsupported conditional cells.

## Strategy and abstention semantics

- `graph_backdoor` remains the strict M61 back-door-only comparator.
- `graph_identification` tries a valid back-door set first, then the single-mediator front-door criterion.
- `identified_by_frontdoor` means the supplied DAG satisfies the implemented front-door conditions and the observed-data functional was computable.
- `not_identified_by_implemented_criteria` means neither implemented sufficient criterion passed. It does **not** imply global non-identifiability.
- Back-door criterion accuracy remains separately reported. The new overall strategy metric is limited to the union of the implemented back-door and front-door criteria.

## Controlled cases

The synthetic suite adds:
- Latent common cause of X and Y, with X -> M -> Y as the complete causal path: front-door should identify the exact intervention effect.
- An additional direct X -> Y path: front-door must reject.
- An unobserved common cause of M and Y: front-door must reject.

These exact binary SCM cases test implementation logic only. They are not evidence that a classical yixiang claim is causal.

The evaluator now reports back-door criterion accuracy separately from combined implemented-strategy accuracy, and reports effect MAE separately for back-door-identified and combined back-door/front-door cases. This prevents front-door cases from being omitted from the new strategy's error score or incorrectly counted as back-door successes.

## Known limitations

- No instrumental-variable identification or estimation.
- No front-door mediator sets, proximal identification, general do-calculus, ID algorithm, PAG/CPDAG, or latent projection.
- No finite-sample estimator, confidence interval, bootstrap, cross-fitting, positivity diagnostics beyond missing-cell detection, or sensitivity analysis.
- Correctness is conditional on the supplied DAG and assumptions. The checker does not infer or validate the causal graph from observational data.
- A criterion pass is not evidence that the assumed graph is true.

## Research context

Recent work develops flexible nonparametric and targeted estimators under front-door assumptions, while 2026 work studies proximal extensions where mediator confounding is more general. These are separate estimation/identification advances and are not implemented here:
- https://academic.oup.com/jrsssb/advance-article-abstract/doi/10.1093/jrsssb/qkag122/8832505
- https://proceedings.mlr.press/v337/guo26c.html
- https://doi.org/10.1016/j.spl.2025.110561

The next required layer is finite-sample estimation and uncertainty under declared identification assumptions, followed by held-out source-grounded tasks. No overall Zhouyi-AI completion or empirical superiority claim is made.
