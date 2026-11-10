# E12-A3 Integration Review: Proposal Portfolio and Sparse Composition

Date: 2026-11-11  
Status: architecture review; no integration merge performed

## 1. Two complementary research tracks

The repository currently contains two distinct E12-A3 implementation directions:

- **Proposal portfolio**: `prototype/e12a3_multi_proposer.py` on `research/e12a3-proposer-competition-2026-11-11`. It compares heterogeneous primitive proposal families under a shared proposal-slot budget.
- **Sparse composition induction**: `prototype/e12a3_compositional_induction.py` on `research/e12a3-m0-composition-engine-2026-11-11`. It composes E12-A1 typed predicates into bounded Boolean expressions, including non-contiguous sparse combinations such as A+C+E.

These solve different problems and should not be collapsed into one module:
- proposal portfolio asks **where candidate primitives come from**;
- composition induction asks **how existing primitives combine into higher-order concepts**.

## 2. Recommended unified architecture

Use a two-level candidate system:

1. Primitive proposal portfolio:
   - statistical;
   - temporal;
   - relational;
   - contrastive;
   - random;
   - bounded exhaustive;
   - later, Yijing-inspired proposal priors.

2. Composition proposal portfolio:
   - unary and binary Boolean operators;
   - bounded sparse n-ary operators;
   - typed role/relation operators;
   - later, learned composition templates.

Both emit a shared CandidateEnvelope containing:
- stable candidate ID;
- candidate kind: PRIMITIVE or COMPOSITION;
- canonical expression/DAG;
- input/output type signature;
- proposer family and version;
- source observation and parent candidate IDs;
- grammar version;
- proposal cost and measured evaluation cost;
- declared domain and uncertainty.

The global coordinator allocates a single total budget across both levels. Composition candidates must pay for their primitive dependencies and their own evaluation. Otherwise the composition path receives unpriced free computation.

## 3. Important review issue in the composition branch

The current composition branch's CI run reported an AttributeError in candidate ordering: `_candidate_order` accesses `.depth` on a base A1 Predicate, but Predicate exposes `.complexity` and has no `.depth` property.

The branch owner fixed candidate ordering by treating an A1 Predicate as a depth-zero leaf and reading .depth only from Expr. The subsequent full repository CI run passed on commit `d888c3ec9a7ad37d949646f6f7a1ae26e3b30c2e`.

This is a review finding and validation record, not a patch to that branch. The composition branch remains separate so the proposal portfolio and composition induction can be evaluated independently before integration.

## 4. Proposal portfolio validation status

The multi-proposer branch passed the full repository workflow on commit `55cd2ca7fc4d72e729df83fc3003398c09295be1` (run `42870394169`). The run includes all E12-A3 tests, smoke execution, the 20-seed benchmark, and the repository's existing E01/E02 experiment steps.

The exact-budget benchmark uses 31 proposal slots per method, Support exact-consistency screening, Gate selection, and evaluator-side Locked Test scoring. The equal-share PORTFOLIO achieved 27.5% selection coverage, below RELATIONAL (42.5%) and BOUNDED_ENUM (35.0%). This is a negative result for fixed round-robin allocation; see `docs/E12A3_M0_BENCHMARK_RESULTS_2026-11-11.md`.

CPU operations and wall-clock time are not yet matched. The benchmark does not establish generalization beyond two synthetic task families.

## 5. Integration gates

Before merging the tracks:
1. Repair and validate the composition branch independently.
2. Define one shared candidate envelope and canonical AST schema.
3. Preserve syntactic identity separately from empirical equivalence.
4. Account for dependency cost and expression evaluation cost.
5. Use one global proposal/evaluation budget.
6. Keep evaluator truth and Locked Test behind a process boundary.
7. Compare primitive-only, composition-only, and combined portfolios on the same held-out world families.
8. Include random, fixed, bounded exhaustive, and decision-tree baselines.

## 6. Research conclusion

The strongest current direction is not a single proposer that tries to do everything. It is a hierarchical search system: diverse mechanisms propose primitives; a separate bounded composition engine builds higher-order structures; a coordinator assigns scarce compute; and an evidence registry decides which structures survive.

This remains a research architecture. No claim of general concept discovery or superiority over existing models is made.
