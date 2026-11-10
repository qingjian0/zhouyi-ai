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

The fix should make candidate depth explicit for both variants, e.g. depth 0 for a Predicate and Expr.depth for an expression. Then rerun the complete repository test suite, not only the new test file.

This is a review finding, not a patch to that branch. The composition branch remains separate pending its own repair and validation.

## 4. Proposal portfolio validation status

The multi-proposer branch has a passing full unit-test step and passing A3-specific benchmark-test and smoke-test steps on commit `b11592038e0cd6bc01b36608b209bbc450110a13`.

The subsequent 20-seed equal-budget benchmark step also completed successfully on the later branch run. The complete repository workflow was still running at the time of this record; do not label the whole workflow successful until all legacy experiment steps finish.

The benchmark uses equal proposal slots, Support exact-consistency screening, Gate selection, and evaluator-side Locked Test scoring. It does not yet match CPU operations or wall-clock time.

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
