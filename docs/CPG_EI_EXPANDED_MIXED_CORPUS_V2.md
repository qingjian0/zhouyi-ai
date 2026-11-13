# CPG-EI Expanded Mixed-Operator Corpus v2

## Purpose

Increase independent teacher-family diversity by at least 4x without changing the
v1 rule semantics or silently changing the state-space definition.

## Target configuration

| Property | v1 reference | v2 target |
|---|---:|---:|
| Independent teacher families | 400 | 1,600 |
| Input bits | 8 | 8 |
| Output rules per family | 8 | 8 |
| Exhaustive states per family | 256 | 256 |
| Total teacher-state rows | 102,400 | 409,600 |
| Teacher rules | 3,200 | 12,800 |

The expansion is on independent teacher families, not a larger per-family state
space. Every family still has a complete 8-bit Boolean state table.

## Diversity and split controls

- Retains the seven typed operators: XOR, AND, OR, NAND, ordered implication,
  threshold, and context-gated XOR.
- Retains deterministic round-robin operator assignment across output rules.
- Uses independent deterministic family seeds and a separate family-split seed.
- Each family has disjoint train, development, and locked state partitions.
- Family-level train/development/locked strata are recorded separately from
  within-family state splits. A locked-family stratum is **not** zero-shot transfer
  while the learner is still fitted independently on that family's train states.
- Teacher digests, split counts, operator counts, corpus digest, and generator
  configuration are included in the manifest.

## Validation

The focused test suite checks deterministic generation, teacher uniqueness,
operator balance, expansion metadata, and the minimum supported scale.
The CI workflow generates the full 1,600-family / 409,600-row artifact and
checks manifest counts before upload.

## Claim boundary

This is a larger synthetic data artifact. It does not demonstrate that a model
can learn across families, discover arbitrary relation operators, understand
Yi-Xue concepts, reason in natural language, or outperform Transformers.
A separate task-conditioned learner and genuinely held-out-family protocol are
required for those claims.
