# CPG-EI active-query discovery

## Question

Does choosing the next training state by disagreement among surviving finite-rule
hypotheses reduce the number of oracle queries needed to identify a relation,
compared with a deterministic random-query control?

## Protocol

- Reuse the fixed mixed-operator corpus and candidate grammar from the symbolic
  discovery baseline.
- Each family/output starts with the same complete candidate grammar.
- Query pool contains only that output's training-state partition.
- Active acquisition chooses the unqueried state that most evenly divides the
  distinct surviving prediction patterns. Semantic prediction patterns, rather
  than raw rule aliases, determine disagreement weights.
- Random control queries a seeded permutation of the same training pool.
- Both methods use the same query budgets and oracle labels.
- Development labels only break ties after query acquisition.
- Locked labels are report-only.
- Teacher manifests are consulted only after selection for post-hoc scoring.
- Query traces, version-space sizes, structural hypothesis counts, function
  recovery, operator recovery, exact-rule recovery, and locked accuracy are
  reported per output and aggregated by budget.

## Query policy

For binary outputs, maximum predictive entropy is equivalent to choosing a
query with the most balanced 0/1 split among the surviving distinct prediction
patterns. The implementation uses bit-sliced population counting over packed
integer patterns to avoid a Python loop over every hypothesis for every state.

If all surviving hypotheses agree on every remaining training state, active
acquisition stops and reports the smaller effective query count. This exposes
a query-pool identifiability limit rather than issuing uninformative queries.

## Leakage boundaries

- Training labels alone select queries and filter the version space.
- Development labels only break ties among surviving candidates after acquisition.
- Locked labels never affect query traces or selected rules.
- Teacher manifests never affect query selection or candidate filtering.

## Interpretation boundary

This is active finite-hypothesis search over a declared synthetic Boolean rule
grammar. It measures within-family active querying, not zero-shot family
transfer, cross-family meta-learning, causal discovery, open-world induction,
Yi-Xue understanding, natural-language reasoning, or Transformer superiority.
