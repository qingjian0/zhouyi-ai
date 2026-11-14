# E12-A3-M0 — Bounded Sparse Composition Engine

Date: 2026-11-11  
Status: implementation committed; focused tests, smoke test, full unit-test discovery, and all repository benchmark workflow steps passed in GitHub Actions run #375.

## Files

- `prototype/e12a3_compositional_induction.py`
- `tests/test_e12a3_compositional_induction.py`

## What it implements

A deterministic symbolic baseline over E12-A1 typed predicates:

- unary NOT;
- binary AND, OR, XOR;
- bounded n-ary ALL_OF and ANY_OF;
- sparse feature selection, so a composition can use A,C,E and omit B,D;
- canonical keys for commutative operators;
- deterministic candidate ordering;
- bounded depth, arity, node complexity, and candidate count;
- Train consistency followed by independent Gate consistency;
- explicit IDENTIFIABLE, AMBIGUOUS, INCONSISTENT, and BUDGET_EXHAUSTED outcomes.

Nested depth-2 expressions combine disjoint feature supports in this first version. This deliberately limits the search space and avoids trivial repeated-feature constructions. It is not a complete Boolean algebra simplifier.

## Important implementation boundary

A1's predicate proposal can produce several structurally different predicates that agree on the observed values. A3 keeps these structurally distinct rather than silently collapsing them based on Train behavior. This is faithful to the identifiability requirement but can cause candidate-space growth.

When the candidate space exceeds the declared cap, the implementation returns BUDGET_EXHAUSTED and no selected candidate. It does not choose a winner from a truncated prefix.

The learner API receives only a LearnerView (schema, Train, Gate) and search configuration. It has no Test or evaluator-truth argument. The current implementation uses hard binary predicate outputs; uncertainty propagation from noisy predicates remains future work.

## Run

```bash
python -m unittest tests.test_e12a3_compositional_induction -v
python -m prototype.e12a3_compositional_induction
```

The CLI uses a conservative depth-1, arity-3 demo configuration to keep the example within a finite search budget. Depth-2 search is available through the API and must be budgeted explicitly.

## Tests included

- sparse A+C+E candidate proposal;
- semantic independence from distractors B and D;
- commutative canonicalization;
- deterministic output under primitive reordering;
- explicit candidate-budget exhaustion and abstention;
- rejection of type-invalid primitive evaluation;
- ambiguity preservation for observationally equivalent feature explanations;
- learner API has no Test/oracle-truth parameter.

## Limitations / next validation gates

1. The focused A3-M0 tests, CLI smoke test, full unit-test discovery, and all repository benchmark workflow steps passed in GitHub Actions run #375.
2. Candidate generation is exhaustive only within the declared finite grammar and caps.
3. The current baseline uses hard Boolean outputs and exact consistency; noisy predicates and probabilistic scoring are not implemented.
4. Nested compositions require disjoint feature supports, a conservative restriction to revisit in a separate ablation.
5. No baseline comparison or multi-seed benchmark has been run.
6. Next: run the complete repository test suite, add random/fixed/decision-tree baselines, measure candidate growth, then evaluate held-out composition families.
7. Only after the generic baseline is validated should Yijing-inspired priors be introduced.

Passing these tests would establish implementation behavior on the finite grammar, not general concept discovery or an advantage over existing architectures.
