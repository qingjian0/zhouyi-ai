# E12-M2.1 — Degree-preserving null model and motif significance

## Research question

Does a candidate co-occurrence motif carry association information beyond what is
explained by the observed transaction sizes and singleton item frequencies?

The E12-M2 discovery score uses an independence lift. That score is useful for
ranking, but it is not a significance test and can be biased by heterogeneous
row sizes, item marginals, and candidate selection.

## Null model

Represent observations as a bipartite graph:

- left vertices: observation/transaction rows;
- right vertices: discrete symbols/items;
- edges: item membership in a row.

A valid 2-switch takes edges `(r1, i1)` and `(r2, i2)`, where rows and items
are distinct and both cross edges are absent, then replaces them with
`(r1, i2)` and `(r2, i1)`.

This preserves exactly:

1. every row's number of items;
2. every item's marginal frequency;
3. the total number of incidences.

It randomizes association structure while conditioning on those margins.

## Statistics

For a pre-specified candidate motif, calculate the same score used by E12-M2
on the observed graph and each randomized graph. The one-sided empirical
Monte Carlo p-value is:

`p = (1 + count(null_score >= observed_score)) / (B + 1)`

The implementation also reports a max-statistic p-value. For each null graph,
it finds the maximum score across all item combinations up to `max_order`,
then compares that maximum with the observed candidate score. This is a
conservative family-wise correction for selecting a motif after searching
many candidates.

## Mixing and diagnostics

The implementation reports attempted and accepted switches and the acceptance
rate. A low acceptance rate or a graph with no legal switches indicates that
the null chain may not explore the conditional state space adequately.
The current prototype does not claim a formal mixing-time guarantee. Results
must be interpreted alongside acceptance rate, multiple seeds, and longer
chains. For production research, add trace autocorrelation and independent
chain diagnostics.

## Required next experiments

- Sweep seeds and report median/range of p-values and acceptance rates.
- Vary swaps-per-edge and test stability of null distributions.
- Compare planted motifs against degree-preserving nulls and marginal-matched
  negative controls.
- Report both candidate-specific and max-statistic p-values.
- Test higher-order motifs, sparse graphs, disconnected components, and
  near-saturated rows.
- Compare runtime and memory against Apriori/FP-Growth and a brute-force oracle
  on small datasets.

## Interpretation boundary

A low p-value means the observed incidence pattern is unusual under this
specific degree-preserving null model. It does not establish causality,
semantics, human-like concepts, or transfer to unseen tasks. A high p-value
may reflect a weak motif, low sample size, or poor null-chain mixing.
