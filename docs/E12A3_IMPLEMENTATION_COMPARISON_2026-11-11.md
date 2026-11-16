# E12-A3 Implementation Comparison and Integration Design

Date: 2026-11-11  
Status: architecture synthesis; no merged implementation or performance claim.

## 1. Why two A3 implementations exist

Two complementary research branches now contain A3 work:

- Direct composition engine: `research/e12a3-m0-composition-engine-2026-11-11`
- Multi-proposer portfolio: `research/e12a3-proposer-competition-2026-11-11`

They should not be treated as duplicate implementations. They solve different subproblems and should remain independently testable until a shared contract is agreed.

## 2. Capability comparison

| Capability | Direct composition engine | Multi-proposer portfolio |
|---|---|---|
| Input | E12-A1 typed predicates | typed observations |
| Main task | compose primitives into sparse Boolean expressions | generate heterogeneous candidate predicates |
| Proposal families | bounded symbolic grammar | STAT, RELATIONAL, RANDOM, EXHAUSTIVE |
| Non-contiguous A+C+E | direct n-ary composition | not yet implemented as a portfolio family in current code |
| Parallel candidate evaluation | deterministic finite enumeration, then batch filtering | multiple proposer pools and shared budget scheduler |
| Budget | candidate cap; abstains on overflow | equal allocation and round-robin proposal slots |
| Canonicalization | expression keys; commutative operator normalization | canonical predicate serialization |
| Empirical equivalence | not yet implemented as separate dataset-scoped relation | dataset-scoped behavior signatures |
| Lifecycle | not yet implemented | lifecycle transition records |
| Train/Gate | exact Train then Gate consistency | Support screening then Gate ranking |
| Locked Test | absent from learner API | evaluator-side one-time Test scoring in benchmark |
| Current validation | 93 repository unit tests and focused A3-M0 smoke passed in CI run #369; later full workflow pending | multi-proposer unit tests, smoke, 20-seed benchmark, and the complete repository workflow passed in CI run #374 |

## 3. Important distinction

The multi-proposer branch is currently the stronger portfolio/evidence-management baseline. It has explicit proposal families, budget allocation, empirical-equivalence grouping, and candidate lifecycle transitions.

The direct composition branch is currently the clearer baseline for the user's original sparse-combination requirement: choose non-adjacent primitives and combine them into higher-order expressions.

The current multi-proposer implementation does not yet implement the COMPOSITIONAL proposer family described in its protocol. It proposes atomic statistical, relational, random, and exhaustive predicates. Do not infer that the existence of a multi-proposer portfolio already solves higher-order composition.

Conversely, the direct engine does not yet provide portfolio allocation, persisted lifecycle events, probabilistic uncertainty, or independent locked-test benchmarking.

## 4. Recommended unified architecture

Adopt a common typed expression AST and a common candidate envelope. A candidate should carry:

- stable candidate ID and grammar version;
- proposer family and proposer version;
- typed expression AST;
- source observation/evidence IDs;
- parent candidate IDs;
- declared expression complexity;
- proposal cost and evaluation cost;
- scope and validity conditions;
- dataset-versioned behavior signatures;
- append-only lifecycle events.

Then use the portfolio as the outer scheduler and the direct composition engine as one proposer family:

1. STAT proposes typed feature predicates.
2. RELATIONAL proposes cross-feature predicates.
3. RANDOM explores grammar-valid candidates.
4. EXHAUSTIVE enumerates a bounded baseline grammar.
5. COMPOSITIONAL combines accepted or Support-screened primitives into sparse typed DAGs.
6. A portfolio allocator distributes one global budget across all families.
7. One shared canonicalizer and type checker validates all outputs.
8. One evidence evaluator performs Support, Gate, and finally Locked Test evaluation.
9. E12-A2 selects additional observations only when a declared measurement can resolve a live ambiguity.
10. E02's registry stores accepted concepts and their evidence-governed lifecycle.

The direct composition engine must not be granted more Gate access or candidate-evaluation budget than other families.

## 5. Integration contract

The next refactor should define these stable interfaces before moving code:

- `Expression`: immutable typed AST with deterministic canonical serialization and evaluation.
- `Candidate`: expression plus provenance, proposer identity, scope, complexity, and cost.
- `Proposer.propose(view, budget)`: returns proposals and explicit budget accounting; no evaluator truth or Locked Test access.
- `Evaluator.evaluate(candidates, split)`: evaluator-side interface; learner process cannot import hidden labels or Test.
- `Portfolio.allocate(family_stats, global_budget)`: returns a deterministic allocation with conservation proof.
- `Registry.append(event)`: append-only lifecycle log; no in-place history rewrite.

A proposer may return fewer candidates than its allocation. Unused budget should be returned to a declared reserve or redistributed under a preregistered policy; it must not be silently reassigned.

## 6. Required integration tests

1. Every proposer emits candidates accepted by the same type checker.
2. Equivalent syntax has one canonical key; different syntax with identical Support behavior remains only empirically equivalent for that dataset.
3. Reordering input rows and feature declarations does not change canonical candidates.
4. Candidate provenance survives composition and simplification.
5. Composition parents must exist and be type-compatible.
6. The global budget is conserved across all proposer families.
7. A proposer cannot inspect Gate or Locked Test while generating proposals.
8. Repeated Gate queries are logged and capped.
9. Test mutation cannot alter proposals, allocations, or Gate decisions.
10. Unidentifiable alternatives remain AMBIGUOUS.
11. A composition proposer can discover A+C+E while B,D are irrelevant.
12. A DSL-misspecification world causes explicit coverage failure or abstention.

## 7. Benchmark interpretation

The current multi-proposer benchmark is a useful first protocol check:
- two synthetic task families: THRESHOLD and PAIRWISE_DIFFERENCE;
- 20 independent seeds per task;
- Support proposal, Gate selection, one-time Locked Test scoring;
- equal proposal-slot budgets.

Its own limitations correctly note that proposal slots are not equivalent to CPU operations or wall-clock cost, and the DSL is hand-specified. Therefore even a successful 20-seed run is preliminary evidence only. It does not establish a general advantage for portfolio search or for CPG-EI.

Next benchmark additions:
- include a sparse triple-composition task with distractors;
- include a nested composition task;
- include a deliberately unidentifiable task;
- compare direct composition, portfolio without COMPOSITIONAL, portfolio with COMPOSITIONAL, random, exhaustive-tiny, and decision-tree baselines;
- match candidate count, evaluation count, and measured runtime separately;
- report coverage, conditional accuracy, false acceptance, abstention calibration, and world-level confidence intervals.

## 8. Decision

Do not merge either branch into main yet.

Keep the direct engine as the reference implementation for sparse expression composition. Keep the portfolio as the reference implementation for heterogeneous proposal scheduling and evidence lifecycle. Integrate them only through the common candidate/expression contract, then run the same benchmark suite against both standalone and combined variants.

The central hypothesis to test is whether the combined system discovers more useful held-out concepts per unit of actual compute while preserving calibrated uncertainty—not whether it merely generates more candidates.
